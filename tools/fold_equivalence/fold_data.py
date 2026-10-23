#!/usr/bin/env python3
"""Shared JSON loading, copy-from resolution and field normalisation for fold checks.

This is a static approximation of the game loaders: it resolves copy-from, extend,
delete, relative and proportional the way generic_factory/assign do for the fields
that the fold checks compare.  Runtime truth still comes from `--dump-stats FOLDED`.
"""

import copy
import json
import os
import re
import sys

MASS_UNITS = {"mg": 0.001, "g": 1.0, "kg": 1000.0}
VOLUME_UNITS = {"ml": 1.0, "l": 1000.0, "L": 1000.0}
MONEY_UNITS = {"cent": 1.0, "USD": 100.0, "kUSD": 100000.0}
TIME_UNITS = {"turn": 1.0 / 100.0, "turns": 1.0 / 100.0, "s": 1.0 / 60.0,
              "m": 1.0, "h": 60.0, "d": 1440.0}

UNIT_FIELDS_LIKE = {**MASS_UNITS, **VOLUME_UNITS, **MONEY_UNITS, **TIME_UNITS}

PRESENTATION_KEYS = {
    "name", "description", "color", "symbol", "looks_like", "ascii_picture",
    "snippet_category", "//", "copy-from", "abstract", "id", "extend", "delete",
    "relative", "proportional", "conditional_names",
}

# Field -> unit table used by the normaliser.
UNIT_FIELDS = {
    "weight": MASS_UNITS, "integral_weight": MASS_UNITS,
    "weight_capacity_bonus": MASS_UNITS,
    "volume": VOLUME_UNITS, "integral_volume": VOLUME_UNITS,
    "storage": VOLUME_UNITS, "contains": VOLUME_UNITS, "barrel_volume": VOLUME_UNITS,
    "price": MONEY_UNITS, "price_postapoc": MONEY_UNITS,
    "time": TIME_UNITS, "spoils": TIME_UNITS,
}

LIST_FIELDS = {
    "material", "materials", "flags", "techniques", "ammo_effects", "effects",
    "covers", "valid_mods", "petfood", "use_action",
}


def iter_json_files(root, subdir):
    base = os.path.join(root, subdir)
    for dirpath, _dirs, files in os.walk(base):
        for name in sorted(files):
            if name.endswith(".json"):
                yield os.path.join(dirpath, name)


def load_documents(root, subdir):
    docs = []
    for path in iter_json_files(root, subdir):
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as err:  # noqa: BLE001 - report the file, keep going
            print(f"fold_data: cannot parse {path}: {err}", file=sys.stderr)
            continue
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list):
            docs.append((path, data))
    return docs


ITEM_TYPES = {
    "AMMO", "GUN", "ARMOR", "PET_ARMOR", "TOOL", "TOOLMOD", "TOOL_ARMOR", "BOOK",
    "COMESTIBLE", "CONTAINER", "ENGINE", "WHEEL", "FUEL", "GUNMOD", "MAGAZINE",
    "BATTERY", "GENERIC", "BIONIC_ITEM",
}


class Context:
    """One load context: a JSON tree (core or a mod)."""

    def __init__(self, root, subdir, label):
        self.root = root
        self.subdir = subdir
        self.label = label
        self.defs = {}        # id -> list of objects in load order
        self.types = {}       # id -> type
        self.abstracts = {}   # id -> object
        self.migrations = {}  # id -> migration object
        self.docs = load_documents(root, subdir)
        self.uncraft = {}     # result id -> list of uncraft objects
        self._resolved = {}
        for _path, data in self.docs:
            for obj in data:
                if not isinstance(obj, dict):
                    continue
                if obj.get("type") == "MIGRATION":
                    ids = obj.get("id")
                    if isinstance(ids, str):
                        ids = [ids]
                    for ident in ids or []:
                        self.migrations[ident] = obj
                    continue
                if obj.get("type") == "uncraft":
                    result = obj.get("result")
                    if isinstance(result, str):
                        self.uncraft.setdefault(result, []).append(obj)
                    continue
                if obj.get("type") not in ITEM_TYPES:
                    continue
                if "abstract" in obj:
                    self.abstracts[obj["abstract"]] = obj
                    continue
                ids = obj.get("id")
                if isinstance(ids, str):
                    ids = [ids]
                for ident in ids or []:
                    self.defs.setdefault(ident, []).append(obj)
                    if "type" in obj:
                        self.types[ident] = obj["type"]

    def has(self, ident):
        return ident in self.defs or ident in self.abstracts

    def raw(self, ident):
        if ident in self.abstracts:
            return self.abstracts[ident]
        entries = self.defs.get(ident)
        if not entries:
            return None
        merged = {}
        for obj in entries:
            merged = merge_objects(merged, obj)
        return merged

    def resolve(self, ident, _seen=None):
        if ident in self._resolved:
            return copy.deepcopy(self._resolved[ident])
        if _seen is None:
            _seen = set()
        if ident in _seen:
            return {"__cycle__": ident}
        _seen.add(ident)
        obj = self.raw(ident)
        if obj is None:
            return None
        parent_id = obj.get("copy-from")
        if isinstance(parent_id, str) and not parent_id.startswith("no_copy"):
            parent = self.resolve(parent_id, _seen)
            if parent is None:
                parent = {}
        else:
            parent = {}
        out = apply_inheritance(parent, obj)
        self._resolved[ident] = out
        return copy.deepcopy(out)


