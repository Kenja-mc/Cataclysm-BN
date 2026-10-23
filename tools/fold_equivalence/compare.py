#!/usr/bin/env python3
"""Compare a mainline fold baseline with the fork dump and report every mismatch.

The mainline dump (`--dump-stats FOLDED ... <requests.json>`) produces the baseline.
The fork dump (`--dump-stats FOLDED ... <baseline.json>`) spawns the migrated replacement
fresh and through the save-load path, then this script compares both with the baseline.

Usage:
  tools/fold_equivalence/compare.py --baseline baseline.json --fork fork.json \
      [--allowlist allowlist.json] [--json out.json] [--markdown out.md]
"""

import argparse
import json
import sys

# Identity, not balance: the fold intentionally replaces the id, chooses the variant and
# records the stack modifier.  Their gameplay effects appear in the compared fields.
IDENTITY_FIELDS = {
    "type_id", "variant", "stack_modifiers", "effective_modifier",
}

# Order-insensitive containers.
SORTED_FIELDS = {"materials", "flags", "use_methods", "techniques", "ammo_types",
                 "magazine_compatible", "covers", "effects"}
SORTED_OBJECT_LISTS = {"contents", "damage", "portions", "components"}


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def normalise(value, key=None, depth=0):
    if isinstance(value, dict):
        return {k: normalise(v, k, depth + 1) for k, v in sorted(value.items())
                if k not in IDENTITY_FIELDS}
    if isinstance(value, list):
        items = [normalise(v, key, depth + 1) for v in value]
        if key in SORTED_OBJECT_LISTS:
            items.sort(key=lambda item: json.dumps(item, sort_keys=True))
        elif key in SORTED_FIELDS:
            items.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return items
    if isinstance(value, float):
        rounded = round(value, 6)
        return int(rounded) if rounded == int(rounded) else rounded
    return value


def same_value(left, right):
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        # Float32 accumulation in the stack-modifier multipliers is representation noise;
        # every real difference in this data is far above one hundredth of a cent.
        return abs(left - right) <= max(0.01, 1e-6 * max(abs(left), abs(right)))
    return left == right


def flatten(node, prefix=""):
    out = {}
    if isinstance(node, dict):
        for key, value in node.items():
            if key in IDENTITY_FIELDS:
                continue
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (dict, list)):
                sub = flatten(value, path)
                if sub:
                    out.update(sub)
                else:
                    out[path] = value
            else:
                out[path] = value
    elif isinstance(node, list):
        out[prefix] = node
    else:
        out[prefix] = node
    return out


def compare_props(expected, actual):
    """Deep compare two normalised prop trees; return [(field, expected, actual)]."""
    diffs = []
    expected_flat = flatten(normalise(expected))
    actual_flat = flatten(normalise(actual))
    for field in sorted(set(expected_flat) | set(actual_flat)):
        if field not in actual_flat:
            diffs.append((field, expected_flat[field], None))
        elif field not in expected_flat:
            diffs.append((field, None, actual_flat[field]))
        elif not same_value(expected_flat[field], actual_flat[field]):
            diffs.append((field, expected_flat[field], actual_flat[field]))
    return diffs


def index_records(dump):
    records = {}
    for record in dump.get("records", []):
        key = (record["id"], bool(record.get("has_charges")), record.get("charges", 0))
        records[key] = record
    return records


def load_allowlist(path):
    if not path:
        return {}
    data = load(path)
    allowed = {}
    for entry in data.get("allowed", []):
        allowed[(entry["id"], entry["view"], entry["field"])] = entry.get("reason", "")
    return allowed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--fork", required=True)
    parser.add_argument("--allowlist")
    parser.add_argument("--json")
    parser.add_argument("--markdown")
    args = parser.parse_args()

    baseline = load(args.baseline)
    fork = load(args.fork)
    allowlist = load_allowlist(args.allowlist)
    base_records = index_records(baseline)
    fork_records = index_records(fork)

    results = []
    for key, base in sorted(base_records.items(), key=lambda item: str(item[0])):
        old_id = base["id"]
        fork_record = fork_records.get(key)
        entry = {"id": old_id, "charges": base.get("charges"),
                 "has_charges": base.get("has_charges", False),
                 "replacement": None, "mismatches": {}}
        if fork_record is None:
            entry["mismatches"]["missing"] = [
                {"view": "record", "field": "record", "mainline": "present", "fork": None}]
            results.append(entry)
            continue
        entry["replacement"] = fork_record.get("replacement")
        for view in ("fresh", "migrated"):
            actual = fork_record.get(view)
            if actual is None:
                entry["mismatches"][view] = [
                    {"view": view, "field": "item", "mainline": "present", "fork": None}]
                continue
            # For an ammo stack, ammo_current is the item's own type id, i.e. the identity
            # that the migration replaces by design.  For a magazine it is the loaded ammo.
            ignore_ammo_current = (
                base["props"].get("ammo_current") == base["props"].get("type_id") and
                actual.get("ammo_current") == actual.get("type_id"))
            diffs = compare_props(base["props"], actual)
            kept = []
            for field, old, new in diffs:
                if (old_id, view, field) in allowlist:
                    continue
                if ignore_ammo_current and field == "ammo_current":
                    continue
                kept.append({"view": view, "field": field, "mainline": old, "fork": new})
            if kept:
                entry["mismatches"][view] = kept
        if entry["mismatches"]:
            results.append(entry)

    report = {
        "baseline": args.baseline,
        "fork": args.fork,
        "records_compared": len(base_records),
        "records_with_mismatches": len(results),
        "allowlisted": len(allowlist),
        "results": results,
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, sort_keys=True)

    total = sum(len(v) for record in results for v in record["mismatches"].values())
    print(f"compared {len(base_records)} spawned items; "
          f"{len(results)} ids differ, {total} field mismatches")
    for record in results:
        for view in sorted(record["mismatches"]):
            for diff in record["mismatches"][view]:
                print(f"{record['id']} -> {record['replacement']} [{view}] "
                      f"{diff['field']}: {diff['mainline']!r} != {diff['fork']!r}")

    if args.markdown:
        lines = ["| old id | replacement | view | field | mainline | fork |",
                 "|---|---|---|---|---|---|"]
        for record in results:
            for view in sorted(record["mismatches"]):
                for diff in record["mismatches"][view]:
                    lines.append(
                        f"| `{record['id']}` | `{record['replacement']}` | {view} | "
                        f"`{diff['field']}` | {diff['mainline']!r} | {diff['fork']!r} |")
        with open(args.markdown, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    return 1 if results else 0


if __name__ == "__main__":
    sys.exit(main())
