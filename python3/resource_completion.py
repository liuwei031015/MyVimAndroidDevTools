#!/usr/bin/env python3
"""Complete Android XML attributes and source resources without a language server."""

import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


ATTRIBUTES = {
    "android": "id layout_width layout_height layout_margin layout_marginStart layout_marginEnd layout_marginTop layout_marginBottom layout_weight padding paddingStart paddingEnd paddingTop paddingBottom text hint textColor textSize textStyle inputType imeOptions maxLength maxLines minLines singleLine ellipsize gravity layout_gravity background foreground src contentDescription visibility enabled clickable orientation minWidth minHeight maxWidth elevation importantForAccessibility".split(),
    "app": "layout_constraintTop_toTopOf layout_constraintTop_toBottomOf layout_constraintBottom_toTopOf layout_constraintBottom_toBottomOf layout_constraintStart_toStartOf layout_constraintStart_toEndOf layout_constraintEnd_toStartOf layout_constraintEnd_toEndOf layout_constraintHorizontal_bias layout_constraintVertical_bias layout_constraintDimensionRatio srcCompat tint".split(),
    "tools": "context text hint src visibility ignore".split(),
}


def project_module(path):
    path = Path(path).resolve()
    root = next((parent for parent in path.parents if (parent / "gradlew").is_file()), None)
    if root is None:
        return None
    source = next((parent for parent in path.parents if parent.name == "src"), None)
    return source.parent if source and source.is_relative_to(root) else root


def resources(module, kind, prefix, buffer_lines=()):
    if module is None:
        return []
    names = set()
    for res in (module / "src").glob("*/res"):
        for folder in res.iterdir():
            if not folder.is_dir():
                continue
            category = folder.name.split("-", 1)[0]
            if category == kind and category != "values":
                names.update(path.stem for path in folder.iterdir() if path.is_file())
    names.update(cached_xml_names(module, kind))
    if kind == "id":
        for line in buffer_lines:
            names.update(re.findall(r"@\+id/([A-Za-z_][\w]*)", line))
    return sorted(name for name in names if name.startswith(prefix))[:40]


def cached_xml_names(module, kind):
    source = module / "src"
    values = sorted(source.glob("*/res/values*/*.xml"))
    layouts = sorted(source.glob("*/res/layout*/*.xml")) if kind == "id" else []
    paths = values + layouts
    stamps = [(str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths]
    root = next((parent for parent in (module, *module.parents)
                 if (parent / "gradlew").is_file()), module)
    module_name = (module.relative_to(root).as_posix().replace("/", "_")
                   if module != root else "root")
    cache = root / ".vim-api/resource-completion" / (module_name + "-" + kind + ".json")
    try:
        saved = json.loads(cache.read_text())
        if saved.get("stamps") == [list(stamp) for stamp in stamps]:
            return saved["names"]
    except (OSError, ValueError, KeyError):
        pass
    names = set()
    for path in values:
        try:
            elements = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for element in elements:
            entry_kind = element.get("type") if element.tag == "item" else element.tag
            if entry_kind == kind and element.get("name"):
                names.add(element.get("name"))
    if kind == "id" and layouts:
        result = subprocess.run(["rg", "--no-filename", "--only-matching", "--glob", "*.xml",
                                 r"@\+id/[A-Za-z_][\w]*", str(source)],
                                capture_output=True, text=True, check=False)
        names.update(value.split("/", 1)[1] for value in result.stdout.splitlines())
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"stamps": stamps, "names": sorted(names)}))
    except OSError:
        pass
    return names


def attributes(module, namespace, prefix):
    names = set(ATTRIBUTES.get(namespace, ()))
    if namespace == "app" and module is not None:
        for path in (module / "src").glob("*/res/values*/attrs*.xml"):
            try:
                names.update(element.get("name") for element in ET.parse(path).iter("attr")
                             if element.get("name"))
            except (ET.ParseError, OSError):
                continue
    return sorted(name for name in names if name.startswith(prefix))[:40]


def complete(path, context, buffer_lines=()):
    mode, kind, prefix = context.split(":", 2)
    module = project_module(path)
    if mode == "attribute":
        return [{"word": name + '=""', "abbr": name, "menu": kind + ":",
                 "kind": "a", "user_data": "android_dev_xml_attr"}
                for name in attributes(module, kind, prefix)]
    return [{"word": name, "abbr": name, "menu": "@" + kind + "/", "kind": "r"}
            for name in resources(module, kind, prefix, buffer_lines)]


if __name__ == "__main__":
    lines = json.load(sys.stdin) if "--buffer" in sys.argv[3:] else []
    print(json.dumps(complete(sys.argv[1], sys.argv[2], lines), ensure_ascii=False))
