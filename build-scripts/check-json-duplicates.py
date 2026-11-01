#!/usr/bin/env python3
"""Report duplicate keys in `data/**/*.json`.

A merge that adds the same key on both sides resolves cleanly in git and still produces a file the
loader rejects, one file at a time. This scan reports every such file in one pass.
"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]


def strict_pairs(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key {key!r}")
        seen[key] = value
    return seen


def main() -> int:
    bad = 0
    for path in sorted((root / "data").rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)
        except ValueError as err:
            print(f"{path.relative_to(root)}: {err}")
            bad += 1
    print(f"{bad} file(s) with duplicate keys" if bad else "no duplicate keys")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