def parse_unit_value(value, units):
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return value
    text = value.strip()
    total = 0.0
    matched = False
    for number, unit in re.findall(r"(-?[0-9.]+)\s*([A-Za-z]+)", text):
        if unit in units:
            total += float(number) * units[unit]
            matched = True
    if not matched:
        return value
    return total


def _numeric(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?[0-9.]+", value)
        if match:
            return float(match.group(0))
    return None


def multiply_value(value, factor):
    factor = _numeric(factor)
    if factor is None:
        return value
    if isinstance(value, (int, float)):
        return value * factor
    if isinstance(value, str):
        match = re.match(r"^\s*(-?[0-9.]+)\s*([A-Za-z]+)\s*$", value)
        if match:
            number = float(match.group(1)) * factor
            if number == int(number):
                return f"{int(number)} {match.group(2)}"
            return f"{number} {match.group(2)}"
    return value


def add_value(value, delta):
    raw_delta = delta
    delta = _numeric(delta)
    if delta is None:
        return value
    if isinstance(value, (int, float)):
        return value + delta
    if isinstance(raw_delta, str) and isinstance(value, str):
        match = re.match(r"^\s*(-?[0-9.]+)\s*([A-Za-z]+)\s*$", raw_delta)
        if match:
            base = parse_unit_value(value, UNIT_FIELDS_LIKE)
            if isinstance(base, float):
                number = base + delta
                if number == int(number):
                    return f"{int(number)} {match.group(2)}"
                return f"{number} {match.group(2)}"
    if isinstance(value, str):
        match = re.match(r"^\s*(-?[0-9.]+)\s*([A-Za-z]+)\s*$", value)
        if match:
            number = float(match.group(1)) + delta
            if number == int(number):
                return f"{int(number)} {match.group(2)}"
            return f"{number} {match.group(2)}"
    return value


def merge_damage(base, extra, proportional=False, relative=False):
    """Apply a damage object/array on top of another the way assign() does."""
    def units_of(value):
        if isinstance(value, dict):
            if "values" in value:
                return [dict(u) for u in value["values"]]
            return [dict(value)]
        if isinstance(value, list):
            return [dict(u) for u in value]
        return []

    out = units_of(base)
    for unit in units_of(extra):
        dtype = unit.get("damage_type") or unit.get("type") or "bullet"
        unit.setdefault("damage_type", dtype)
        existing = next((u for u in out if (u.get("damage_type") == dtype)), None)
        if proportional:
            if existing is None:
                continue
            if "amount" in unit:
                existing["amount"] = existing.get("amount", 0) * unit["amount"]
            if "armor_penetration" in unit:
                existing["armor_penetration"] = existing.get("armor_penetration", 0) * unit["armor_penetration"]
        elif relative:
            if existing is None:
                out.append(unit)
                continue
            for key in ("amount", "armor_penetration", "damage_multiplier"):
                if key in unit:
                    existing[key] = existing.get(key, 0) + unit[key]
        else:
            if existing is None:
                out.append(unit)
            else:
                existing.update(unit)
    return out


def apply_inheritance(parent, child):
    out = copy.deepcopy(parent)
    extend = child.get("extend") or {}
    delete = child.get("delete") or {}
    relative = child.get("relative") or {}
    proportional = child.get("proportional") or {}

    for key, value in child.items():
        if key in ("copy-from", "extend", "delete", "relative", "proportional"):
            continue
        if key == "damage" or key.startswith("damage"):
            out[key] = merge_damage(out.get(key), value)
        else:
            out[key] = copy.deepcopy(value)

    for key, extra in extend.items():
        base = out.get(key)
        if isinstance(extra, dict) and not isinstance(base, dict):
            continue
        if isinstance(base, dict):
            for subkey, subvalue in extra.items():
                if isinstance(subvalue, list) and isinstance(base.get(subkey), list):
                    base[subkey].extend(copy.deepcopy(subvalue))
                else:
                    base[subkey] = copy.deepcopy(subvalue)
        elif isinstance(base, list):
            base.extend(copy.deepcopy(extra))
        elif isinstance(extra, list):
            out[key] = copy.deepcopy(extra)
        elif isinstance(extra, dict):
            out.setdefault(key, {}).update(copy.deepcopy(extra))
        else:
            out[key] = copy.deepcopy(extra)

    for key, extra in delete.items():
        base = out.get(key)
        if isinstance(base, list):
            remove = extra if isinstance(extra, list) else [extra]
            out[key] = [item for item in base if item not in remove]
        elif isinstance(base, dict) and isinstance(extra, list):
            for entry in extra:
                base.pop(entry, None)
        else:
            out.pop(key, None)

    for key, delta in relative.items():
        if key not in out:
            continue
        if key.startswith("damage") or key == "damage":
            out[key] = merge_damage(out.get(key), delta, relative=True)
        else:
            out[key] = add_value(out.get(key), delta)

    for key, factor in proportional.items():
        if key not in out:
            continue
        if key.startswith("damage") or key == "damage":
            out[key] = merge_damage(out.get(key), factor, proportional=True)
        else:
            out[key] = multiply_value(out.get(key), factor)

    return out


def merge_objects(base, child):
    """Merge repeated same-type definitions the way the loaders do."""
    out = copy.deepcopy(base)
    out.update(copy.deepcopy(child))
    return out


def normalise_value(key, value):
    if value is None:
        return None
    if key in UNIT_FIELDS and isinstance(value, (str, int, float)):
        return parse_unit_value(value, UNIT_FIELDS[key])
    if key in LIST_FIELDS:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return sorted(str(v) for v in value)
    if key == "damage" or key.startswith("damage"):
        value = merge_damage(None, value) if not isinstance(value, list) else value
        units = []
        for unit in value or []:
            units.append({
                "type": unit.get("damage_type") or unit.get("type"),
                "amount": unit.get("amount", 0),
                "armor_penetration": unit.get("armor_penetration", 0),
            })
        return sorted(units, key=lambda u: str(u["type"]))
    if isinstance(value, dict):
        return {str(k): normalise_value(k, v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [normalise_value(key, v) for v in value]
    if isinstance(value, float) and value == int(value):
        return int(value)
    return value


def variant_map(root):
    variants = {}
    for _path, data in load_documents(root, "data/json"):
        for obj in data:
            if not isinstance(obj, dict) or obj.get("type") != "item_variants":
                continue
            base = obj.get("id")
            for variant in obj.get("variants", []):
                variants[variant.get("id")] = dict(variant, base=base,
                                                   cosmetic=obj.get("cosmetic", False))
    return variants


def load_modifiers(root):
    mods = {}
    for _path, data in load_documents(root, "data/json"):
        for obj in data:
            if isinstance(obj, dict) and obj.get("type") == "stack_modifier":
                mods[obj["id"]] = obj
    return mods


def family_of(old_id, replacement):
    if replacement in ("light_battery_cell", "medium_battery_cell", "heavy_battery_cell",
                       "light_atomic_battery_cell", "medium_atomic_battery_cell",
                       "heavy_atomic_battery_cell"):
        return "batteries"
    if old_id.startswith("bp_"):
        return "black powder"
    if replacement.startswith("jewelry_"):
        return "jewelry"
    if replacement == "paperback":
        return "books"
    if replacement in ("board_game", "tabletop_game"):
        return "games"
    if replacement == "mre_ration":
        return "MREs"
    if replacement in ("30gal_drum", "keg", "box_large", "jug_plastic", "bottle_plastic_small"):
        return "containers"
    return "others"


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
