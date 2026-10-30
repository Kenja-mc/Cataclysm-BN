#!/usr/bin/env python3
"""Generate the Modern controls keyboard and the key tables of docs/fork/controls.md.

    python3 build-scripts/gen_controls_guide.py [--check]

Both outputs come from data/raw/keybindings/*.json (Classic) with
data/raw/control_schemes/modern.json laid over it, which is how the game resolves Modern. The
guide's hand-written text lives in controls.md itself; only the blocks between
`<!-- BEGIN generated:NAME -->` and `<!-- END generated:NAME -->` are rewritten. `--check` exits
non-zero when either file is out of date.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

ROOT = Path(__file__).resolve().parent.parent
CLASSIC_DIR = ROOT / "data" / "raw" / "keybindings"
MODERN_FILE = ROOT / "data" / "raw" / "control_schemes" / "modern.json"
SVG_OUT = ROOT / "docs" / "fork" / "images" / "controls-modern.svg"
GUIDE = ROOT / "docs" / "fork" / "controls.md"

# Map actions by family: (heading, keycap colour, action ids in table order).
FAMILIES = (
    ("Moving", "#2b6cb0", (
        "UP", "LEFT", "DOWN", "RIGHT", "LEFTUP", "RIGHTUP", "LEFTDOWN", "RIGHTDOWN", "pause",
        "wait", "open_movement", "LEVEL_UP", "LEVEL_DOWN", "auto_explore", "auto_travel_mode")),
    ("Looking and selecting", "#6b46c1", (
        "shift_n", "shift_w", "shift_s", "shift_e", "shift_nw", "shift_ne", "shift_sw", "shift_se",
        "PEEK_N", "PEEK_W", "PEEK_S", "PEEK_E", "PEEK_NW", "PEEK_NE", "PEEK_SW", "PEEK_SE",
        "NEXT_TARGET", "PREV_TARGET", "zoom_in", "zoom_out", "map", "world_hub")),
    ("Items and interaction", "#2f855a", (
        "examine", "toggle_curtain", "inventory", "advinv", "use_contextual", "pickup",
        "quick_pickup", "pickup_all", "reload_item", "throw", "butcher", "horn",
        "hotbar_1", "hotbar_2", "hotbar_3", "hotbar_4", "hotbar_5", "hotbar_6", "hotbar_assign")),
    ("Combat", "#c53030", ("fire", "select_fire_mode", "safemode", "ignore_enemy")),
    ("Character", "#b7791f", (
        "player_data", "body_status", "bionics", "mutations", "perks", "messages", "diary")),
    ("Menus and system", "#4a5568", (
        "action_menu", "search_action", "main_menu", "open_options", "HELP_KEYBINDINGS", "help",
        "debug", "lua_console")),
)
OTHER = ("Other", "#319795")

# Keycap labels; the tables use the game's own action names.
SHORT = {
    "UP": "move N", "DOWN": "move S", "LEFT": "move W", "RIGHT": "move E",
    "LEFTUP": "move NW", "RIGHTUP": "move NE", "LEFTDOWN": "move SW", "RIGHTDOWN": "move SE",
    "pause": "wait a turn", "wait": "wait / rest", "open_movement": "stance menu",
    "LEVEL_UP": "stairs up", "LEVEL_DOWN": "stairs down", "auto_explore": "auto-explore",
    "auto_travel_mode": "auto travel", "NEXT_TARGET": "next hostile",
    "PREV_TARGET": "prev hostile", "zoom_in": "zoom in", "zoom_out": "zoom out", "map": "map",
    "world_hub": "World page", "examine": "interact", "toggle_curtain": "curtain",
    "inventory": "inventory", "advinv": "adv. inventory", "use_contextual": "use by kind",
    "pickup": "pick up", "quick_pickup": "take all beside", "pickup_all": "pick up nearby",
    "reload_item": "reload", "throw": "throw", "butcher": "butcher", "horn": "horn",
    "hotbar_assign": "assign hotbar", "fire": "attack", "select_fire_mode": "fire mode",
    "safemode": "safe mode", "ignore_enemy": "ignore foe", "player_data": "character",
    "body_status": "body", "bionics": "bionics", "mutations": "mutations", "perks": "perks",
    "messages": "messages", "diary": "diary", "action_menu": "all actions",
    "search_action": "find action", "main_menu": "menu", "open_options": "options",
    "HELP_KEYBINDINGS": "all keys", "help": "help", "debug": "debug", "lua_console": "Lua console",
}
for _n in range(1, 7):
    SHORT[f"hotbar_{_n}"] = f"hotbar {_n}"
DIRECTIONS = {"n": "N", "w": "W", "s": "S", "e": "E", "nw": "NW", "ne": "NE", "sw": "SW", "se": "SE"}
for _d, _label in DIRECTIONS.items():
    SHORT[f"shift_{_d}"] = f"select {_label}"
    SHORT[f"PEEK_{_d.upper()}"] = f"peek {_label}"

# Screens with their own keys: (heading, binding categories, one-line description, optional ids).
GLOBAL_IDS = ("CONFIRM", "QUIT", "HELP_KEYBINDINGS", "FILTER", "RESET_FILTER", "PAGE_UP", "PAGE_DOWN",
              "SCROLL_UP", "SCROLL_DOWN", "NEXT_TAB", "PREV_TAB", "DESC_UP", "DESC_DOWN", "SELECT",
              "SEC_SELECT")
SCREENS = (
    ("Every screen", (None, "default"), "Keys most screens share unless they say otherwise.", GLOBAL_IDS),
    ("Menus", ("UILIST",), "The common list menus, such as the Enter menu and item actions."),
    ("Look around", ("LOOK",), "Look mode: a cursor that describes what is under it."),
    ("Aiming", ("TARGET",), "Choosing a target for a gun, a throw or a spell."),
    ("World map", ("OVERMAP",), "The `m` map."),
    ("Inventory", ("INVENTORY", "INVENTORY_ITEM", "ITEM_ACTIONS"),
     "The `i` inventory and the action menu of a selected item."),
    ("Picking up", ("PICKUP",), "The pickup list (`g` on a pile, `Ctrl+G`)."),
    ("Advanced inventory", ("ADVANCED_INVENTORY",), "Two panes for moving items between places."),
    ("Crafting", ("CRAFTING",), "The crafting menu (`i`, then `F5`)."),
    ("Trading", ("NPC_TRADE",), "Trading with an NPC."),
    ("Vehicle controls", ("VEHICLE",), "The controls menu of the vehicle you sit at."),
)

KEY_NAMES = {
    "SPACE": "Space", "SHIFT_SPACE": "Shift+Space", "CTRL_SPACE": "Ctrl+Space", "RETURN": "Enter",
    "ESC": "Esc", "TAB": "Tab", "BACKTAB": "Shift+Tab", "PPAGE": "PgUp", "NPAGE": "PgDn",
    "UP": "↑", "DOWN": "↓", "LEFT": "←", "RIGHT": "→", "HOME": "Home", "END": "End",
    "DELETE": "Delete", "BACKSPACE": "Backspace", "MOUSE_LEFT": "Left click",
    "MOUSE_RIGHT": "Right click", "SCROLL_UP": "Wheel up", "SCROLL_DOWN": "Wheel down",
    "MOUSE_BACK": "Mouse back button",
}


def read_entries(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load():
    """Returns (classic, modern): {(category, id): entry}, Modern laid over Classic."""
    classic = {}
    for path in sorted(CLASSIC_DIR.glob("*.json")):
        for entry in read_entries(path):
            if entry.get("type") == "keybinding":
                classic[(entry.get("category"), entry["id"])] = entry
    modern = dict(classic)
    for entry in read_entries(MODERN_FILE):
        if entry.get("type") == "keybinding":
            key = (entry.get("category"), entry["id"])
            modern[key] = {**classic.get(key, {}), **entry}
    return classic, modern


def bindings(entry, methods=("keyboard", "mouse")):
    keys = []
    for binding in (entry or {}).get("bindings", []):
        if binding.get("input_method") not in methods:
            continue
        raw = binding["key"]
        for key in raw if isinstance(raw, list) else [raw]:
            if key != "MOUSE_MOVE":
                keys.append(key)
    return keys


def key_tokens(key):
    """Display tokens for one binding: 'CTRL+F' -> ['Ctrl', 'F'], 'W' -> ['Shift', 'W']."""
    if key in KEY_NAMES:
        return KEY_NAMES[key].split("+") if "+" in KEY_NAMES[key] else [KEY_NAMES[key]]
    if key.startswith("CTRL+"):
        return ["Ctrl", key[5:].upper()]
    if key.startswith("NUMPAD_"):
        return [f"Numpad {key[7:]}"]
    if len(key) == 1 and key.isalpha() and key.isupper():
        return ["Shift", key]
    if len(key) == 1 and key.isalpha():
        return [key.upper()]
    return [key]


def resolve(table, category, action):
    """The entry a screen uses: its own, else the global one, as input_context looks them up."""
    for key in ((category, action), (None, action), ("default", action)):
        if key in table:
            return table[key]
    return None


def kbd(key):
    return "+".join(f"<kbd>{token.replace('|', '&#124;')}</kbd>" for token in key_tokens(key))


def keys_cell(keys):
    return ", ".join(kbd(key) for key in keys) if keys else "—"


def action_name(entry, action_id):
    return (entry or {}).get("name") or action_id.replace("_", " ").capitalize()


def table(rows):
    lines = ["| Action | Modern | Classic |", "| --- | --- | --- |"]
    for name, modern_keys, classic_keys in rows:
        lines.append(f"| {name.replace('|', '&#124;')} | {keys_cell(modern_keys)} | {keys_cell(classic_keys)} |")
    return lines


def map_tables(classic, modern):
    placed = {action for _, _, ids in FAMILIES for action in ids}
    extra = tuple(sorted(action for (category, action), entry in modern.items()
                         if category == "DEFAULTMODE" and action not in placed and bindings(entry)))
    out = []
    for heading, _, ids in FAMILIES + ((OTHER[0], OTHER[1], extra),):
        rows = []
        for action in ids:
            entry = resolve(modern, "DEFAULTMODE", action)
            if entry is None:
                continue
            rows.append((action_name(entry, action), bindings(entry),
                         bindings(resolve(classic, "DEFAULTMODE", action))))
        if rows:
            out += [f"### {heading}", ""] + table(rows) + [""]
    return out


def screen_tables(classic, modern):
    out = []
    for heading, categories, blurb, *only in SCREENS:
        rows, seen = [], set()
        for (category, action), entry in modern.items():
            if category not in categories or action in seen or (only and action not in only[0]):
                continue
            seen.add(action)
            modern_keys = bindings(entry)
            classic_keys = bindings(resolve(classic, category, action))
            if modern_keys or classic_keys:
                rows.append((action_name(entry, action), modern_keys, classic_keys))
        if rows:
            out += [f"### {heading}", "", blurb, ""] + table(rows) + [""]
    return out


def replace_block(text, name, lines):
    begin, end = f"<!-- BEGIN generated:{name} -->", f"<!-- END generated:{name} -->"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise SystemExit(f"{GUIDE}: missing {begin} … {end}")
    body = "\n".join([begin, "", *lines, end])
    return pattern.sub(lambda _: body, text)


# ---------------------------------------------------------------- keyboard

@dataclass(frozen=True)
class Key:
    label: str
    units: float = 1
    plain: str | None = None
    shift: str | None = None
    ctrl: str | None = None
    height: float = 1


def letter(ch):
    return Key(ch, plain=ch.lower(), shift=ch, ctrl=f"CTRL+{ch}")


ROWS = (
    tuple(Key(ch, plain=ch, shift=shifted) for ch, shifted in zip("`1234567890-=", "~!@#$%^&*()_+"))
    + (Key("Backspace", 2, "BACKSPACE"),),
    (Key("Tab", 1.5, "TAB", "BACKTAB"),) + tuple(letter(ch) for ch in "QWERTYUIOP")
    + (Key("[", plain="[", shift="{"), Key("]", plain="]", shift="}"), Key("\\", 1.5, "\\", "|")),
    (Key("Caps Lock", 1.75),) + tuple(letter(ch) for ch in "ASDFGHJKL")
    + (Key(";", plain=";", shift=":"), Key("'", plain="'", shift='"'), Key("Enter", 2.25, "RETURN")),
    (Key("Shift", 2.25),) + tuple(letter(ch) for ch in "ZXCVBNM")
    + (Key(",", plain=",", shift="<"), Key(".", plain=".", shift=">"), Key("/", plain="/", shift="?"),
       Key("Shift", 2.75)),
    (Key("Ctrl", 1.25), Key("Super", 1.25), Key("Alt", 1.25),
     Key("Space", 6.25, "SPACE", "SHIFT_SPACE", "CTRL_SPACE"), Key("Alt", 1.25), Key("Super", 1.25),
     Key("Menu", 1.25), Key("Ctrl", 1.25)),
)
PITCH_X, PITCH_Y, GAP, MARGIN = 76, 98, 5, 24
INK, MUTED, FAINT = "#1a202c", "#4a5568", "#a0aec0"
CHAR_W = 0.56  # average glyph width of the sans-serif face, in ems


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fit(text, width, largest=13.0, smallest=9.0):
    """Lines and font size that fit text into width: one line if possible, else two."""
    size = largest
    while size >= 11:
        if len(text) * CHAR_W * size <= width:
            return [text], size
        size -= 0.5
    size = largest
    while size > smallest:
        rows = wrap(text, max(4, int(width / (CHAR_W * size))), break_long_words=False)
        if len(rows) <= 2 and all(len(row) * CHAR_W * size <= width for row in rows):
            return rows, size
        size -= 0.5
    return wrap(text, max(4, int(width / (CHAR_W * smallest))))[:2], smallest


# One keyboard per modifier: (file suffix, title, Key field, modifier keycaps to highlight).
LAYERS = (
    ("", "Keys alone", "plain", ()),
    ("-shift", "Hold Shift", "shift", ("Shift",)),
    ("-ctrl", "Hold Ctrl", "ctrl", ("Ctrl",)),
)
MOUSE_NOTES = (
    ("Left click", "use or attack beside you"),
    ("Right click", "select a tile, free"),
    ("Wheel", "zoom; scroll lists"),
    ("Hover", "describe the tile"),
    ("Back button", "cancel, like Esc"),
)


class Keyboard:
    def __init__(self, modern):
        self.lines = []
        self.keymap = {}
        self.family = {action: colour for _, colour, ids in FAMILIES for action in ids}
        for (category, action), entry in modern.items():
            if category == "DEFAULTMODE":
                for key in bindings(entry, ("keyboard",)):
                    self.keymap.setdefault(key, []).append(action)
        self.conflicts = [(key, ids) for key, ids in self.keymap.items() if len(ids) > 1]

    def add(self, line):
        self.lines.append(line)

    def colour(self, action):
        return self.family.get(action, OTHER[1])

    def draw_key(self, key, x, y, field="plain", held=()):
        width = key.units * PITCH_X - GAP
        height = key.height * PITCH_Y - GAP
        code = getattr(key, field)
        actions = self.keymap.get(code, []) if code else []
        if key.label in held:
            self.add(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="6" fill="{INK}"/>')
            self.add(f'<text x="{x + 8}" y="{y + 22}" font-size="15" font-weight="700" fill="#ffffff">'
                     f'{esc(key.label)}</text>')
            self.add(f'<text x="{x + 8}" y="{y + 42}" font-size="12" fill="#ffffff">hold</text>')
            return
        conflict = len(actions) > 1
        colour = self.colour(actions[0]) if actions else FAINT
        dash = ' stroke-dasharray="5 3"' if conflict else ""
        self.add(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="6" '
                 f'fill="{colour if actions else "none"}" fill-opacity="{0.12 if actions else 0}" '
                 f'stroke="{"#e53e3e" if conflict else colour}" stroke-width="{1.8 if actions else 0.8}"{dash}/>')
        label = key.label
        if field == "shift" and key.shift and len(key.shift) == 1 and not key.shift.isalpha():
            label = key.shift
        label_size = min(16, (width - 12) / max(len(label) * CHAR_W, 1))
        self.add(f'<text x="{x + 8}" y="{y + 21}" font-size="{label_size:.1f}" font-weight="700" '
                 f'fill="{INK if actions else MUTED}">{esc(label)}</text>')
        if actions:
            rows, size = fit(" / ".join(SHORT.get(action, action) for action in actions), width - 14)
            for index, row in enumerate(rows):
                self.add(f'<text x="{x + 8}" y="{y + 44 + index * (size + 3)}" font-size="{size:.1f}" '
                         f'font-weight="600" fill="{colour}">{esc(row)}</text>')

    def header(self, width, height, title, subtitle):
        self.lines = []
        self.add('<?xml version="1.0" encoding="UTF-8"?>')
        self.add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                 f'viewBox="0 0 {width} {height}" font-family="DejaVu Sans, Verdana, sans-serif">')
        self.add(f'<title>{esc(title)}</title>')
        self.add(f'<desc>{esc(subtitle)} Generated from the binding files.</desc>')
        self.add(f'<rect width="{width}" height="{height}" rx="10" fill="#ffffff"/>')
        self.add(f'<text x="{MARGIN}" y="38" font-size="26" font-weight="700" fill="{INK}">{esc(title)}</text>')
        self.add(f'<text x="{MARGIN}" y="62" font-size="14" fill="{MUTED}">{esc(subtitle)}</text>')

    def legend(self, top):
        x = MARGIN
        for heading, colour, _ in FAMILIES + ((OTHER[0], OTHER[1], ()),):
            self.add(f'<rect x="{x}" y="{top}" width="18" height="18" rx="4" fill="{colour}" '
                     f'fill-opacity="0.25" stroke="{colour}" stroke-width="1.8"/>')
            self.add(f'<text x="{x + 26}" y="{top + 14}" font-size="13" fill="{INK}">{esc(heading)}</text>')
            x += 26 + len(heading) * CHAR_W * 13 + 28

    def main_rows(self, top, field, held):
        for row_index, row in enumerate(ROWS):
            x = MARGIN
            for key in row:
                self.draw_key(key, x, top + row_index * PITCH_Y, field, held)
                x += key.units * PITCH_X

    def render(self, layer):
        _, title, field, held = layer
        keyboard_width = 15 * PITCH_X
        width = keyboard_width + 2 * MARGIN
        if field != "plain":
            rows_top = 84
            height = rows_top + 5 * PITCH_Y + 50
            self.header(width, height, f"Modern controls on the map: {title}",
                        f"{title} and press the key. Grey keys do nothing with {held[0]} on the map.")
            self.main_rows(rows_top, field, held)
            self.legend(rows_top + 5 * PITCH_Y + 16)
            self.add('</svg>')
            return "\n".join(self.lines) + "\n"

        top = 84
        rows_top = top + PITCH_Y + 16
        clusters_top = rows_top + 5 * PITCH_Y + 46
        legend_top = clusters_top + 4 * PITCH_Y + 20
        height = legend_top + 40
        self.header(width, height, "Modern controls on the map: keys alone",
                    "Walking into an enemy attacks it. Space does the obvious thing with the tile "
                    "you face or selected; Enter lists every other action.")
        self.draw_key(Key("Esc", plain="ESC"), MARGIN, top)
        for index in range(12):
            unit = 2 + index + 0.5 * (index // 4)
            self.draw_key(Key(f"F{index + 1}", plain=f"F{index + 1}"), MARGIN + unit * PITCH_X, top)
        self.main_rows(rows_top, "plain", ())

        self.add(f'<text x="{MARGIN}" y="{clusters_top - 14}" font-size="15" font-weight="700" fill="{INK}">'
                 'Navigation, arrows, mouse and numpad</text>')
        for index, (label, code) in enumerate((("Insert", "INSERT"), ("Home", "HOME"), ("PgUp", "PPAGE"),
                                               ("Delete", "DELETE"), ("End", "END"), ("PgDn", "NPAGE"))):
            self.draw_key(Key(label, plain=code), MARGIN + index % 3 * PITCH_X,
                          clusters_top + index // 3 * PITCH_Y)
        arrows_x = MARGIN + 3 * PITCH_X + 24
        for label, code, column, row in (("↑", "UP", 1, 0), ("←", "LEFT", 0, 1), ("↓", "DOWN", 1, 1),
                                         ("→", "RIGHT", 2, 1)):
            self.draw_key(Key(label, plain=code), arrows_x + column * PITCH_X, clusters_top + row * PITCH_Y)
        self.draw_mouse(arrows_x + 3 * PITCH_X + 30, clusters_top)
        pad_x = MARGIN + keyboard_width - 4 * PITCH_X
        for column, label in enumerate(("Num", "/", "*", "−")):
            self.draw_key(Key(label), pad_x + column * PITCH_X, clusters_top)
        for row, digits in enumerate(("789", "456", "123"), start=1):
            for column, digit in enumerate(digits):
                self.draw_key(Key(digit, plain=f"NUMPAD_{digit}"), pad_x + column * PITCH_X,
                              clusters_top + row * PITCH_Y)
        self.draw_key(Key("+", height=2), pad_x + 3 * PITCH_X, clusters_top + PITCH_Y)
        self.draw_key(Key("Enter", plain="RETURN"), pad_x + 3 * PITCH_X, clusters_top + 3 * PITCH_Y)
        self.legend(legend_top)
        self.add('</svg>')
        return "\n".join(self.lines) + "\n"

    def draw_mouse(self, x, y):
        """The map's mouse behaviour lives in code rather than bindings, so it is drawn by hand."""
        body_w, body_h = 104, 176
        self.add(f'<rect x="{x}" y="{y + 8}" width="{body_w}" height="{body_h}" rx="50" fill="none" '
                 f'stroke="{INK}" stroke-width="1.8"/>')
        self.add(f'<line x1="{x + body_w / 2}" y1="{y + 8}" x2="{x + body_w / 2}" y2="{y + 78}" '
                 f'stroke="{INK}" stroke-width="1.4"/>')
        self.add(f'<line x1="{x}" y1="{y + 78}" x2="{x + body_w}" y2="{y + 78}" stroke="{INK}" stroke-width="1.4"/>')
        self.add(f'<rect x="{x + body_w / 2 - 7}" y="{y + 26}" width="14" height="30" rx="7" fill="#e2e8f0" '
                 f'stroke="{INK}" stroke-width="1.2"/>')
        self.add(f'<rect x="{x - 5}" y="{y + 96}" width="8" height="26" rx="3" fill="#e2e8f0" '
                 f'stroke="{INK}" stroke-width="1.2"/>')
        self.add(f'<text x="{x + 20}" y="{y + 50}" font-size="14" font-weight="700" fill="{INK}">L</text>')
        self.add(f'<text x="{x + body_w - 30}" y="{y + 50}" font-size="14" font-weight="700" fill="{INK}">R</text>')
        text_x = x + body_w + 18
        for index, (what, does) in enumerate(MOUSE_NOTES):
            line_y = y + 22 + index * 34
            self.add(f'<text x="{text_x}" y="{line_y}" font-size="13" font-weight="700" fill="{INK}">{esc(what)}</text>')
            self.add(f'<text x="{text_x}" y="{line_y + 16}" font-size="12.5" fill="{MUTED}">{esc(does)}</text>')
        self.add(f'<text x="{x}" y="{y + 206}" font-size="12.5" fill="{MUTED}">Clicks never walk you.</text>')


def render_guide(classic, modern, current):
    text = replace_block(current, "map", map_tables(classic, modern))
    return replace_block(text, "screens", screen_tables(classic, modern))


def main():
    check = "--check" in sys.argv[1:]
    classic, modern = load()
    keyboard = Keyboard(modern)
    outputs = {SVG_OUT.with_name(f"{SVG_OUT.stem}{layer[0]}.svg"): keyboard.render(layer) for layer in LAYERS}
    outputs[GUIDE] = render_guide(classic, modern, GUIDE.read_text(encoding="utf-8"))
    stale = [path for path, text in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
    if check:
        for path in stale:
            print(f"out of date: {path.relative_to(ROOT)}")
        sys.exit(1 if stale else 0)
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    for key, ids in keyboard.conflicts:
        print(f"CONFLICT on {key}: {', '.join(ids)}")
    if not keyboard.conflicts:
        print("no map key conflicts")


if __name__ == "__main__":
    main()
