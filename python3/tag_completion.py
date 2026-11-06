#!/usr/bin/env python3
"""Prefix queries for sorted ctags files and the project class index."""

import json
import mmap
import os
from pathlib import Path
import re
import sys
import tempfile


def matching_lines(path, prefix, limit):
    if not Path(path).is_file() or not Path(path).stat().st_size:
        return
    target = prefix.encode("utf-8")
    with open(path, "rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
        low, high = 0, len(data)
        while low < high:
            middle = (low + high) // 2
            start = 0 if middle == 0 else data.find(b"\n", middle - 1) + 1
            if start >= high:
                high = middle
                continue
            end = data.find(b"\n", start)
            if end < 0:
                end = len(data)
            separator = data.find(b"\t", start, end)
            name = data[start:separator if separator >= 0 else end]
            if name < target:
                low = end + 1
            else:
                high = start
        count = 0
        while low < len(data) and count < limit:
            end = data.find(b"\n", low)
            if end < 0:
                end = len(data)
            line = data[low:end]
            if not line.startswith(target):
                break
            yield line.decode("utf-8", errors="replace")
            count += 1
            low = end + 1


def project_root(index, current_file):
    current = Path(current_file).resolve()
    for directory in current.parents:
        if (directory / ".vim-api").is_dir() or (directory / "gradlew").is_file():
            return directory
    index_path = Path(index).resolve()
    return index_path.parents[2] if ".vim-api" in index_path.parts else current.parent


def current_owners(current_file):
    try:
        content = Path(current_file).read_text(encoding="utf-8", errors="replace")[:12000]
    except OSError:
        return set()
    declaration = re.search(r"\bclass\s+([A-Za-z_$][\w$]*)[^{};]*?"
                            r"(?:\bextends\s+([A-Za-z_$][\w.$]*))?\s*(?:implements|\{)",
                            content)
    if not declaration:
        return set()
    return {name.rsplit(".", 1)[-1] for name in declaration.groups() if name}


def source_path(tagfile, entry):
    source = Path(entry)
    return source if source.is_absolute() else Path(tagfile).parent / source


def in_project(source, root):
    try:
        relative = source.absolute().relative_to(root)
    except ValueError:
        try:
            relative = source.resolve().relative_to(root)
        except ValueError:
            return False
    return ".vim-api" not in relative.parts and "build" not in relative.parts


def project_classes(prefix, tagfiles, root, current_file, limit=12):
    found = {}
    current_dir = Path(current_file).resolve().parent
    for path in tagfiles:
        for line in matching_lines(path, prefix, 500):
            fields = line.split("\t")
            if len(fields) < 4 or fields[3] not in ("c", "i", "e", "a", "kind:c",
                                                  "kind:i", "kind:e", "kind:a"):
                continue
            name = fields[0]
            if "." in name:
                continue
            source = source_path(path, fields[1])
            if not in_project(source, root):
                continue
            rank = (source.absolute().parent != current_dir, len(name), name)
            if name not in found or rank < found[name]:
                found[name] = rank
        if found:
            break
    return [name for name, _ in sorted(found.items(), key=lambda item: item[1])[:limit]]


def methods(prefix, tagfiles, current_file="", root=None, limit=30):
    result, seen = [], set()
    current = Path(current_file).resolve()
    owners = current_owners(current_file)
    project_count = 0
    for path in tagfiles:
        for line in matching_lines(path, prefix, 1000):
            fields = line.split("\t")
            if len(fields) < 4 or fields[3] not in ("m", "kind:m"):
                continue
            attributes = dict(field.split(":", 1) for field in fields[4:] if ":" in field)
            signature = attributes.get("signature", "")
            owner = attributes.get("class", attributes.get("interface", ""))
            source = source_path(path, fields[1])
            same_file = source.name == current.name and source.resolve() == current
            if ("file:" in fields[4:] or attributes.get("access") == "private") and not same_file:
                continue
            local = root is not None and in_project(source, root)
            key = (fields[0], owner, signature)
            if key in seen:
                continue
            seen.add(key)
            if local:
                project_count += 1
            scope = 0 if same_file else 1 if owner in owners and local else 2 if local else 3
            rank = (scope, fields[0] != prefix, len(fields[0]), fields[0], owner)
            result.append((rank, {"name": fields[0], "owner": owner,
                                  "signature": signature}))
        if project_count >= 12:
            break
    result.sort(key=lambda item: item[0])
    return [item for _, item in result[:limit]]


def classes(index, prefix, limit=30):
    if not (Path(index) / "classes.json").is_file():
        return []
    names_file = Path(index) / "class-names"
    if not names_file.is_file():
        entries = json.loads((Path(index) / "classes.json").read_text(encoding="utf-8"))
        names = sorted({name.rsplit(".", 1)[-1] for name in entries if "$" not in name})
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=index,
                                         prefix=".class-names-", delete=False) as temporary:
            temporary.write("\n".join(names) + "\n")
        os.replace(temporary.name, names_file)
    names = (line.split("\t", 1)[0] for line in matching_lines(names_file, prefix, limit))
    return list(dict.fromkeys(names))[:limit]


def query(index, prefix, current_file, tagfiles):
    root = project_root(index, current_file)
    if prefix[:1].isupper():
        return {"project_classes": project_classes(prefix, tagfiles, root, current_file),
                "classes": classes(index, prefix), "methods": []}
    return {"project_classes": [], "classes": [],
            "methods": methods(prefix, tagfiles, current_file, root)}


if __name__ == "__main__":
    print(json.dumps(query(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]), ensure_ascii=False))
