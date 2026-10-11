#!/usr/bin/env python3
"""Generate the modern-controls keyboard diagram.

Reads the classic keybinding data from ``data/raw/keybindings/*.json`` and
applies the modern control scheme overlay from
``data/raw/control_schemes/modern.json`` (an overlay entry with the same
``id`` and ``category`` replaces that action's bindings; new ids are added),
then renders ``docs/fork/images/controls-modern.svg``: one key per physical
keycap, labelled with its DEFAULTMODE action, plus the same key with Shift
as a small coloured label.  A key bound to more than one DEFAULTMODE action
is drawn in red with both names so conflicts stay visible.

Stdlib only.  Usage::

    python3 build-scripts/gen_controls_svg.py [output.svg]
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASSIC_FILES = tuple(path.name for path in sorted((ROOT / "data/raw/keybindings").glob("*.json")))
OVERLAY_FILE = "modern.json"
DEFAULT_OUT = ROOT / "docs" / "fork" / "images" / "controls-modern.svg"

# Menu-only actions worth a note on the diagram (looked up in every category),
# with the verb phrase used in the note sentence.
MENU_NOTES = (
    ("CRAFTING", "CRAFT_PARTS", "jumps to a part recipe"),
    ("INVENTORY_ITEM", "COMBINE", "combines items"),
)

# Short labels for action names that would overflow a key.
ABBREV = {
    "Toggle Safe Mode": "safe mode",
    "View Player Info": "player info",
    "Move northwest": "move nw",
    "Move north": "move n",
    "Move west": "move w",
    "Move northeast": "move ne",
    "Move east": "move e",
    "Move southwest": "move sw",
    "Move south": "move s",
    "Move southeast": "move se",
    "Pause": "wait",
    "Wait for Several Minutes": "wait",
    "Toggle Run": "run",
    "Toggle Crouch": "crouch",
    "Toggle Prone": "prone",
    "Lua Console": "console",
    "Recraft last recipe": "recraft",
    "Swap Inventory Letters": "swap inv",
    "Attack in a direction": "attack (dir)",
    "Apply or Use Item": "use",
    "Reload Item": "reload",
    "Throw Item": "throw",
    "Open Inventory": "inventory",
    "Open Door": "open",
    "Smash Nearby Terrain": "smash",
    "Toggle manual combat mode": "manual combat",
    "Apply or Use Wielded Item": "apply wielded",
    "Open Hitchhiker's Guide": "guide",
    "Pick up items from all nearby tiles": "pick up all",
    "Pick up items from one nearby tile": "pick up 1",
    "Body status": "body status",
    "Jump across an adjacent tile": "jump",
    "Craft Items": "craft",
    "Construct Terrain": "construct",
    "Look Around": "look",
    "Ignore Nearby Enemy": "ignore enemy",
    "Action Menu": "action menu",
    "Sort the pile you're standing on": "sort pile",
    "View Morale": "morale",
    "Butcher": "butcher",
    "Explore the nearest unexplored area": "auto-explore",
    "View Map": "map",
    "Advanced Inventory management": "adv inv",
    "Examine Nearby Terrain": "interact",
    "View/Activate Bionics": "bionics",
    "View/Activate Mutations": "mutations",
    "Spellcasting": "spells",
    "Haul items along the ground": "haul",
    "Chat with NPC": "chat",
    "View Help": "help",
    "Main Menu": "main menu",
    "Toggle attack mode of Wielded Item": "fire mode",
    "View Achievements, Scores, and Kills": "scores",
    "Disassemble items": "disassemble",
    "Select default ammo for Wielded Item": "default ammo",
    "Re-layer armor/clothing": "re-layer",
    "Select Martial Arts Style": "martial arts",
    "Control Vehicle": "drive",
    "View Factions": "factions",
    "Sleep": "sleep",
    "Item Action Menu": "item menu",
    "View Message Log": "messages",
    "View Missions": "missions",
    "Manage zones": "zones",
    "Compare two Items": "compare",
    "Wear Item": "wear",
    "Eat": "eat",
    "Read": "read",
    "Take Off Worn Item": "take off",
    "Unload or Empty Wielded Item": "unload",
    "Close Door": "close",
    "Save and Quit": "save & quit",
    "Drop Item": "drop",
    "Grab something nearby": "grab",
    "Wield": "wield",
    "Fire Wielded Item": "fire",
    "Autoattack": "attack",
    "Quick stack to nearby storage": "quick stack",
    "Center View": "center",
    "Movement Mode Menu": "move menu",
    "Open Diary": "diary",
    "Whitelist enemy": "whitelist",
    "Toggle Minimap": "minimap",
}

GROUP_COLORS = {
    "move":  {"fill": "#dbeafe", "stroke": "#2563eb", "label": "#1d4ed8"},
    "items": {"fill": "#dcfce7", "stroke": "#16a34a", "label": "#15803d"},
    "combat": {"fill": "#fee2e2", "stroke": "#dc2626", "label": "#b91c1c"},
    "menus": {"fill": "#f3e8ff", "stroke": "#9333ea", "label": "#7e22ce"},
}
GROUP_LEGEND = (
    ("move", "move &amp; wait"),
    ("items", "items &amp; interaction"),
    ("combat", "combat"),
    ("menus", "menus &amp; info"),
)

MOVE_IDS = {
    "UP", "DOWN", "LEFT", "RIGHT", "LEFTUP", "RIGHTUP", "LEFTDOWN",
    "RIGHTDOWN", "pause", "wait", "auto_explore", "jump", "toggle_run",
    "toggle_crouch", "toggle_prone", "cycle_move", "reset_move",
}
ITEMS_IDS = {
    "recraft", "organize", "chat", "apply", "apply_wielded", "inventory",
    "open", "haul", "examine", "craft", "construct", "pickup", "pickup_all",
    "drop", "wear", "eat", "take_off", "unload", "quick_stack", "sort_armor",
    "disassemble", "sort_pile", "compare", "advinv", "salvage", "read",
    "item_action_menu", "wield",
}
COMBAT_IDS = {
    "attack", "autoattack", "fire", "fire_burst", "throw", "smash", "butcher",
    "grab", "control_vehicle", "pick_style", "toggle_manual_combat_mode",
    "select_fire_mode", "select_default_ammo", "reload_item", "reload_wielded",
    "reload_weapon", "reload", "unload_all", "ignore_enemy", "safemode",
    "whitelist_enemy",
}
MENUS_IDS = {
    "main_menu", "help", "lua_console", "bionics", "mutations", "cast_spell",
    "body_status", "action_menu", "morale", "map", "missions", "zones",
    "messages", "player_data", "factions", "sleep", "scores", "save",
    "center", "open_movement", "toggle_panel_adm", "diary", "look",
}
GROUP_OF = {}
for _ids, _group in ((MOVE_IDS, "move"), (ITEMS_IDS, "items"),
                     (COMBAT_IDS, "combat"), (MENUS_IDS, "menus")):
    for _id in _ids:
        GROUP_OF[_id] = _group

# Keyboard rows: (keycap, width, primary key, shift key or None).
# Widths: 1u = 60px, plus 6px gap after each key.  Row 2 Tab = 93px,
# row 3 Enter = 109px, row 5 Space = 456px (same geometry as before).
ROWS = (
    (("Esc", 60, "ESC", None), ("F1", 60, "F1", None), ("F2", 60, "F2", None),
     ("F3", 60, "F3", None), ("F4", 60, "F4", None)),
    (("`", 60, "`", "~"), ("1", 60, "1", "!"), ("2", 60, "2", "@"),
     ("3", 60, "3", "#"), ("4", 60, "4", "$"), ("5", 60, "5", "%"),
     ("6", 60, "6", "^"), ("7", 60, "7", "&"), ("8", 60, "8", "*"),
     ("9", 60, "9", "("), ("0", 60, "0", ")"), ("-", 60, "-", "_"),
     ("=", 60, "=", "+")),
    (("Tab", 93, "TAB", "BACKTAB"), ("Q", 60, "q", "Q"), ("W", 60, "w", "W"),
     ("E", 60, "e", "E"), ("R", 60, "r", "R"), ("T", 60, "t", "T"),
     ("Y", 60, "y", "Y"), ("U", 60, "u", "U"), ("I", 60, "i", "I"),
     ("O", 60, "o", "O"), ("P", 60, "p", "P"), ("[", 60, "[", "{"),
     ("]", 60, "]", "}"), ("\\", 60, "\\", "|")),
    (("A", 60, "a", "A"), ("S", 60, "s", "S"), ("D", 60, "d", "D"),
     ("F", 60, "f", "F"), ("G", 60, "g", "G"), ("H", 60, "h", "H"),
     ("J", 60, "j", "J"), ("K", 60, "k", "K"), ("L", 60, "l", "L"),
     (";", 60, ";", ":"), ("'", 60, "'", '"'),
     ("Enter", 109, "RETURN", None)),
    (("Z", 60, "z", "Z"), ("X", 60, "x", "X"), ("C", 60, "c", "C"),
     ("V", 60, "v", "V"), ("B", 60, "b", "B"), ("N", 60, "n", "N"),
     ("M", 60, "m", "M"), (",", 60, ",", "<"), (".", 60, ".", ">"),
     ("/", 60, "/", "?")),
    (("Space", 456, "SPACE", None),),
)
ROW_X = (40, 40, 40, 90, 238, 255)  # left offset of each row
ROW_Y = (96, 162, 228, 294, 360, 426)
KEY_H = 58


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def short_name(entry):
    return ABBREV.get(entry["name"], entry["name"])


def group_of(action_id, name):
    group = GROUP_OF.get(action_id)
    if group is None:
        print(f"warning: no group for {action_id!r} ({name}); using 'menus'",
              file=sys.stderr)
        group = "menus"
    return group


def primary_font_size(name):
    n = len(name)
    if n <= 6:
        return 10.5
    if n <= 10:
        return 9.5
    if n <= 13:
        return 8.5
    if n <= 17:
        return 7.6
    return 6.8


def truncate(text, limit):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def load_entries():
    """Classic DEFAULTMODE entries with the modern overlay applied."""
    entries = OrderedDict()
    for fname in CLASSIC_FILES:
        data = json.loads((ROOT / "data" / "raw" / "keybindings" / fname)
                          .read_text(encoding="utf-8"))
        for entry in data:
            if entry.get("category") == "DEFAULTMODE":
                entries[entry["id"]] = entry
    overlay = json.loads((ROOT / "data" / "raw" / "control_schemes"
                          / OVERLAY_FILE).read_text(encoding="utf-8"))
    for entry in overlay:
        if entry.get("category") == "DEFAULTMODE":
            entries[entry["id"]] = entry  # same id+category replaces bindings
    return entries


def load_all_entries():
    """Every entry from every category (for menu-only note lookups)."""
    entries = OrderedDict()
    for fname in CLASSIC_FILES:
        data = json.loads((ROOT / "data" / "raw" / "keybindings" / fname)
                          .read_text(encoding="utf-8"))
        for entry in data:
            entries[(entry.get("category", "default"), entry["id"])] = entry
    overlay = json.loads((ROOT / "data" / "raw" / "control_schemes"
                          / OVERLAY_FILE).read_text(encoding="utf-8"))
    for entry in overlay:
        entries[(entry.get("category", "default"), entry["id"])] = entry
    return entries


def build_keymap(entries):
    """Map physical key -> ordered list of DEFAULTMODE action ids."""
    keymap = {}
    for action_id, entry in entries.items():
        for binding in entry.get("bindings", []):
            if binding.get("input_method") == "keyboard":
                keymap.setdefault(binding["key"], []).append(action_id)
    return keymap


def menu_note_parts(all_entries):
    """Look up the menu-only actions used in the note (any category)."""
    parts = []
    for category, action_id, phrase in MENU_NOTES:
        entry = all_entries.get((category, action_id))
        if entry is None:
            continue
        keys = [b["key"] for b in entry.get("bindings", [])
                if b.get("input_method") == "keyboard"]
        if keys:
            parts.append((keys[0], phrase))
    return parts


def render_svg(keymap, entries, menu_parts):
    lines = []
    add = lines.append
    add('<?xml version="1.0" encoding="UTF-8"?>')
    add('<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="690" '
        'viewBox="0 0 1000 690" font-family="sans-serif">')
    add('  <title>Modern control scheme</title>')
    add('  <desc>Keyboard diagram of the default (modern) control scheme of '
        'Cataclysm: Bright Nights Overhaul fork. Every key is labelled with '
        'its default-mode action; the small label is the same key pressed '
        'with Shift.</desc>')
    add('')
    add('  <rect x="0" y="0" width="1000" height="690" fill="#f8fafc"/>')
    add('')
    add('  <text x="40" y="44" font-size="25" font-weight="700" '
        'fill="#0f172a">Modern control scheme &#8212; default keys</text>')
    add('  <text x="40" y="68" font-size="12.5" fill="#475569">Cataclysm: '
        'Bright Nights, Overhaul fork. Every key shows its default-mode '
        'action; the small label is the same key with Shift.</text>')
    add('')

    conflicts = [(key, ids) for key, ids in keymap.items() if len(ids) > 1]
    row_titles = (
        "Esc and function row", "number row", "QWERTY row", "home row",
        "bottom letter row", "Space row",
    )
    for row_idx, row in enumerate(ROWS):
        add(f'  <!-- ================= row {row_idx}: {row_titles[row_idx]} '
            '================= -->')
        x = ROW_X[row_idx]
        y = ROW_Y[row_idx]
        for keycap, width, primary_key, shift_key in row:
            ids = keymap.get(primary_key, [])
            if not ids:
                print(f"warning: no DEFAULTMODE binding for {keycap}",
                      file=sys.stderr)
                x += width + 6
                continue
            cx = x + width / 2
            conflict = len(ids) > 1
            if conflict:
                primary_id = ids[-1]
            else:
                primary_id = ids[0]
            primary_name = short_name(entries[primary_id])
            shift_ids = keymap.get(shift_key, [])
            shift_id = shift_ids[-1] if shift_ids else None
            shift_name = (short_name(entries[shift_id])
                          if shift_id else None)
            if conflict or len(shift_ids) > 1:
                group = GROUP_COLORS["combat"]
            else:
                group = GROUP_COLORS[group_of(primary_id,
                                               entries[primary_id]["name"])]
            stroke = group["stroke"]
            stroke_w = 1.5
            if conflict or len(shift_ids) > 1:
                stroke = "#b91c1c"
                stroke_w = 2.5
            add('  <g>')
            add(f'    <rect x="{x}" y="{y}" width="{width}" '
                f'height="{KEY_H}" rx="6" fill="{group["fill"]}" '
                f'stroke="{stroke}" stroke-width="{stroke_w}"/>')
            add(f'    <text x="{x + 6}" y="{y + 14}" font-size="10" '
                f'fill="#64748b">{esc(keycap)}</text>')
            if conflict:
                for i, cid in enumerate(ids):
                    name = truncate(short_name(entries[cid]), 16)
                    add(f'    <text x="{cx}" y="{y + 30 + i * 15}" '
                        f'font-size="8" font-weight="700" fill="#b91c1c" '
                        f'text-anchor="middle">{esc(name)}</text>')
            else:
                name = truncate(primary_name, 18)
                add(f'    <text x="{cx}" y="{y + 34}" '
                    f'font-size="{primary_font_size(primary_name)}" '
                    f'font-weight="700" fill="#0f172a" '
                    f'text-anchor="middle">{esc(name)}</text>')
                if shift_name:
                    step = min(10, 16 / len(shift_ids))
                    for index, shifted_id in enumerate(shift_ids):
                        shift_label = "⇧ " + truncate(short_name(entries[shifted_id]), 13)
                        add(f'    <text x="{cx}" y="{y + 44 + index * step}" '
                            f'font-size="{min(7, step * 0.75)}" fill="{group["label"]}" '
                            f'text-anchor="middle">{esc(shift_label)}</text>')
            add('  </g>')
            x += width + 6
        add('')

    add('  <!-- ================= legend ================= -->')
    add('  <line x1="40" y1="500" x2="960" y2="500" stroke="#cbd5e1" '
        'stroke-width="1"/>')
    add('  <g font-size="12">')
    for i, (group, label) in enumerate(GROUP_LEGEND):
        x = 40 + i * 190
        add(f'    <rect x="{x}" y="514" width="18" height="18" rx="4" '
            f'fill="{GROUP_COLORS[group]["fill"]}" '
            f'stroke="{GROUP_COLORS[group]["stroke"]}" stroke-width="1.5"/>')
        add(f'    <text x="{x + 26}" y="528" fill="#0f172a">{label}</text>')
    add('  </g>')
    add('')
    add('  <!-- ================= notes ================= -->')
    notes = [
        'The small label under a key is the same key with Shift: '
        '<tspan font-weight="700" fill="#0f172a">Q</tspan> quick stacks, '
        '<tspan font-weight="700" fill="#0f172a">W</tspan> wears, '
        '<tspan font-weight="700" fill="#0f172a">S</tspan> saves, '
        '<tspan font-weight="700" fill="#0f172a">D</tspan> drops, '
        '<tspan font-weight="700" fill="#0f172a">H</tspan> shows body status.',
    ]
    if len(menu_parts) == 2:
        (p_key, p_phrase), (c_key, c_phrase) = menu_parts
        notes.append(
            f'In the crafting menu, <tspan font-weight="700" fill="#0f172a">'
            f'{p_key}</tspan> {p_phrase}; in an inventory item menu, '
            f'<tspan font-weight="700" fill="#0f172a">{c_key}</tspan> '
            f'{c_phrase}.')
    notes += [
        '<tspan font-weight="700" fill="#0f172a">n</tspan> auto-explores: it '
        'walks toward reachable ground you have not seen yet, and '
        'stops for threats.',
        'Arrow keys and the numpad still move, aim and answer direction '
        'prompts. Click a map tile to walk there in one click.',
        '<tspan font-weight="700" fill="#0f172a">?</tspan> lists every '
        'keybinding on any screen, and Enter opens the action menu with '
        'every action.',
        'Classic controls (vi-keys, numpad, bump attacks) stay one option '
        'away: Options &#8594; Interface &#8594; Control scheme.',
    ]
    add('  <g font-size="11.5" fill="#475569">')
    for i, note in enumerate(notes):
        add(f'    <text x="40" y="{558 + i * 20}">{note}</text>')
    add('  </g>')
    add('</svg>')
    return "\n".join(lines) + "\n", conflicts


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    entries = load_entries()
    keymap = build_keymap(entries)
    menu_parts = menu_note_parts(load_all_entries())

    svg, conflicts = render_svg(keymap, entries, menu_parts)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    print(f"wrote {out_path} ({len(keymap)} bound keys)")
    if conflicts:
        for keycap, ids in conflicts:
            print(f"CONFLICT on {keycap}: {', '.join(ids)}")
    else:
        print("no DEFAULTMODE key conflicts")


if __name__ == "__main__":
    main()
