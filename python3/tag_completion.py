#!/usr/bin/env python3
"""Prefix queries for sorted ctags files and the project class index."""

import json
import mmap
from pathlib import Path
import sys


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


def methods(prefix, tagfiles, current_file="", limit=30):
    result, seen = [], set()
    current = Path(current_file).resolve()
    for path in tagfiles:
        for line in matching_lines(path, prefix, 1000):
            fields = line.split("\t")
            if len(fields) < 4 or fields[3] not in ("m", "kind:m"):
                continue
            attributes = dict(field.split(":", 1) for field in fields[4:] if ":" in field)
            if "file:" in fields[4:] or attributes.get("access") == "private":
                continue
            signature = attributes.get("signature", "")
            owner = attributes.get("class", attributes.get("interface", ""))
            key = (fields[0], owner, signature)
            if key in seen:
                continue
            seen.add(key)
            source = Path(fields[1])
            if not source.is_absolute():
                source = Path(path).parent / source
            same_file = source.name == current.name and source.resolve() == current
            rank = (not same_file,
                    fields[0] != prefix, len(fields[0]), fields[0], owner)
            result.append((rank, {"name": fields[0], "owner": owner,
                                  "signature": signature}))
    result.sort(key=lambda item: item[0])
    return [item for _, item in result[:limit]]


def classes(index, prefix, limit=30):
    if not (Path(index) / "classes.json").is_file():
        return []
    names_file = Path(index) / "class-names"
    if names_file.is_file():
        names = (line.split("\t", 1)[0] for line in matching_lines(names_file, prefix, limit))
    else:
        entries = json.loads((Path(index) / "classes.json").read_text(encoding="utf-8"))
        names = sorted({name.rsplit(".", 1)[-1] for name in entries if "$" not in name
                        and name.rsplit(".", 1)[-1].startswith(prefix)})
    return list(dict.fromkeys(names))[:limit]


def query(index, prefix, current_file, tagfiles):
    return {"classes": classes(index, prefix),
            "methods": methods(prefix, tagfiles, current_file)}


if __name__ == "__main__":
    print(json.dumps(query(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]), ensure_ascii=False))
