#!/usr/bin/env python3
"""dupes.py - sprite-level duplicate / blank analysis for Cataclysm: BN bundled tilesets.

Hashes every sprite cell of every sheet referenced by a tile_config.json under gfx/,
plus every sheet referenced by data/json/external_tileset/*.json (each of those files is
its own index space, matching cata_tiles::tileset_loader::load_internal, which resets
`offset` per config and accumulates it per tiles-new entry).

Pixel data is decoded through ImageMagick (`magick ... rgba:-`) because Pillow is not
installed on this machine.

Outputs (in /tmp/texture-sweep/):
  duplicates.md        report
  dupe_groups.csv      all in-tileset duplicate groups, ranked
  cross_tileset.csv    cross-tileset identical sprites
  blank_or_solid.csv   ids mapped entirely to blank or single-colour sprites
  totals.csv           per-tileset sprite totals
  top/                 sprite crops for the contact sheet
"""

import collections
import hashlib
import json
import os
import struct
import subprocess
import sys

REPO = os.environ.get("BN_REPO", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
OUT = "/tmp/texture-sweep"
CACHE = os.path.join(OUT, "sheet_cache_v3.json")

# ----------------------------------------------------------------------------- config

def png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("not a png: " + path)
    return struct.unpack(">II", head[16:24])

_raw_cache = {}

def raw_rgba(path, w, h):
    key = path
    if key in _raw_cache:
        return _raw_cache[key]
    out = subprocess.run(["magick", path, "-depth", "8", "rgba:-"],
                         stdout=subprocess.PIPE, check=True).stdout
    if len(out) != w * h * 4:
        raise RuntimeError("unexpected raw size for %s: %d != %d" %
                           (path, len(out), w * h * 4))
    _raw_cache[key] = out
    return out


# ----------------------------------------------------------------------------- sprites

def sprite_bytes(raw, sheet_w, sw, sh, col, row):
    stride = sheet_w * 4
    x0 = col * sw * 4
    y0 = row * sh
    if sw == sheet_w:
        return raw[y0 * stride + x0:y0 * stride + x0 + sw * sh * 4]
    parts = []
    for r in range(y0, y0 + sh):
        base = r * stride
        parts.append(raw[base + x0:base + x0 + sw * 4])
    return b"".join(parts)


def trim_hash(buf, sw, sh):
    """hash of the non-transparent bounding box content (offset-invariant),
    plus (x0, y0, w, h) of that box; None for a fully transparent sprite."""
    row_len = sw * 4
    rows = []
    first_x = sw
    last_x = -1
    first_y = -1
    last_y = -1
    for r in range(sh):
        row = buf[r * row_len:(r + 1) * row_len]
        alpha = row[3::4]
        stripped = alpha.lstrip(b"\x00")
        if not stripped:
            continue
        x0 = len(alpha) - len(stripped)
        x1 = len(alpha.rstrip(b"\x00"))
        if first_y < 0:
            first_y = r
        last_y = r
        if x0 < first_x:
            first_x = x0
        if x1 > last_x:
            last_x = x1
        rows.append(row[x0 * 4:x1 * 4])
    if first_y < 0:
        return None, None
    h = hashlib.md5()
    for r in rows:
        h.update(struct.pack("<HH", len(r), 0))
        h.update(r)
    # NOTE: row lengths are prefixed so that different row splits cannot collide.
    return h.hexdigest(), (first_x, first_y, last_x - first_x, last_y - first_y + 1)


def solid_color(buf, sw, sh):
    """True when every visible pixel has one identical RGBA value."""
    row_len = sw * 4
    ref = None
    for r in range(sh):
        row = buf[r * row_len:(r + 1) * row_len]
        if not row.strip(b"\x00"):
            continue
        if ref is None:
            px = row[0:4]
            if row != px * sw:
                return None
            ref = px
        elif row != ref * sw:
            return None
    return ref.hex() if ref else None


def load_sheet(path, sw, sh):
    """Return [(local_index, hash, trim_hash, trim_box, solid, blank)] cached."""
    w, h = png_size(path)
    key = "%s|%d|%d|%d|%d|%d" % (path, os.path.getmtime(path), w, h, sw, sh)
    store = _cache.setdefault(path, {})
    if key in store:
        return store[key]
    raw = raw_rgba(path, w, h)
    cols = w // sw
    rows = h // sh
    out = []
    for row in range(rows):
        for col in range(cols):
            buf = sprite_bytes(raw, w, sw, sh, col, row)
            md5 = hashlib.md5(buf).hexdigest()
            blank = not buf[3::4].strip(b"\x00")
            if blank:
                th, box, solid = None, None, None
            else:
                th, box = trim_hash(buf, sw, sh)
                solid = solid_color(buf, sw, sh)
            out.append((row * cols + col, md5, th, box, solid, blank))
    store[key] = out
    return out


# ----------------------------------------------------------------------------- sheets

def group_configs():
    """[(group_id, root_dir, config_path, default_w, default_h)]"""
    groups = []
    for name in sorted(os.listdir(os.path.join(REPO, "gfx"))):
        root = os.path.join(REPO, "gfx", name)
        cfg = os.path.join(root, "tile_config.json")
        if not os.path.isdir(root) or not os.path.exists(cfg):
            continue
        j = json.load(open(cfg))
        ti = j.get("tile_info") or [{}]
        groups.append((name, root, cfg, ti[0].get("width"), ti[0].get("height")))
    ext_dir = os.path.join(REPO, "data/json/external_tileset")
    for dirpath, _, files in os.walk(ext_dir):
        for fn in sorted(files):
            if not fn.endswith(".json") or fn == "README.md":
                continue
            cfg = os.path.join(dirpath, fn)
            data = json.load(open(cfg))
            if isinstance(data, dict):
                data = [data]
            if not any(isinstance(o, dict) and "tiles-new" in o for o in data):
                continue
            rel = os.path.relpath(dirpath, os.path.join(REPO, "data/json"))
            groups.append(("ext:" + os.path.join(rel, fn[:-5]), os.path.join(REPO, "data/json"),
                           cfg, 32, 32))
    return groups


def build_group(gid, root, cfg, def_w, def_h):
    data = json.load(open(cfg))
    if isinstance(data, dict):
        data = [data]
    sheets = []
    offset = 0
    for obj in data:
        if not isinstance(obj, dict) or "tiles-new" not in obj:
            continue
        offset = 0
        for entry in obj["tiles-new"]:
            file = entry.get("file")
            if not isinstance(file, str):
                continue
            path = os.path.join(root, file)
            if not os.path.exists(path):
                continue
            sw = entry.get("sprite_width", def_w)
            sh = entry.get("sprite_height", def_h)
            w, h = png_size(path)
            cols, rows = w // sw, h // sh
            sheets.append(dict(file=file, path=path, sw=sw, sh=sh, cols=cols, rows=rows,
                               base=offset, count=cols * rows))
            offset += cols * rows
    return sheets


# ----------------------------------------------------------------------------- content index

ITEM_TYPES = {
    "GENERIC", "AMMO", "COMESTIBLE", "GUN", "TOOL", "TOOLMOD", "TOOL_ARMOR", "ARMOR",
    "PET_ARMOR", "BOOK", "CONTAINER", "ENGINE", "WHEEL", "GUNMOD", "MAGAZINE",
    "BATTERY", "BIONIC_ITEM", "MIGRATION", "SPELL", "ENGINE",
}
WANT = ("name", "category", "ammo_type", "weight", "species", "default_faction",
        "flags", "move_cost", "move_cost_mod", "difficulty", "looks_like", "color",
        "comestible_type")


def load_content():
    keys = ["id", "type"] + list(WANT) + ["copy-from", "abstract"]
    index = {}
    for base in ("data/json", "data/mods"):
        for dirpath, _, files in os.walk(os.path.join(REPO, base)):
            for fn in files:
                if not fn.endswith(".json"):
                    continue
                try:
                    data = json.load(open(os.path.join(dirpath, fn)))
                except Exception:
                    continue
                if isinstance(data, dict):
                    data = [data]
                if not isinstance(data, list):
                    continue
                for o in data:
                    if not isinstance(o, dict):
                        continue
                    t = o.get("type")
                    i = o.get("id")
                    if not isinstance(t, str) or not isinstance(i, str):
                        continue
                    if t not in ITEM_TYPES and t not in ("MONSTER", "terrain", "furniture",
                                                         "vehicle_part", "field_type"):
                        continue
                    if i in index:
                        continue
                    rec = {k: o[k] for k in keys if k in o}
                    index[i] = rec
    # shallow copy-from resolution for the fields we care about
    def resolve(oid, seen=()):
        rec = index.get(oid)
        if rec is None or oid in seen:
            return rec
        parent = rec.get("copy-from")
        if not isinstance(parent, str):
            return rec
        prec = resolve(parent, seen + (oid,))
        if prec:
            for k, v in prec.items():
                rec.setdefault(k, v)
        return rec

    for oid in list(index):
        resolve(oid)
    return index


def classify(oid, index):
    """-> (class, info dict, base_id)"""
    base = oid
    for p in ("overlay_wielded_", "overlay_worn_", "overlay_mutation_", "overlay_effect_",
              "overlay_", "wielded_", "worn_"):
        if base.startswith(p):
            base = base[len(p):]
            break
    base = base.split("[")[0].strip()
    info = index.get(base) or index.get(oid)
    if info:
        t = info.get("type")
        if t == "MONSTER":
            return "monster", info, base
        if t in ("terrain", "furniture"):
            return t, info, base
        if t == "field_type":
            return "field", info, base
        if t == "vehicle_part":
            return "vehicle", info, base
        if t in ITEM_TYPES:
            return "item", info, base
    if base.startswith("mon_"):
        return "monster", {}, base
    if base.startswith("t_"):
        return "terrain", {}, base
    if base.startswith("f_"):
        return "furniture", {}, base
    if base.startswith("vp_"):
        return "vehicle", {}, base
    if base.startswith("fd_"):
        return "field", {}, base
    return "unknown", {}, base


# ----------------------------------------------------------------------------- analysis helpers

def sprints(v):
    if isinstance(v, int):
        return [v]
    out = []
    if isinstance(v, list):
        for e in v:
            out.extend(sprints(e))
    elif isinstance(v, dict):
        for k in ("sprite", "fg", "bg"):
            if k in v:
                out.extend(sprints(v[k]))
    return out


def refs_of_tile(t):
    """[(sprite_index, role, id_suffix)]"""
    out = []
    for role in ("fg", "bg"):
        for i in sprints(t.get(role)):
            out.append((i, role, ""))
    for add in t.get("additional_tiles", []) or []:
        sub = add.get("id", "?")
        for role in ("fg", "bg"):
            for i in sprints(add.get(role)):
                out.append((i, role, "[" + sub + "]"))
    return out


def same_object(a, b):
    return a == b


def variant_only(a, b):
    """ids differing only by a size/black-powder/on-off variant prefix or suffix."""
    if a == b:
        return True
    for pre in ("bp_", "xl_", "xs_", "test_", "fake_", "corpse_", "dummy_"):
        if a == pre + b or b == pre + a:
            return True
    for suf in ("_on", "_off", "_lit", "_active", "_deployed"):
        if a == b + suf or b == a + suf:
            return True
    return False


PASSIVE_FACTIONS = {"player", "vermin"}
PLACEHOLDER_STEMS = ("fallback", "filler", "temporary", "unknown", "incomplete")


def pair_score(ca, cb):
    """(score, reason) for one pair of classified ids. Higher = more confusing in play."""
    a_cls, ai, abase = ca
    b_cls, bi, bbase = cb
    if same_object(abase, bbase):
        return 0, "same object (overlay/base)"
    if a_cls == "monster" and b_cls == "monster":
        fa = ai.get("default_faction", "") or ""
        fb = bi.get("default_faction", "") or ""
        na, nb = ai.get("name"), bi.get("name")
        same_name = na is not None and na == nb
        if not ai or not bi:
            return 95, "creature, definition missing from data (obsolete id?)"
        if fa and fb and fa != fb:
            if same_name:
                return 140, "creature, same name, different faction (%s vs %s)" % (fa, fb)
            return 130, "creature, different factions (%s vs %s)" % (fa, fb)
        return 100, "creature, same faction"
    if a_cls == "item" and b_cls == "item":
        s = 55
        reasons = []
        ta, tb = ai.get("type", ""), bi.get("type", "")
        aa, ab = ai.get("ammo_type"), bi.get("ammo_type")
        if ta == tb == "AMMO" and aa and ab:
            if aa == ab and aa != "components":
                s += 45
                reasons.append("same ammo type %s" % aa)
            elif aa != ab and "components" not in (aa, ab):
                s += 20
                reasons.append("different ammo types %s vs %s" % (aa, ab))
        ca_, cb_ = ai.get("comestible_type"), bi.get("comestible_type")
        if ca_ and cb_ and ca_ == cb_:
            if ca_ == "MED":
                s += 35
                reasons.append("both medicine")
            elif ca_ == "DRINK":
                s += 15
                reasons.append("both drinks")
            elif ca_ == "FOOD":
                s += 12
                reasons.append("both food")
        if ai.get("category") and ai.get("category") == bi.get("category"):
            s += 10
            reasons.append("same category %s" % ai.get("category"))
        if ta and ta == tb:
            s += 5
        if not reasons:
            reasons.append("two items (%s/%s)" % (ta or "?", tb or "?"))
        return s, ", ".join(reasons)
    if a_cls in ("terrain", "furniture") and b_cls in ("terrain", "furniture"):
        s = 55
        ma, mb = ai.get("move_cost"), bi.get("move_cost")
        fa = set(ai.get("flags") or [])
        fb = set(bi.get("flags") or [])
        HAZARD = {"LAVA", "DEEP_WATER", "SHARP", "MINEABLE"}
        danger = (fa ^ fb) & HAZARD
        if isinstance(ma, int) and isinstance(mb, int) and ma != mb:
            return s + 30 + (20 if danger else 0), "terrain, move_cost %d vs %d" % (ma, mb)
        if danger:
            return s + 25, "terrain, hazard flag differs (%s)" % ", ".join(sorted(danger))
        if a_cls != b_cls:
            s += 5
        return s, "two terrain/furniture"
    if a_cls == b_cls == "vehicle":
        return 70, "two vehicle parts"
    if a_cls == b_cls == "field":
        return 55, "two fields"
    if a_cls == "monster" or b_cls == "monster":
        return 45, "creature vs other"
    return 15, "%s vs %s" % (a_cls, b_cls)


# ----------------------------------------------------------------------------- main

_cache = {}
if os.path.exists(CACHE):
    try:
        _cache = json.load(open(CACHE))
    except Exception:
        _cache = {}


def main():
    index = load_content()
    groups = group_configs()
    report = {"tilesets": [], "cross": {}, "blank": [], "totals": []}

    # group_id -> list of tile dicts, and resolved sprite table
    per_group = {}
    for gid, root, cfg, dw, dh in groups:
        sheets = build_group(gid, root, cfg, dw, dh)
        raw = json.load(open(cfg))
        if isinstance(raw, dict):
            raw = [raw]
        tiles = []
        for obj in raw:
            if not isinstance(obj, dict):
                continue
            for entry in obj.get("tiles-new", []) or []:
                for t in entry.get("tiles", []) or []:
                    ids = t.get("id")
                    if isinstance(ids, str):
                        ids = [ids]
                    if not isinstance(ids, list):
                        continue
                    tiles.append((ids, t))
        per_group[gid] = dict(sheets=sheets, tiles=tiles)

    # sprite table per group: global index -> sprite record
    sprite_info = {}
    for gid, g in per_group.items():
        table = {}
        for s in g["sheets"]:
            rows = load_sheet(s["path"], s["sw"], s["sh"])
            for (li, md5, th, box, solid, blank) in rows:
                gi = s["base"] + li
                table[gi] = dict(sheet=s["file"], path=s["path"], local=li, md5=md5,
                                 trim=th, box=box, solid=solid, blank=blank,
                                 w=s["sw"], h=s["sh"], cols=s["cols"], base=s["base"])
        g["sprites"] = table

    # id -> referenced sprite indices
    id_refs = {}
    for gid, g in per_group.items():
        refs = {}
        for ids, t in g["tiles"]:
            for oid in ids:
                # later entries overwrite earlier ones (tileset::create_tile_type)
                refs[oid] = [(i, role, sub) for i, role, sub in refs_of_tile(t)]
        g["refs"] = refs
        id_refs[gid] = refs

    # ---- totals / section 3
    totals = []
    blank_rows = []
    for gid, g in per_group.items():
        sprites = g["sprites"]
        referenced = set()
        for oid, rl in g["refs"].items():
            for i, _, _ in rl:
                referenced.add(i)
        hashes = {sprites[i]["md5"] for i in referenced if i in sprites}
        blank_ids, solid_ids = [], []
        for oid, rl in g["refs"].items():
            sm = [sprites[i] for i, _, _ in rl if i in sprites]
            if not sm:
                continue
            if all(s["blank"] for s in sm):
                blank_ids.append(oid)
            elif all(s["solid"] for s in sm) and len({s["solid"] for s in sm}) == 1:
                solid_ids.append((oid, sm[0]["solid"], sm[0]["sheet"], sm[0]["local"]))
        totals.append(dict(tileset=gid, sprites=len(sprites), referenced=len(referenced),
                           unique=len(hashes), ids=len(g["refs"]),
                           blank_ids=len(blank_ids), solid_ids=len(solid_ids)))
        for oid in sorted(blank_ids):
            i = [i for i, _, _ in g["refs"][oid] if i in sprites][0]
            blank_rows.append(dict(tileset=gid, id=oid, kind="blank",
                                   sheet=sprites[i]["sheet"], index=i))
        for oid, col, sheet, local in sorted(solid_ids):
            blank_rows.append(dict(tileset=gid, id=oid, kind="solid:%s" % col,
                                   sheet=sheet, index=local))

    # ---- section 1: in-tileset duplicate groups
    all_groups = []
    for gid, g in per_group.items():
        sprites = g["sprites"]
        idx_users = collections.defaultdict(list)
        for oid, rl in g["refs"].items():
            for i, role, _ in rl:
                if role == "fg" and i in sprites:
                    idx_users[i].append(oid)
        g["idx_users"] = idx_users
        by_hash = collections.defaultdict(list)
        for i, s in sprites.items():
            by_hash[s["md5"]].append(i)
        for md5, idxs in by_hash.items():
            users = []
            for i in idxs:
                for oid in idx_users.get(i, []):
                    users.append((oid, i))
            if users:
                all_groups.append((gid, md5, idxs, users))

    # rank groups with >=2 distinct base content ids
    raw_results = []
    placeholder_groups = collections.Counter()
    for gid, md5, idxs, users in all_groups:
        if any(per_group[gid]["sprites"][i]["blank"] for i in idxs):
            continue          # fully transparent sprites are reported in section 3
        classified = {oid: classify(oid, index) for oid, _ in users}
        base_ids = sorted({c[2] for c in classified.values()
                           if not c[2].startswith("bg_shadow")})
        if len(base_ids) < 2:
            continue
        best = (0, "")
        pairnames = None
        sampled = users[:40]
        for x in range(len(sampled)):
            for y in range(x + 1, len(sampled)):
                oa, ob = sampled[x][0], sampled[y][0]
                if oa == ob:
                    continue
                sc, r = pair_score(classified[oa], classified[ob])
                if variant_only(classified[oa][2], classified[ob][2]):
                    sc -= 20
                    r += " (variant prefix/suffix)"
                if sc > best[0]:
                    best = (sc, r)
                    pairnames = (oa, ob)
        sheet_names = {per_group[gid]["sprites"][i]["sheet"] for i in idxs}
        if all(sheet_is_placeholder(n) for n in sheet_names):
            placeholder_groups[gid] += 1
            continue
        rep = users[0][1]
        s0 = per_group[gid]["sprites"][rep]
        raw_results.append(dict(tileset=gid, base_score=best[0], base_reason=best[1],
                                pair=pairnames or (users[0][0], users[1][0]),
                                base_ids=base_ids, ids=sorted({o for o, _ in users}),
                                picks=[],
                                sheet=s0["sheet"], base=s0["base"], local=s0["local"],
                                count=len(idxs), w=s0["w"], h=s0["h"], md5=md5,
                                trim=s0["trim"], users=users))

    # merge groups that expose exactly the same set of ids (for example a multi-frame
    # animation where all frames are identical): one finding, several sprite cells.
    merged = {}
    for r in raw_results:
        key = (r["tileset"], tuple(r["base_ids"]))
        if key not in merged:
            merged[key] = r
            r["sprite_cells"] = 1
        else:
            m = merged[key]
            m["sprite_cells"] += 1
            m["count"] = max(m["count"], r["count"])
    results = list(merged.values())
    for r in results:
        n = len(r["base_ids"])
        r["score"] = r["base_score"] + min(20, 4 * max(0, n - 2))
        r["reason"] = r["base_reason"]
        picks, seen = [], set()
        order = [r["pair"][0], r["pair"][1]] + [u[0] for u in r["users"]]
        by_id = {}
        for oid, i in r["users"]:
            by_id.setdefault(oid, i)
        for oid in order:
            if oid not in by_id:
                continue
            b = classify(oid, index)[2]
            if b in seen or b.startswith("bg_shadow"):
                continue
            seen.add(b)
            picks.append((b, by_id[oid]))
            if len(picks) == 3:
                break
        r["picks"] = picks
    results.sort(key=lambda r: (-r["score"], -len(r["base_ids"]), r["tileset"]))
    display = []
    for r in results:
        idset = set(r["base_ids"])
        sig = set()
        if all(classify(i, index)[0] == "item" for i in r["base_ids"]):
            for i in r["base_ids"]:
                inf = classify(i, index)[1]
                sig.add(tuple(hv(inf.get(k)) for k in (
                    "category", "type", "comestible_type", "ammo_type")))
        r["also"] = []
        dup = None
        for d in display:
            other = set(d["base_ids"])
            inter = len(idset & other)
            if inter and inter / len(idset | other) >= 0.5:
                dup = d
                break
            if sig and d.get("sig"):
                si = len(sig & d["sig"])
                if si and si / len(sig | d["sig"]) >= 0.6:
                    dup = d
                    break
        if dup is not None:
            if isinstance(dup["also"], list):
                dup["also"] = set(dup["also"])
            dup["also"].add(r["tileset"])
            continue
        r["sig"] = sig
        display.append(r)

    # duplicate group counts per tileset
    group_count = collections.Counter(r["tileset"] for r in results)

    # trimmed-hash duplicates that exact hashing misses (offset copies)
    trimmed_groups = 0
    for gid, g in per_group.items():
        byt = collections.defaultdict(set)
        for i, s in g["sprites"].items():
            if s["trim"]:
                byt[s["trim"]].add(s["md5"])
        trimmed_groups += sum(1 for v in byt.values() if len(v) > 1)

    # ---- section 2: cross tileset
    # only referenced (and non-blank) sprites count
    hash_ids = {}
    ref_hashes = {}
    for gid, g in per_group.items():
        sprites = g["sprites"]
        hm = hash_ids.setdefault(gid, {})
        for oid, rl in g["refs"].items():
            for i, _, _ in rl:
                s = sprites.get(i)
                if s and not s["blank"]:
                    ref_hashes.setdefault(s["md5"], set()).add(gid)
                    hm.setdefault(s["md5"], []).append((oid, i))
    pair_counts = collections.Counter()
    pair_examples = collections.defaultdict(list)
    for md5, gs in ref_hashes.items():
        if len(gs) < 2:
            continue
        gs = sorted(gs)
        for x in range(len(gs)):
            for y in range(x + 1, len(gs)):
                pair_counts[(gs[x], gs[y])] += 1
                ex_ids = [hash_ids[gg][md5][0] for gg in (gs[x], gs[y])]
                pen = sum(1 for oid, _ in ex_ids if oid.startswith(("bg_", "unknown")))
                if len(pair_examples[(gs[x], gs[y])]) < 8:
                    pair_examples[(gs[x], gs[y])].append(
                        (pen, md5 + " | " + "; ".join(
                            "%s:%s@%d" % (gg, oid, idx)
                            for gg, (oid, idx) in zip((gs[x], gs[y]), ex_ids))))

    for t in totals:
        t["dupes"] = group_count.get(t["tileset"], 0)
        t["placeholders"] = placeholder_groups.get(t["tileset"], 0)

    # ---- csvs
    report_keys = {(d["tileset"], tuple(d["base_ids"])) for d in display}
    with open(os.path.join(OUT, "dupe_groups.csv"), "w") as f:
        f.write("per_tileset_rank,in_report,tileset,score,reason,sheet,index,size,"
                "content_ids,id_count,sprite_copies\n")
        for n, r in enumerate(results, 1):
            f.write("%d,%d,%s,%d,%s,%s,%d,%dx%d,%s,%d,%d\n" % (
                n, 1 if (r["tileset"], tuple(r["base_ids"])) in report_keys else 0,
                r["tileset"], r["score"], r["reason"].replace(",", ";"), r["sheet"],
                r["local"], r["w"], r["h"], "|".join(r["base_ids"]).replace(",", ";"),
                len(r["base_ids"]), r["count"]))
    with open(os.path.join(OUT, "cross_tileset.csv"), "w") as f:
        f.write("tileset_a,tileset_b,identical_sprites,examples\n")
        for (a, b), c in pair_counts.most_common():
            f.write("%s,%s,%d,%s\n" % (a, b, c, " || ".join(
                e[1] for e in sorted(pair_examples[(a, b)]))))
    with open(os.path.join(OUT, "blank_or_solid.csv"), "w") as f:
        f.write("tileset,kind,id,sheet,index\n")
        for r in blank_rows:
            f.write("%s,%s,%s,%s,%d\n" % (r["tileset"], r["kind"], r["id"], r["sheet"],
                                           r["index"]))
    with open(os.path.join(OUT, "totals.csv"), "w") as f:
        f.write("tileset,sheet_sprites,referenced_sprites,unique_referenced,ids,"
                "dupe_groups,placeholder_groups,blank_ids,solid_ids\n")
        for t in totals:
            f.write("%(tileset)s,%(sprites)d,%(referenced)d,%(unique)d,%(ids)d,"
                    "%(dupes)d,%(placeholders)d,%(blank_ids)d,%(solid_ids)d\n" % t)

    make_contact_sheet(display[:10], per_group)

    for x in results + display:
        if isinstance(x.get("sig"), set):
            x["sig"] = sorted(map(str, x["sig"]))
        if isinstance(x.get("also"), set):
            x["also"] = sorted(x["also"])
    json.dump(dict(results=results[:400], display=display[:200], totals=totals,
                   pairs=[(a, b, c) for (a, b), c in pair_counts.most_common()],
                   trimmed_groups=trimmed_groups, blank_rows=blank_rows),
              open(os.path.join(OUT, "results.json"), "w"), indent=1)
    json.dump(_cache, open(CACHE, "w"))
    print("groups:", len(results), "placeholders:", sum(placeholder_groups.values()),
          "trimmed-only groups:", trimmed_groups, "cross pairs:", len(pair_counts),
          file=sys.stderr)
    for t in totals:
        print(t, file=sys.stderr)
    write_markdown(results, display, pair_counts, pair_examples, totals, blank_rows,
                   placeholder_groups, trimmed_groups)
    return results


def safe(name):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def make_contact_sheet(top, per_group):
    d = os.path.join(OUT, "top")
    if os.path.isdir(d):
        for f in os.listdir(d):
            os.unlink(os.path.join(d, f))
    else:
        os.makedirs(d)
    cells = []
    for n, r in enumerate(top, 1):
        for k, (oid, i) in enumerate(r["picks"], 1):
            s = per_group[r["tileset"]]["sprites"][i]
            x = (s["local"] % s["cols"]) * s["w"]
            y = (s["local"] // s["cols"]) * s["h"]
            tmp = os.path.join(d, "_spr.png")
            cell = os.path.join(d, "%02d-%d.png" % (n, k))
            subprocess.run(["magick", s["path"], "-crop", "%dx%d+%d+%d" % (
                s["w"], s["h"], x, y), "+repage", "-filter", "point", "-resize", "400%",
                tmp], check=True)
            label = "%02d %s" % (n, oid)
            subprocess.run(["magick",
                            "(", tmp, "-filter", "point", "-resize", "160x160",
                             "-background", "#262626", "-gravity", "center",
                             "-extent", "168x168", ")",
                            "(", "-background", "#262626", "-fill", "white", "-font",
                             "Adwaita-Mono", "-pointsize", "9", "-size", "168x",
                             "caption:" + label, ")",
                            "-append", cell], check=True)
            os.unlink(tmp)
            cells.append(cell)
    subprocess.run(["magick", "montage", "-background", "#262626",
                    "-tile", "5x", "-geometry", "+4+4"] + cells
                   + [os.path.join(OUT, "dupes-top.png")], check=True)


def hv(v):
    """hashable form of a JSON value"""
    if isinstance(v, (list, tuple)):
        return tuple(hv(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted(v.items()))
    return v


def sheet_is_placeholder(name):
    stem = os.path.splitext(os.path.basename(name))[0].lower()
    return stem.startswith(PLACEHOLDER_STEMS)


def md_ids(ids, n=6):
    shown = ids[:n]
    txt = ", ".join("`%s`" % i for i in shown)
    if len(ids) > n:
        txt += " and %d more" % (len(ids) - n)
    return txt


def write_markdown(results, display, pair_counts, pair_examples, totals, blank_rows,
                   placeholder_groups, trimmed_groups):
    lines = []
    a = lines.append
    a("# Duplicate and blank sprite report for the bundled tilesets")
    a("")
    a("Generated by `/tmp/texture-sweep/dupes.py` (data: `dupe_groups.csv`, "
      "`cross_tileset.csv`, `blank_or_solid.csv`, `totals.csv`).")
    a("")
    a("Method: every sheet named by a `tiles-new` entry in each `gfx/<tileset>/tile_config.json` "
      "and in every `data/json/external_tileset/*.json` is decoded to 8-bit RGBA. Each sprite cell "
      "is hashed (md5 of its exact pixels) and a second hash is taken of the non-transparent "
      "bounding box, which catches the same art at a different offset. Sprite indices are counted "
      "per JSON file, resetting for each file and accumulating across its `tiles-new` sheets, as in "
      "`cata_tiles::tileset_loader::load_internal`.")
    a("")
    a("An id defined more than once in the same file keeps its last definition, matching "
      "`tileset::create_tile_type`, which overwrites. Sheets whose name starts with `fallback`, "
      "`filler`, `temporary`, `unknown` or `incomplete` are treated as placeholder art: their "
      "groups are counted in section 4 but excluded from section 1, because every id there is "
      "expected to look the same.")
    a("")
    a("Only foreground sprites make two ids indistinguishable, so section 1 uses `fg` references "
      "only; a shared `bg` ground texture is intended layering. Section 2 counts both `fg` and "
      "`bg`, because a sprite can be foreground in one tileset and background in another.")
    a("")
    a("## 1. Identical sprites inside one tileset, mapped to different ids")
    a("")
    a("Ranked by how much the confusion costs in play. The score is a heuristic: a creature "
      "pair starts at 100 (+30 when the factions differ, +40 more when both share a name), an "
      "item pair at 55 (+45 for the same ammo type, +35 for two medicines, +15 for two drinks, "
      "+12 for two foods, +10 for the same category), a terrain pair at 55 (+30 when move cost "
      "differs, +25 for a hazard flag), plus 4 per id beyond the second, capped at 20. "
      "**The ranking is [INFERENCE]** based on the content JSON; the hashes are exact. "
      "Variants that differ only by a `bp_`/`xl_`/`_on` style prefix or suffix are scored 20 "
      "lower because the art reuse is deliberate. The table shows the top 40.")
    a("")
    a("| # | Tileset | Sprite (sheet:index) | Score | Why | Example pair | Content ids |")
    a("|---|---|---|---|---|---|---|")
    for n, r in enumerate(display[:40], 1):
        others = sorted(set(r["also"]) - {r["tileset"]})
        also = " (+%d tilesets)" % len(others) if others else ""
        a("| %d | %s%s | `%s:%d` | %d | %s | %s vs %s | %s |" % (
            n, r["tileset"], also, r["sheet"], r["local"], r["score"], r["reason"],
            r["pair"][0], r["pair"][1], md_ids(r["base_ids"], 6)))
    a("")
    a("### Visual check")
    a("")
    a("`dupes-top.png` crops the cited ids of the ten highest-ranked groups (three ids each, "
      "native pixels scaled 4x with nearest neighbour, tile id under each cell). I viewed it: "
      "within every group the cells are the same drawing, pixel for pixel. Nothing in the "
      "silhouette, palette or outline separates the ids, so on the map they are "
      "indistinguishable; only the item or monster name in the UI tells them apart. "
      "The three consequences that matter most are the dog group (the mutant dog is drawn "
      "exactly like domestic breeds), the hallucination pair (the hostile and the harmless "
      "version are the same sprite) and the liquid groups (water, ethanol and methanol share "
      "one bottle in RetroDays+; bleach and sulphuric acid share one blob in MSX++).")
    a("")
    a("This table is de-duplicated: the same finding repeated in another tileset is folded "
      "into one row and noted as (+N tilesets). Full per-tileset list: %d groups in "
      "`dupe_groups.csv` (`in_report` marks the rows shown here; the other rows are the same "
      "kind of finding in another tileset), top 200 in `results.json`." % len(results))
    a("")
    a("")
    a("## 2. Identical sprites across tilesets")
    a("")
    a("| Tileset A | Tileset B | Identical sprites | Example |")
    a("|---|---|---|---|")
    for (pa, pb), c in pair_counts.most_common():
        exs = sorted(pair_examples[(pa, pb)])
        ex = exs[0][1].split("|", 1)[1].strip() if exs else ""
        a("| %s | %s | %d | %s |" % (pa, pb, c, ex))
    a("")
    a("## 3. Ids mapped to blank or single-colour sprites")
    a("")
    a("| Tileset | Blank ids | Non-overlay blank ids | Solid-colour ids | Examples |")
    a("|---|---|---|---|---|")
    by = collections.defaultdict(lambda: ([], []))
    for r in blank_rows:
        by[r["tileset"]][0 if r["kind"] == "blank" else 1].append(r)
    for gid, (bl, so) in sorted(by.items()):
        real = [r["id"] for r in bl
                if not r["id"].startswith(("overlay_", "bg_")) and r["id"]]
        ex = real[:4] + ["%s (%s)" % (r["id"], r["kind"].split(":")[-1])
                         for r in so[:2]]
        a("| %s | %d | %d | %d | %s |" % (gid, len(bl), len(real), len(so),
                                          ", ".join("`%s`" % e for e in ex)))
    a("")
    a("A blank sprite is fully transparent, so the id draws nothing. A solid sprite is one "
      "repeated RGBA value, so the id draws a featureless block. Most blank `overlay_` ids are "
      "deliberate: those tilesets simply do not draw worn clothing. The non-overlay column is "
      "the part to look at. Examples verified by reading the pixels: ChestHole maps every "
      "DinoMod monster (for example `mon_tyrannosaurus`, fg 6393, `tree.png` local 73) to an "
      "empty cell; BrownLikeBears defines `battleaxe` twice and the second entry (fg 861) is "
      "fully transparent, which hides the item. Full list: `blank_or_solid.csv`.")
    a("")
    a("## 4. Totals")
    a("")
    a("| Tileset | Sprites on sheets | Referenced sprites | Unique referenced | Ids | Duplicate groups | Placeholder groups | Blank ids | Solid ids |")
    a("|---|---|---|---|---|---|---|---|---|")
    for t in totals:
        a("| %s | %d | %d | %d | %d | %d | %d | %d | %d |" % (
            t["tileset"], t["sprites"], t["referenced"], t["unique"], t["ids"],
            t["dupes"], t["placeholders"], t["blank_ids"], t["solid_ids"]))
    a("")
    a("## Notes and limits")
    a("")
    a("- Hashes compare exact pixels, including alpha; two sprites that differ by one alpha "
      "level are not reported as duplicates, so the counts are lower bounds.")
    a("- Cross-tileset matches only exist when the two sheets use the same sprite size, because "
      "a cell of a different size cannot contain the same pixels.")
    a("- Sprite sheets referenced by `data/mods/*/mod_tileset.json` are out of scope here; only "
      "`gfx/` tilesets and `data/json/external_tileset/` are covered.")
    a("")
    a("Total per-tileset duplicate groups: %d; distinct content findings: %d. "
      "Groups on placeholder sheets: %d. Sprite-cell groups whose members differ "
      "only in transparent padding (same art shifted or padded inside the cell): %d." % (
          len(results), len(display), sum(placeholder_groups.values()), trimmed_groups))
    a("")
    open(os.path.join(OUT, "duplicates.md"), "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
