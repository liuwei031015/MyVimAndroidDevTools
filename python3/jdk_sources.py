"""Index JDK Java sources in a cache shared by Android projects."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.error
import urllib.request
import zipfile


PUBLIC_TYPE = re.compile(r"\bpublic\s+(?:(?:abstract|final|sealed|non-sealed|strictfp)\s+)*"
                         r"(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)\b")
PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)


def active_jdk():
    result = subprocess.run(["java", "-XshowSettings:properties", "-version"],
                            capture_output=True, text=True, check=True)
    output = result.stdout + result.stderr
    version = re.search(r"^\s*java.version = ([^\s]+)", output, re.MULTILINE)
    home = re.search(r"^\s*java.home = (.+)$", output, re.MULTILINE)
    if not version or not home:
        raise RuntimeError("Cannot determine active JDK version and home")
    preferred = Path(os.environ.get("JAVA_HOME", ""))
    directory = preferred if preferred.is_dir() else Path(home.group(1).strip())
    return version.group(1), directory


def archive_source(version, cache):
    major = version.split(".")[0]
    repository = f"jdk{major}u" if int(major) >= 11 else f"jdk{major}u"
    candidates = (f"jdk-{version}-ga", f"jdk-{version}")
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "openjdk-sources.zip"
    pending = cache / "openjdk-sources.download"
    for tag in candidates:
        url = f"https://github.com/openjdk/{repository}/archive/refs/tags/{tag}.zip"
        try:
            with urllib.request.urlopen(url, timeout=30) as response, pending.open("wb") as output:
                shutil.copyfileobj(response, output)
            with zipfile.ZipFile(pending) as source:
                if any("/share/classes/" in name and name.endswith(".java")
                       for name in source.namelist()):
                    pending.replace(archive)
                    return archive
        except (urllib.error.URLError, zipfile.BadZipFile):
            continue
        finally:
            pending.unlink(missing_ok=True)
    raise RuntimeError(f"No OpenJDK source archive found for {version}; install a JDK with src.zip")


def source_target(member):
    parts = Path(member).parts
    if not parts or ".." in parts or not member.endswith(".java"):
        return None
    if "share" in parts and "classes" in parts:
        index = parts.index("share")
        if index >= 1 and parts[index + 1] == "classes":
            return Path(parts[index - 1], *parts[index + 2:])
    if len(parts) >= 3 and parts[0].startswith(("java.", "jdk.")):
        return Path(*parts)
    return None


def ensure_jdk_sources(download=False):
    version, home = active_jdk()
    cache = Path.home() / ".cache/vim-android-dev" / ("jdk-" + version)
    local = next((path for path in (home / "lib/src.zip", home / "src.zip", home.parent / "src.zip")
                  if path.is_file()), None)
    archive = local or (cache / "openjdk-sources.zip" if (cache / "openjdk-sources.zip").is_file() else None)
    if archive is None and download:
        archive = archive_source(version, cache)
    if archive is None:
        return None
    stat = archive.stat()
    stamp = f"3:{archive}:{stat.st_size}:{stat.st_mtime_ns}"
    if (cache / "fingerprint").is_file() and (cache / "fingerprint").read_text() == stamp:
        return cache
    sources = cache / "sources"
    if sources.exists():
        shutil.rmtree(sources)
    sources.mkdir(parents=True)
    classes = {}
    with zipfile.ZipFile(archive) as source:
        for member in source.namelist():
            relative = source_target(member)
            if relative is None:
                continue
            target = sources / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read(member)
            target.write_bytes(data)
            content = data.decode("utf-8", errors="replace")
            package = PACKAGE.search(content)
            public_type = PUBLIC_TYPE.search(content)
            if not package or not public_type or public_type.group(1) != target.stem:
                continue
            if package.group(1).startswith(("jdk.internal", "sun.")):
                continue
            name = package.group(1) + "." + target.stem
            classes[name] = {"jar": "", "binary": "", "coordinate": "JDK " + version,
                             "bytecode_name": name, "source": str(target)}
    cache.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ctags", "--languages=Java", "--fields=+nS", "--output-format=e-ctags",
                    "-R", "-f", str(cache / "tags"), str(sources)], check=True)
    (cache / "classes.json").write_text(json.dumps(classes), encoding="utf-8")
    (cache / "fingerprint").write_text(stamp)
    return cache
