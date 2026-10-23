#!/usr/bin/env python3
"""Extract folded item ids and static mismatches between mainline and the fork.

Usage:
  tools/fold_equivalence/extract.py --mainline /path/to/mainline --fork /path/to/fork \
      --requests /tmp/fold_requests.json --report /tmp/fold_static.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fold_data  # noqa: E402

UNIT_FIELDS = fold_data.UNIT_FIELDS

# Play-breaking fields: a fresh spawn no longer has the same charge/ammo state.
SPAWN_STATE_FIELDS = {
    "count", "capacity", "charges", "def_charges", "max_charges", "stack_size",
    "rand_charges", "default_ammo", "energy", "max_capacity", "ammo_type",
}

GAMEPLAY_FIELDS = {
    "weight", "volume", "price", "price_postapoc", "material", "flags", "bashing",
    "cutting", "stab", "to_hit", "qualities", "damage", "range", "dispersion",
    "recoil", "armor_penetration", "loudness", "speed", "effects", "ammo_effects",
    "reload_time", "reliability", "linkage", "protects_contents", "seals",
    "watertight", "preserves", "unseals_into", "contains", "storage", "warmth",
    "encumbrance", "coverage", "env_resist", "env_resist_w_filter", "thickness",
    "fun", "intelligence", "time", "chapters", "skill", "level", "req",
    "calories", "nutrition", "quench", "healthy", "addict", "stim", "fatigue_mod",
    "parasites", "radiation", "spoils", "comesttype", "tool", "cooks_like",
    "smoking_result", "monotony_penalty", "clip", "durability", "sight_dispersion",
    "ups_charges", "ammo_to_fire", "skill_used", "built_in_mods", "default_mods",
    "default_container", "components", "revert_to", "subtype", "power_draw",
    "charges_per_use", "turns_per_charge", "charge_factor", "rigid",
    "light_emission", "use_methods", "techniques", "description",
}

SEVERITY_ORDER = {"BREAKS PLAY": 0, "BALANCE CHANGE": 1, "PRESENTATION ONLY": 2,
                  "IDENTITY/STATE": 3}


def collect_context(root, subdir, label):
    return fold_data.Context(root, subdir, label)


def normalise_def(ctx, ident, variant=None, modifiers=None):
    raw = ctx.resolve(ident)
    if raw is None:
        return None
    out = {}
    for key, value in raw.items():
        if key in fold_data.PRESENTATION_KEYS:
            continue
        if key in ("id", "abstract", "type"):
            continue
        out[key] = fold_data.normalise_value(key, value)
    if variant:
        mult = variant.get("price_multiplier")
        if mult is not None:
            if "price" in out and isinstance(out["price"], (int, float)):
                out["price"] = out["price"] * mult
            if "price_postapoc" in out and isinstance(out["price_postapoc"], (int, float)):
                out["price_postapoc"] = out["price_postapoc"] * mult
        if variant.get("material"):
            out["material"] = sorted(variant["material"])
        if variant.get("components"):
            out["variant_components"] = sorted(
                [str(c[0]), int(c[1])] for c in variant["components"])
    if modifiers:
        factor_damage = 1.0
        factor_pen = 1.0
        factor_disp = 1.0
        factor_recoil = 1.0
        for mod in modifiers:
            factor_damage *= mod.get("damage", 1.0)
            factor_pen *= mod.get("armor_penetration", 1.0)
            factor_disp *= mod.get("dispersion", 1.0)
            factor_recoil *= mod.get("recoil", 1.0)
        if isinstance(out.get("damage"), list):
            for unit in out["damage"]:
                if isinstance(unit, dict):
                    if "amount" in unit:
                        unit["amount"] = unit["amount"] * factor_damage
                    if "armor_penetration" in unit:
                        unit["armor_penetration"] = unit["armor_penetration"] * factor_pen
        if isinstance(out.get("dispersion"), (int, float)):
            out["dispersion"] = out["dispersion"] * factor_disp
        if isinstance(out.get("recoil"), (int, float)):
            out["recoil"] = out["recoil"] * factor_recoil
        price_factor = 1.0
        price_post_factor = 1.0
        added_effects = set()
        removed_effects = set()
        for mod in modifiers:
            price_factor *= mod.get("price", 1.0)
            price_post_factor *= mod.get("price_postapoc", 1.0)
            added_effects.update(mod.get("ammo_effects", []) or [])
            removed_effects.update(mod.get("remove_ammo_effects", []) or [])
        for key, factor in (("price", price_factor), ("price_postapoc", price_post_factor)):
            if isinstance(out.get(key), (int, float)):
                out[key] = out[key] * factor
        if added_effects or removed_effects:
            effects = set(out.get("effects", []) or []) - removed_effects
            effects |= added_effects
            out["effects"] = sorted(effects)
    return out


def severity_for(field):
    if field in SPAWN_STATE_FIELDS:
        return "BREAKS PLAY"
    return "BALANCE CHANGE"


# Variant components are represented additively; the uncraft comparison checks the
# resulting yields, so the raw field itself is not a difference.
REPRESENTATION_ONLY_FIELDS = {"variant_components"}


def diff_defs(old, new):
    changes = []
    for key in sorted(set(old) | set(new)):
        if key in REPRESENTATION_ONLY_FIELDS:
            continue
        if key in SPAWN_STATE_FIELDS:
            severity = "BREAKS PLAY"
        else:
            severity = "BALANCE CHANGE"
        if key not in old:
            changes.append({"field": key, "old": None, "new": new[key],
                            "severity": severity})
        elif key not in new:
            changes.append({"field": key, "old": old[key], "new": None,
                            "severity": severity})
        elif old[key] != new[key]:
            changes.append({"field": key, "old": old[key], "new": new[key],
                            "severity": severity})
    return changes


def build_groups(ctx):
    """item_group id -> list of entries (modern and legacy shapes)."""
    groups = {}
    for _path, data in ctx.docs:
        for obj in data:
            if not isinstance(obj, dict) or obj.get("type") != "item_group":
                continue
            ident = obj.get("id")
            if not isinstance(ident, str):
                continue
            entries = groups.setdefault(ident, [])
            for key in ("entries", "items"):
                for entry in obj.get(key, []) or []:
                    if isinstance(entry, str):
                        entries.append({"item": entry})
                    elif isinstance(entry, list) and entry and isinstance(entry[0], str):
                        item = {"item": entry[0]}
                        if len(entry) > 1:
                            item["prob"] = entry[1]
                        if len(entry) > 2:
                            item["count"] = entry[2]
                        entries.append(item)
                    elif isinstance(entry, dict):
                        entries.append(entry)
    return groups


def reference_entry(node):
    """Copy an entry and normalise schema aliases used by the fork."""
    entry = dict(node)
    if "item_variant" in entry and "variant" not in entry:
        entry["variant"] = entry.pop("item_variant")
    else:
        entry.pop("item_variant", None)
    return entry


def singleton_group_entry(groups, ident, depth, seen):
    """Return the single item entry of a group that is a pure indirection, else None."""
    if depth > 8 or ident in seen or ident not in groups:
        return None
    seen.add(ident)
    entries = groups[ident]
    if len(entries) != 1:
        return None
    inner = dict(entries[0])
    if "group" in inner:
        return singleton_group_entry(groups, inner["group"], depth + 1, seen)
    if isinstance(inner.get("item"), str):
        return inner
    return None


def iter_entries(node, path, owner, sink, groups=None, depth=0):
    """Find spawn entries that mention an item id."""
    groups = groups or {}
    if depth > 8:
        return
    if isinstance(node, dict):
        this_owner = owner
        if node.get("type") == "item_group" and isinstance(node.get("id"), str):
            this_owner = ("item_group", node["id"])
        elif node.get("type") == "profession" and isinstance(node.get("id"), str):
            this_owner = ("profession", node["id"])
        elif node.get("type") == "mission_definition" and isinstance(node.get("id"), str):
            this_owner = ("mission", node["id"])
        item = node.get("item")
        if isinstance(item, str):
            sink.append({"owner": this_owner, "path": path, "entry": reference_entry(node)})
        elif isinstance(item, list):
            for ident in item:
                if isinstance(ident, str):
                    sink.append({"owner": this_owner, "path": path,
                                 "entry": {"item": ident}})
        group_refs = []
        if isinstance(node.get("group"), str):
            group_refs.append(node["group"])
        for key in ("items", "item_groups"):
            values = node.get(key)
            if isinstance(values, list):
                group_refs.extend(v for v in values if isinstance(v, str))
        for group_id in group_refs:
            inner = singleton_group_entry(groups, group_id, depth + 1, set())
            if inner is None:
                continue
            merged = {k: v for k, v in node.items()
                      if k not in ("group", "items", "item_groups")}
            merged.update(inner)
            outer_prob = node.get("prob", 100)
            inner_prob = inner.get("prob", 100)
            if isinstance(outer_prob, int) and isinstance(inner_prob, int):
                merged["prob"] = outer_prob * inner_prob / 100
            sink.append({"owner": this_owner, "path": path, "entry": reference_entry(merged)})
        items = node.get("items")
        if isinstance(items, list):
            for ident in items:
                if isinstance(ident, str):
                    sink.append({"owner": this_owner, "path": path,
                                 "entry": {"item": ident}})
                elif isinstance(ident, list) and ident and isinstance(ident[0], str):
                    entry = {"item": ident[0]}
                    if len(ident) > 1:
                        entry["prob"] = ident[1]
                    if len(ident) > 2:
                        entry["count"] = ident[2]
                    sink.append({"owner": this_owner, "path": path, "entry": entry})
        for key, value in node.items():
            if key in ("group", "item_groups"):
                continue
            iter_entries(value, f"{path}/{key}", this_owner, sink, groups, depth + 1)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            iter_entries(value, f"{path}[{index}]", owner, sink, groups, depth + 1)


def entry_key(entry):
    ignore = {"item", "//"}
    return json.dumps({k: entry[k] for k in sorted(entry) if k not in ignore},
                      sort_keys=True)


def collect_all_refs(contexts, ids):
    """collect refs for many ids in one pass over every context."""
    by_id = {ident: [] for ident in ids}
    for context_name, ctx in contexts:
        groups = build_groups(ctx)
        for path, data in ctx.docs:
            sink = []
            iter_entries(data, os.path.basename(path), None, sink, groups)
            for ref in sink:
                ident = ref["entry"].get("item")
                if ident in by_id:
                    ref["file"] = os.path.relpath(path, ctx.root)
                    ref["context"] = context_name
                    by_id[ident].append(ref)
    return by_id


def compare_refs(old_id, mapping, baseline_refs, fork_refs):
    """Check every baseline spawn entry has an equivalent fork spawn entry."""
    variant = mapping.get("variant")
    modifier = mapping.get("stack_modifier")
    problems = []
    expected = []
    for ref in baseline_refs:
        entry = dict(ref["entry"])
        entry["item"] = mapping["replace"]
        if variant:
            entry["variant"] = variant
        if modifier:
            entry["stack_modifier"] = modifier
        expected.append((entry_key(entry), (ref.get("context"), ref["owner"]), ref["file"]))
    actual = []
    for ref in fork_refs:
        entry = dict(ref["entry"])
        if entry.get("item") != mapping["replace"]:
            continue
        if variant and entry.get("variant") != variant:
            continue
        actual.append((entry_key(entry), (ref.get("context"), ref["owner"]), ref["file"]))
    expected_counts = {}
    for key, owner, path in expected:
        expected_counts.setdefault((key, owner), 0)
        expected_counts[(key, owner)] += 1
    actual_counts = {}
    for key, owner, path in actual:
        actual_counts.setdefault((key, owner), 0)
        actual_counts[(key, owner)] += 1
    for (key, owner), count in expected_counts.items():
        have = actual_counts.get((key, owner), 0)
        if have < count:
            problems.append({"owner": owner, "entry": json.loads(key),
                             "missing": count - have})
    for problem in problems:
        problem["mission"] = bool(problem["owner"] and problem["owner"][1] and
                                  problem["owner"][1][0] == "mission")
    return problems


def constant_charges(refs):
    values = set()
    for ref in refs:
        entry = ref["entry"]
        if isinstance(entry.get("charges"), int):
            values.add(entry["charges"])
        if isinstance(entry.get("charges-max"), int):
            values.add(entry["charges-max"])
        if isinstance(entry.get("count"), int) and "charges" not in entry:
            values.add(entry["count"])
    return sorted(values)


def spawn_capacity(new_def):
    for key in ("capacity", "max_charges"):
        if isinstance(new_def.get(key), int):
            return new_def[key]
    for section in ("magazine", "tool"):
        block = new_def.get(section)
        if isinstance(block, dict):
            for key in ("capacity", "max_charges"):
                if isinstance(block.get(key), int):
                    return block[key]
    return None


def magazine_acceptance(ctx):
    """tool/gun id -> set of magazine ids it accepts, including reloads_like expansion."""
    reloads = {}
    for ident in ctx.defs:
        raw = ctx.raw(ident) or {}
        target = raw.get("reloads_like")
        if isinstance(target, str):
            reloads[ident] = target
    result = {}
    for ident in ctx.defs:
        raw = ctx.raw(ident) or {}
        magazines = raw.get("magazines")
        if not isinstance(magazines, list):
            continue
        accepted = set()
        for entry in magazines:
            if isinstance(entry, list) and len(entry) >= 2 and isinstance(entry[1], list):
                accepted.update(v for v in entry[1] if isinstance(v, str))
        expanded = set(accepted)
        changed = True
        while changed:
            changed = False
            for mag, target in reloads.items():
                if target in expanded and mag not in expanded:
                    expanded.add(mag)
                    changed = True
        result[ident] = expanded
    return result


def uncraft_of(ctx, ident):
    entries = ctx.uncraft.get(ident)
    if not entries:
        return None
    merged = {}
    for entry in entries:
        merged = fold_data.apply_inheritance(merged, entry)
    components = []
    for group in merged.get("components", []) or []:
        if isinstance(group, list) and group:
            alternative = group[0]
            if isinstance(alternative, list) and len(alternative) >= 2:
                components.append([alternative[0], alternative[1]])
    return {
        "components": sorted(components),
        "time": fold_data.normalise_value("time", merged.get("time", 0)),
        "qualities": sorted(
            [[q.get("id"), q.get("level", 1)] for q in merged.get("qualities", [])
             if isinstance(q, dict)]),
        "skill": merged.get("skill_used") or merged.get("skill"),
        "difficulty": merged.get("difficulty", 0),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mainline", required=True)
    parser.add_argument("--fork", required=True)
    parser.add_argument("--requests", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--markdown")
    args = parser.parse_args()

    core_old = collect_context(args.mainline, "data/json", "core")
    core_new = collect_context(args.fork, "data/json", "core")
    variants = fold_data.variant_map(args.fork)
    modifiers = fold_data.load_modifiers(args.fork)

    all_new_migrations = {}
    for context in [core_new]:
        all_new_migrations.update(context.migrations)

    mod_contexts = []
    mods_root = os.path.join(args.mainline, "data/mods")
    for mod in sorted(os.listdir(mods_root)):
        old_dir = os.path.join(mods_root, mod)
        new_dir = os.path.join(args.fork, "data/mods", mod)
        if not os.path.isdir(old_dir) or not os.path.isdir(new_dir):
            continue
        old_ctx = collect_context(args.mainline, f"data/mods/{mod}", mod)
        new_ctx = collect_context(args.fork, f"data/mods/{mod}", mod)
        mod_contexts.append((mod, old_ctx, new_ctx))
        all_new_migrations.update(new_ctx.migrations)

    removed = []
    for ident in sorted(core_old.defs):
        if ident not in core_new.defs:
            removed.append({"id": ident, "context": "core", "type": core_old.types.get(ident)})
    for mod, old_ctx, new_ctx in mod_contexts:
        for ident in sorted(old_ctx.defs):
            if ident not in new_ctx.defs:
                removed.append({"id": ident, "context": mod, "type": old_ctx.types.get(ident)})

    requests = []
    report = {"missing_migrations": [], "missing_targets": [], "records": [],
              "reference_problems": [], "request_count": 0}

    contexts = {("core"): (core_old, core_new)}
    for mod, old_ctx, new_ctx in mod_contexts:
        contexts[mod] = (old_ctx, new_ctx)

    reload_problems = []
    magazine_types = {record["id"] for record in removed
                      if record["type"] in ("MAGAZINE", "BATTERY")}
    for context_name, old_ctx, new_ctx in ([("core", core_old, core_new)] +
                                          [(m, o, n) for m, o, n in mod_contexts]):
        old_accept = magazine_acceptance(old_ctx)
        new_accept = magazine_acceptance(new_ctx)
        for tool, accepted in old_accept.items():
            lost = sorted(ident for ident in accepted & magazine_types
                          if ident in all_new_migrations)
            if not lost or tool not in new_accept:
                continue
            replacement_set = new_accept[tool]
            for ident in lost:
                replacement = all_new_migrations[ident].get("replace")
                if replacement not in replacement_set:
                    reload_problems.append({
                        "context": context_name, "tool": tool,
                        "lost": ident, "replacement": replacement,
                    })
    report["reload_problems"] = reload_problems

    old_refs_by_id = collect_all_refs(
        [("core", core_old)] + [(mod, ctx) for mod, ctx, _ in mod_contexts],
        {record["id"] for record in removed})
    replacement_ids = {all_new_migrations[record["id"]]["replace"]
                       for record in removed if record["id"] in all_new_migrations}
    fork_refs_by_id = collect_all_refs(
        [("core", core_new)] + [(mod, ctx) for mod, _, ctx in mod_contexts],
        replacement_ids)

    for record in removed:
        ident = record["id"]
        old_ctx, new_ctx = contexts[record["context"]]
        migration = all_new_migrations.get(ident)
        if migration is None:
            report["missing_migrations"].append(ident)
            requests.append({"id": ident})
            continue
        replacement = migration.get("replace")
        if not (core_new.has(replacement) or new_ctx.has(replacement)):
            report["missing_targets"].append({"id": ident, "replace": replacement})
            continue
        target_ctx = new_ctx if new_ctx.has(replacement) else core_new
        variant = variants.get(migration.get("variant")) if migration.get("variant") else None
        active_modifiers = []
        if migration.get("stack_modifier"):
            if migration["stack_modifier"] in modifiers:
                active_modifiers = [modifiers[migration["stack_modifier"]]]
            else:
                report.setdefault("missing_modifiers", []).append(migration["stack_modifier"])
        old_def = normalise_def(old_ctx, ident)
        new_def = normalise_def(target_ctx, replacement, variant, active_modifiers)

        changes = diff_defs(old_def or {}, new_def or {})
        # Uncraft/disassembly: base recipe plus variant extras in the fork.
        old_uncraft = uncraft_of(old_ctx, ident)
        new_uncraft = uncraft_of(target_ctx, replacement)
        if old_uncraft or new_uncraft:
            if variant and variant.get("components"):
                base_components = list((new_uncraft or {}).get("components", []))
                base_components += [[c[0], c[1]] for c in variant["components"]]
                new_uncraft = dict(new_uncraft or {})
                new_uncraft["components"] = sorted(base_components)
            if old_uncraft != new_uncraft:
                changes.append({"field": "uncraft", "old": old_uncraft, "new": new_uncraft,
                                "severity": "BALANCE CHANGE"})

        # Item group / spawn references (core and every mod referencing the old id).
        old_refs = old_refs_by_id.get(ident, [])
        fork_refs = fork_refs_by_id.get(replacement, [])
        mapping = {"replace": replacement, "variant": migration.get("variant"),
                   "stack_modifier": migration.get("stack_modifier")}
        ref_problems = compare_refs(ident, mapping, old_refs, fork_refs)
        mission_problems = [p for p in ref_problems if p.get("mission")]
        spawn_problems = [p for p in ref_problems if not p.get("mission")]
        if spawn_problems:
            report["reference_problems"].append({"id": ident, "problems": spawn_problems})
        if mission_problems:
            report.setdefault("mission_identity_problems", []).append(
                {"id": ident, "problems": mission_problems})

        limit = spawn_capacity(new_def or {})
        if limit:
            for ref in old_refs:
                entry = ref["entry"]
                for field in ("charges", "charges-max", "count"):
                    value = entry.get(field)
                    if isinstance(value, int) and value > limit:
                        report.setdefault("capacity_clamps", []).append({
                            "id": ident, "replacement": replacement,
                            "field": field, "requested": value,
                            "replacement_capacity": limit,
                            "owner": ref.get("owner"), "file": ref.get("file"),
                        })

        for charge in [None] + constant_charges(old_refs):
            request = {"id": ident}
            if charge is not None:
                request["charges"] = charge
            requests.append(request)

        record.update({
            "family": fold_data.family_of(ident, replacement),
            "replacement": replacement,
            "variant": migration.get("variant"),
            "stack_modifier": migration.get("stack_modifier"),
            "changes": changes,
        })
        report["records"].append(record)

    report["request_count"] = len(requests)
    report["removed_count"] = len(removed)
    report["contexts"] = ["core"] + [mod for mod, _, _ in mod_contexts]

    with open(args.requests, "w", encoding="utf-8") as handle:
        json.dump(requests, handle, indent=1, sort_keys=False)
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True)

    if args.markdown:
        lines = ["| family | old id | replacement | variant | severity | field | mainline | fork |",
                 "|---|---|---|---|---|---|---|---|"]
        for record in sorted(report["records"],
                             key=lambda r: (r["family"], r["id"])):
            for change in record["changes"]:
                lines.append(
                    f"| {record['family']} | `{record['id']}` | `{record['replacement']}` | "
                    f"`{record.get('variant') or ''}` | {change['severity']} | "
                    f"`{change['field']}` | `{json.dumps(change['old'])[:160]}` | "
                    f"`{json.dumps(change['new'])[:160]}` |")
        with open(args.markdown, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    # Human-readable summary.
    families = {}
    for record in report["records"]:
        families.setdefault(record["family"], []).append(record)
    print(f"removed ids: {len(removed)}  requests: {len(requests)}  "
          f"migrations missing: {len(report['missing_migrations'])}  "
          f"targets missing: {len(report['missing_targets'])}")
    print(f"{'family':<14} {'ids':>4} {'with diffs':>10} {'breaks play':>11}")
    for family, records in sorted(families.items()):
        with_diffs = sum(1 for r in records if r["changes"])
        breaks = sum(1 for r in records
                     if any(c["severity"] == "BREAKS PLAY" for c in r["changes"]))
        print(f"{family:<14} {len(records):>4} {with_diffs:>10} {breaks:>11}")
    if report["reference_problems"]:
        print(f"reference problems: {len(report['reference_problems'])} ids")


if __name__ == "__main__":
    main()
