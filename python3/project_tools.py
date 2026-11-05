#!/usr/bin/env python3
"""Project resource lookup and device operations used by the Vim commands."""

import argparse
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


RESOURCE = re.compile(r"(?:@\+?|\?)?(?:[\w.]+:)?([\w]+)[/.]([\w.]+)$")
FILE_TYPES = {"anim", "animator", "color", "drawable", "font", "interpolator",
              "layout", "menu", "mipmap", "navigation", "raw", "transition", "xml"}


def resource_key(token):
    token = token.strip('"\'<>(),;')
    if token.startswith("R."):
        token = token[2:]
    match = RESOURCE.search(token)
    return match.groups() if match else ("", "")


def resources(root, module, variant, token=""):
    kind, name = resource_key(token)
    modules = [root / module.strip(":").replace(":", "/")] if module else [
        path.parent.parent for path in root.glob("*/src/main/AndroidManifest.xml")]
    found = []
    for base in modules:
        source = base / "src"
        if not source.is_dir():
            continue
        for res in source.glob("*/res"):
            source_set = res.parent.name
            if source_set != "main" and source_set.lower() not in variant.lower():
                continue
            for folder in res.iterdir():
                if not folder.is_dir():
                    continue
                category = folder.name.split("-", 1)[0]
                if category in FILE_TYPES:
                    if kind and category != kind:
                        continue
                    for path in folder.iterdir():
                        if path.is_file() and (not name or path.stem == name):
                            found.append((category, path.stem, path, 1))
                elif category == "values":
                    for path in folder.glob("*.xml"):
                        try:
                            tree = ET.parse(path)
                        except ET.ParseError:
                            continue
                        for element in tree.getroot():
                            entry_kind = element.get("type") if element.tag == "item" else element.tag
                            entry_name = element.get("name", "")
                            if entry_name and (not kind or entry_kind == kind) and (not name or entry_name == name):
                                line = next((i for i, text in enumerate(path.read_text().splitlines(), 1)
                                             if f'name="{entry_name}"' in text or f"name='{entry_name}'" in text), 1)
                                found.append((entry_kind, entry_name, path, line))
    return sorted(set(found), key=lambda item: (item[0], item[1], str(item[2]), item[3]))


def devices():
    output = subprocess.check_output(["adb", "devices", "-l"], text=True)
    return [(line.split()[0], line.split()[1]) for line in output.splitlines()[1:]
            if len(line.split()) >= 2 and line.split()[1] == "device"]


def lint_diagnostics(report):
    if not report.is_file():
        return []
    lines = []
    for issue in ET.parse(report).getroot().findall("issue"):
        severity = issue.get("severity", "Warning").lower()
        message = issue.get("message", "").replace("\n", " ")
        for location in issue.findall("location"):
            path = location.get("file", "")
            if path:
                lines.append(f"{path}:{location.get('line', '1')}:{location.get('column', '1')}: "
                             f"{severity}: {message} [{issue.get('id', '')}]")
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("resources", "devices", "launch", "lint"))
    parser.add_argument("args", nargs="*")
    args = parser.parse_args()
    if args.action == "resources":
        root, module, variant, *query = args.args
        for kind, name, path, line in resources(Path(root), module, variant, query[0] if query else ""):
            print(f"{kind}/{name}\t{path}\t{line}")
    elif args.action == "devices":
        for serial, state in devices():
            print(f"{serial}\t{state}")
    elif args.action == "lint":
        for line in lint_diagnostics(Path(args.args[0])):
            print(line)
    else:
        serial, package = args.args
        if not re.fullmatch(r"[\w.]+", package):
            raise SystemExit("Invalid application ID")
        subprocess.run(["adb", "-s", serial, "shell", "monkey", "-p", package,
                        "-c", "android.intent.category.LAUNCHER", "1"], check=True)


if __name__ == "__main__":
    try:
        main()
    except (IndexError, ValueError, FileNotFoundError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
