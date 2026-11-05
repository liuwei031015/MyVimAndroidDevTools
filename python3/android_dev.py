#!/usr/bin/env python3
"""Build a project-local Java API index from resolved Gradle artifacts."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from jdk_sources import ensure_jdk_sources


DECLARATION = re.compile(r"^(.*?)\b(class|interface|enum|record)\s+([\w.$]+)(.*)$")
INDEX_VERSION = 3


def unpack_classes(archive, destination):
    if archive.suffix == ".jar":
        return archive
    with zipfile.ZipFile(archive) as outer:
        if "classes.jar" not in outer.namelist():
            return None
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(outer.read("classes.jar"))
    return destination


def source_jar(coordinate):
    parts = coordinate.split(":")
    if len(parts) != 3:
        return None
    group, name, version = parts
    base = Path.home() / ".gradle/caches/modules-2/files-2.1" / group / name / version
    matches = sorted(base.glob(f"*/{name}-{version}-sources.jar"))
    return matches[0] if matches else None


def java_classes(jar):
    with zipfile.ZipFile(jar) as archive:
        return sorted({entry[:-6].replace("/", ".") for entry in archive.namelist()
                       if entry.endswith(".class") and not entry.startswith("META-INF/")
                       and not entry.endswith(("module-info.class", "package-info.class"))
                       and not re.search(r"\$\d+(?:\.|\$)", entry)})


def write_sources(archive, destination):
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            path = Path(member.filename)
            if path.suffix != ".java" or path.is_absolute() or ".." in path.parts:
                continue
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(member))


def write_stubs(jar, classes, destination):
    top_level = [name for name in classes if "$" not in name and name.rsplit(".", 1)[-1] != "R"]
    for start in range(0, len(top_level), 80):
        batch = top_level[start:start + 80]
        result = subprocess.run(["javap", "-public", "-classpath", str(jar), *batch],
                                capture_output=True, text=True, check=False)
        if result.returncode and not result.stdout:
            continue
        current = []
        for line in result.stdout.splitlines():
            if line.startswith('Compiled from ') and current:
                save_stub(current, destination)
                current = []
            if not line.startswith('Compiled from '):
                current.append(line)
        if current:
            save_stub(current, destination)


def save_stub(lines, destination):
    for index, line in enumerate(lines):
        match = DECLARATION.match(line)
        if not match:
            continue
        qualified = match.group(3)
        if "." not in qualified:
            return
        package, simple = qualified.rsplit(".", 1)
        lines[index] = f"{match.group(1)}{match.group(2)} {simple}{match.group(4)}"
        target = destination / Path(*package.split(".")) / f"{simple}.java"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"package {package};\n\n" + "\n".join(lines[index:]) + "\n",
                          encoding="utf-8")
        return


def fingerprint(manifest, jdk_cache):
    items = [INDEX_VERSION, manifest["module"], manifest["variant"], manifest.get("compileSdk", "")]
    if jdk_cache:
        items.append((str(jdk_cache), (jdk_cache / "fingerprint").read_text()))
    for artifact in manifest["artifacts"]:
        path = Path(artifact["path"])
        stat = path.stat()
        source = source_jar(artifact["coordinate"])
        items.append((str(path), artifact["coordinate"], stat.st_size, stat.st_mtime_ns,
                      str(source) if source else ""))
    for module in manifest.get("projectModules", {}).values():
        symbols = resource_symbols(module, manifest["variant"])
        if symbols:
            stat = symbols.stat()
            items.append((str(symbols), stat.st_size, stat.st_mtime_ns))
    return hashlib.sha256(repr(items).encode()).hexdigest()


def module_sources(directory):
    source_root = Path(directory) / "src"
    mapping = {}
    if source_root.is_dir():
        for source in source_root.rglob("*.java"):
            parts = source.parts
            if "java" not in parts:
                continue
            relative = parts[parts.index("java") + 1:]
            if relative:
                mapping[".".join(relative)[:-5]] = str(source)
    return mapping


def resource_symbols(module, variant):
    build = Path(module["directory"]) / "build/intermediates"
    if not build.is_dir():
        return None
    candidates = list(build.glob(f"**/{variant}/**/R.txt"))
    if not candidates and variant.endswith("Debug"):
        candidates = list(build.glob("**/debug/**/R.txt"))
    if not candidates:
        return None
    preferred = [path for path in candidates if "runtime_symbol_list" in path.parts
                 or "compile_symbol_list" in path.parts]
    return sorted(preferred or candidates)[0]


def write_r_stub(symbols, namespace, destination):
    groups = {}
    for line in symbols.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] in ("int", "int[]"):
            groups.setdefault(parts[1], []).append((parts[0], parts[2]))
    if not groups:
        return None
    target = destination / Path(*namespace.split(".")) / "R.java"
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"package {namespace};", "", "public final class R {"]
    for group, fields in sorted(groups.items()):
        lines.append(f"    public static final class {group} {{")
        for kind, name in sorted(set(fields)):
            if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                lines.append(f"        public static final {kind} {name};")
        lines.append("    }")
    lines.append("}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def sdk_index(manifest):
    sdk = Path(manifest.get("sdkDirectory", ""))
    raw_platform = manifest.get("compileSdk", "")
    platform = str(raw_platform) if str(raw_platform).startswith("android-") else f"android-{raw_platform}"
    if not sdk.is_dir() or not raw_platform:
        return None
    android_jar = sdk / "platforms" / platform / "android.jar"
    if not android_jar.exists():
        return None
    cache = Path.home() / ".cache/vim-android-dev" / platform
    source = sdk / "sources" / platform
    stamp = f"{INDEX_VERSION}:{android_jar.stat().st_size}:{android_jar.stat().st_mtime_ns}:{source if source.is_dir() else ''}"
    if not (cache / "fingerprint").exists() or (cache / "fingerprint").read_text() != stamp:
        cache.mkdir(parents=True, exist_ok=True)
        classes = {}
        for name in java_classes(android_jar):
            outer = name.split("$", 1)[0]
            source_file = source / (outer.replace(".", "/") + ".java")
            classes[name.replace("$", ".")] = {
                "jar": str(android_jar), "binary": str(android_jar),
                "coordinate": platform, "bytecode_name": name,
                "source": str(source_file) if source_file.exists() else ""}
        (cache / "classes.json").write_text(json.dumps(classes), encoding="utf-8")
        if source.is_dir():
            subprocess.run(["ctags", "--languages=Java", "--fields=+n", "--output-format=e-ctags",
                            "-R", "-f", str(cache / "tags"), str(source)], check=True)
        (cache / "fingerprint").write_text(stamp)
    return cache


def build(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent.parent
    name = manifest_path.stem
    output = root / "index" / name
    jdk_cache = ensure_jdk_sources(download=False)
    stamp = fingerprint(manifest, jdk_cache)
    sdk_cache = sdk_index(manifest)
    if (output / "fingerprint").exists() and (output / "fingerprint").read_text() == stamp:
        print(output)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=output.parent))
    classes = {}
    try:
        if jdk_cache and (jdk_cache / "classes.json").exists():
            classes.update(json.loads((jdk_cache / "classes.json").read_text(encoding="utf-8")))
        if sdk_cache and (sdk_cache / "classes.json").exists():
            classes.update(json.loads((sdk_cache / "classes.json").read_text(encoding="utf-8")))
        project_sources = {}
        for position, artifact in enumerate(manifest["artifacts"]):
            binary = Path(artifact["path"])
            if binary.suffix not in (".jar", ".aar"):
                continue
            jar = unpack_classes(binary, temporary / "jars" / f"{position}.jar")
            if jar is None:
                continue
            found = java_classes(jar)
            for qualified in found:
                classes.setdefault(qualified.replace("$", "."), {
                    "jar": str(jar if binary.suffix == ".jar" else Path("jars") / f"{position}.jar"),
                    "binary": str(binary), "coordinate": artifact["coordinate"],
                    "bytecode_name": qualified})
            source = source_jar(artifact["coordinate"])
            if source:
                write_sources(source, temporary / "sources" / str(position))
            else:
                write_stubs(jar, found, temporary / "stubs" / str(position))
            folder = "sources" if source else "stubs"
            component = artifact["coordinate"]
            if component.startswith("project ") and component[8:] in manifest.get("projectModules", {}):
                module = manifest["projectModules"][component[8:]]
                project_sources.setdefault(component, module_sources(module["directory"]))
            for qualified in found:
                outer = qualified.split("$", 1)[0]
                path = Path(folder) / str(position) / (outer.replace(".", "/") + ".java")
                if (temporary / path).exists():
                    classes[qualified.replace("$", ".")]["source"] = str(path)
                if component in project_sources and outer in project_sources[component]:
                    classes[qualified.replace("$", ".")]["source"] = project_sources[component][outer]
        for module_name, module in manifest.get("projectModules", {}).items():
            symbols = resource_symbols(module, manifest["variant"])
            namespace = module.get("namespace", "")
            if symbols and namespace:
                path = write_r_stub(symbols, namespace,
                                    temporary / "stubs" / ("R" + module_name.replace(":", "_")))
                if path:
                    classes[namespace + ".R"] = {
                        "jar": "", "binary": "", "coordinate": module_name + " resources",
                        "bytecode_name": namespace + ".R", "source": str(path.relative_to(temporary))}
        folders = [folder for folder in ("sources", "stubs") if (temporary / folder).exists()]
        if folders:
            subprocess.run(["ctags", "--languages=Java", "--fields=+n", "--output-format=e-ctags",
                            "-R", "-f", "tags", *folders], cwd=temporary, check=True)
        else:
            (temporary / "tags").touch()
        (temporary / "classes.json").write_text(json.dumps(classes, ensure_ascii=False), encoding="utf-8")
        if sdk_cache and (sdk_cache / "tags").exists():
            (temporary / "sdk-tags").write_text(str(sdk_cache / "tags"), encoding="utf-8")
        if jdk_cache and (jdk_cache / "tags").exists():
            (temporary / "jdk-tags").write_text(str(jdk_cache / "tags"), encoding="utf-8")
        (temporary / "fingerprint").write_text(stamp)
        if output.exists():
            shutil.rmtree(output)
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    print(output)


def lookup(index, action, query):
    entries = json.loads((Path(index) / "classes.json").read_text(encoding="utf-8"))
    if action == "classes":
        for name, info in sorted(entries.items()):
            print(f"{name}\t{info['coordinate']}")
    elif action == "imports":
        for name in sorted(entries):
            if name.rsplit(".", 1)[-1] == query:
                print(name)
    elif action in ("methods", "location"):
        info = entries.get(query)
        if not info:
            matches = [(name, value) for name, value in entries.items()
                       if name.rsplit(".", 1)[-1] == query]
            if len(matches) == 1:
                query, info = matches[0]
        if not info:
            raise SystemExit(f"Unknown class: {query}")
        if action == "location":
            source = info.get("source", "")
            if not source:
                raise SystemExit(f"No source or declaration for: {query}")
            print(source if Path(source).is_absolute() else Path(index) / source)
            return
        if info.get("coordinate", "").endswith(" resources"):
            source = info["source"]
            print((Path(index) / source).read_text(encoding="utf-8"))
            return
        if info.get("coordinate", "").startswith("JDK "):
            subprocess.run(["javap", "-public", info["bytecode_name"]], check=True)
            return
        binary = Path(info["binary"])
        jar = Path(info["jar"])
        if not jar.is_absolute():
            jar = Path(index) / jar
        if binary.suffix == ".aar" and not jar.is_file():
            source_parts = Path(info.get("source", "")).parts
            if len(source_parts) > 1 and source_parts[1].isdigit():
                jar = Path(index) / "jars" / (source_parts[1] + ".jar")
        if jar.is_file() and jar.suffix == ".jar":
            subprocess.run(["javap", "-public", "-classpath", str(jar),
                            info["bytecode_name"]], check=True)
        elif binary.suffix == ".aar":
            with tempfile.TemporaryDirectory() as directory:
                extracted = unpack_classes(binary, Path(directory) / "classes.jar")
                subprocess.run(["javap", "-public", "-classpath", str(extracted),
                                info["bytecode_name"]], check=True)
        else:
            raise SystemExit(f"Class archive is missing: {jar}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "classes", "imports", "methods", "location", "jdk"))
    parser.add_argument("path", nargs="?", default="")
    parser.add_argument("query", nargs="?", default="")
    args = parser.parse_args()
    if args.action == "jdk":
        cache = ensure_jdk_sources(download=True)
        print(cache)
    elif args.action == "build":
        build(args.path)
    else:
        lookup(args.path, args.action, args.query)


if __name__ == "__main__":
    main()
