#!/usr/bin/env python3
"""Merge per-shard `--durations` files into tests/e2e/durations.json.

Each CI shard writes its own timings file, uploaded as the `e2e-suite-log-<shard>`
artifact. Download them, then run:

  python3 tests/e2e/merge_durations.py /tmp/e2e-durations-shard-*.json --write

Without --write it only prints the merge. Tests missing from the inputs keep the value
already in the manifest, so refreshing from one shard cannot erase the other tests.
The manifest holds CI timings after a refresh: the shard split predicts CI cost, not
this machine's.
"""
import argparse
import json
from pathlib import Path

MANIFEST = Path(__file__).with_name("durations.json")


def merged(files):
    result = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for path in files:
        for name, seconds in json.loads(Path(path).read_text()).items():
            result[name] = round(float(seconds), 1)
    return dict(sorted(result.items()))


def main():
    parser = argparse.ArgumentParser(
        description="Merge e2e --durations files into tests/e2e/durations.json.")
    parser.add_argument("files", nargs="+", type=Path, help="per-shard duration JSON files")
    parser.add_argument("--write", action="store_true", help="update tests/e2e/durations.json")
    args = parser.parse_args()
    timings = merged(args.files)
    known = set(json.loads(MANIFEST.read_text())) if MANIFEST.exists() else set()
    names = [name for path in args.files for name in json.loads(path.read_text())]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        print(f"warning: {len(duplicates)} tests ran in more than one shard: {duplicates}")
    print(f"{len(timings)} tests, {sum(timings.values()):.0f}s total, "
          f"{len(set(names) - known)} new")
    if args.write:
        MANIFEST.write_text(json.dumps(timings, indent=1, sort_keys=True) + "\n")
        print(f"wrote {MANIFEST}")
    else:
        print("pass --write to update the manifest")


if __name__ == "__main__":
    main()
