#!/usr/bin/env python3
"""Generate the ANSI controls diagram: gen_controls_svg.py [output.svg]."""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

ROOT = Path(__file__).resolve().parent.parent
CLASSIC_FILES = tuple(path.name for path in sorted((ROOT / "data/raw/keybindings").glob("*.json")))
OVERLAY_FILE = "modern.json"
DEFAULT_OUT = ROOT / "docs" / "fork" / "images" / "controls-modern.svg"

# Fit action labels on keycaps.
ABBREV = {
    "Toggle Safe Mode": "safe mode",
    "Move northwest": "move nw",
    "Move north": "move n",
    "Move west": "move w",
    "Move northeast": "move ne",
    "Move east": "move e",
    "Move southwest": "move sw",
    "Move south": "move s",
    "Move southeast": "move se",
    "Pause": "wait",
    "Wait for Several Minutes": "wait/rest",
    "Lua Console": "Lua console",
    "Reload Item": "reload",
    "Throw Item": "throw",
    "Open Inventory": "inventory",
    "Pick up items from all nearby tiles": "pick up all",
    "Ignore Nearby Enemy": "ignore foe",
    "Action Menu": "all actions",
    "Explore the nearest unexplored area": "auto-explore",
    "View Map": "map",
    "Examine Nearby Terrain": "tile actions",
    "View Help": "help",
    "Main Menu": "menu",
    "Fire Wielded Item": "attack",
    "Debug Menu": "debug",
    "Ascend stairs": "stairs up",
    "Descend stairs": "stairs down",
    "Keybindings": "all keys",
    "Take everything underfoot": "take all",
    "Body status": "body",
    "Smash Nearby Terrain": "smash/pulp",
}
ACTION_LABELS = {
    "cycle_move": "mode",
    "NEXT_TARGET": "next target",
    "PREV_TARGET": "prev target",
    "use_contextual": "use",
    "player_data": "character",
    "messages": "messages",
    "butcher": "butcher",
    "select_fire_mode": "fire mode",
    "advinv": "adv. inv.",
    "toggle_curtain": "curtain",
}
DIRECTIONS = ("n", "w", "s", "e", "nw", "ne", "sw", "se")
LOOK_ACTIONS = tuple(f"shift_{direction}" for direction in DIRECTIONS)
PEEK_ACTIONS = tuple(f"PEEK_{direction.upper()}" for direction in DIRECTIONS)


@dataclass(frozen=True)
class Key:
    label: str
    units: float = 1
    primary: str | None = None
    shift: str | None = None
    height: float = 1


def letters(text):
    return tuple(Key(ch, primary=ch.lower(), shift=ch) for ch in text)


ROWS = (
    tuple(Key(ch, primary=ch, shift=shift) for ch, shift in
          zip("`1234567890-=", '~!@#$%^&*()_+')) + (Key("Backspace", 2, "BACKSPACE"),),
    (Key("Tab", 1.5, "TAB", "BACKTAB"),) + letters("QWERTYUIOP")
    + (Key("[", primary="[", shift="{"), Key("]", primary="]", shift="}"),
       Key("\\", 1.5, "\\", "|")),
    (Key("Caps Lock", 1.75),) + letters("ASDFGHJKL")
    + (Key(";", primary=";", shift=":"), Key("'", primary="'", shift='"'),
       Key("Enter", 2.25, "RETURN")),
    (Key("Shift", 2.25),) + letters("ZXCVBNM")
    + (Key(",", primary=",", shift="<"), Key(".", primary=".", shift=">"),
       Key("/", primary="/", shift="?"), Key("Shift", 2.75)),
    (Key("Ctrl", 1.25), Key("Super", 1.25), Key("Alt", 1.25),
     Key("Space", 6.25, "SPACE", "SHIFT_SPACE"), Key("Alt", 1.25), Key("Super", 1.25),
     Key("Menu", 1.25), Key("Ctrl", 1.25)),
)
PITCH_X = 64
PITCH_Y = 76
GAP = 4


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def short_name(entry):
    return ACTION_LABELS.get(entry["id"], ABBREV.get(entry["name"], entry["name"]))


def load_entries():
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
            entries[entry["id"]] = {**entries.get(entry["id"], {}), **entry}
    return entries


def action_labels(key, keymap, entries):
    return [short_name(entries[action]) for action in keymap.get(key, [])
            if action not in LOOK_ACTIONS and action not in PEEK_ACTIONS]


def build_keymap(entries):
    keymap = {}
    for action_id, entry in entries.items():
        for binding in entry.get("bindings", []):
            if binding.get("input_method") == "keyboard":
                keymap.setdefault(binding["key"], []).append(action_id)
    return keymap




def render_svg(keymap, entries):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1270" '
        'viewBox="0 0 1000 1270" font-family="sans-serif" fill="currentColor">',
        '<title>Modern control families on a 104-key ANSI keyboard</title>',
        '<desc>Standard 15-unit ANSI main keyboard, including unbound keys and '
        'modifiers. Navigation, arrow and numpad clusters are shown below, not '
        'in their physical position to the right of the main keyboard. '
        'Enter opens all actions, inventory groups equipment and crafting, '
        'Space groups tile actions. Right-click selects; Ctrl-direction '
        'physically peeks with the normal cost. Classic controls are unchanged.</desc>',
        '<text x="20" y="32" font-size="25" font-weight="700">Modern controls</text>',
        '<text x="20" y="57" font-size="14">ANSI layout · action below each key · '
        '⇧ means Shift · direction modifiers are grouped in the legend</text>',
    ]
    add = lines.append
    conflicts = [(key, ids) for key, ids in keymap.items() if len(ids) > 1]
    arrows = {"UP": "aim north", "DOWN": "aim south",
              "LEFT": "aim west", "RIGHT": "aim east"}

    def draw_key(key, position):
        x, y = position
        width = key.units * PITCH_X - GAP
        height = key.height * PITCH_Y - GAP
        names = action_labels(key.primary, keymap, entries)
        shifted = action_labels(key.shift, keymap, entries)
        if key.primary in arrows:
            names = [arrows[key.primary]]
        conflict = len(names) > 1 or len(shifted) > 1
        color = "var(--error,currentColor)" if conflict else "currentColor"
        add(f'<g><rect x="{x}" y="{y}" width="{width}" height="{height}" '
            f'rx="5" fill="none" stroke="{color}" '
            f'stroke-width="{2 if names or shifted else 0.7}"/>')
        key_size = min(15, (width - 14) / max(len(key.label) * 0.6, 1))
        add(f'<text x="{x + 7}" y="{y + 21}" font-size="{key_size:.1f}" '
            f'font-weight="700">{esc(key.label)}</text>')
        for index, name in enumerate(names):
            font_size = max(9, min(12, (width - 10) / max(len(name) * 0.5, 1)))
            add(f'<text x="{x + 6}" y="{y + 40 + index * 14}" '
                f'font-size="{font_size:.1f}" fill="{color}">{esc(name)}</text>')
        for index, name in enumerate(shifted):
            label = "⇧ " + name
            chunks = wrap(label, width=max(8, int((width - 14) / 5)))
            for line_index, chunk in enumerate(chunks):
                add(f'<text x="{x + 6}" y="{y + 55 + index * 24 + line_index * 12}" '
                    f'font-size="10" fill="var(--muted,currentColor)">'
                    f'{esc(chunk)}</text>')
        add('</g>')

    draw_key(Key("Esc", primary="ESC"), (20, 84))
    for index in range(12):
        unit = 2 + index + 0.5 * (index // 4)
        draw_key(Key(f"F{index + 1}", primary=f"F{index + 1}"),
                 (20 + unit * PITCH_X, 84))
    for row_index, row in enumerate(ROWS):
        x = 20
        for key in row:
            draw_key(key, (x, 176 + row_index * PITCH_Y))
            x += key.units * PITCH_X

    add('<text x="20" y="585" font-size="16" font-weight="700">'
        'Separate clusters — shown below for readable labels</text>')
    for column, label in enumerate(("PrtSc", "Scroll Lock", "Pause")):
        draw_key(Key(label), (20 + column * PITCH_X, 610))
    for index, (label, primary) in enumerate((
            ("Insert", "INSERT"), ("Home", "HOME"), ("PgUp", "PPAGE"),
            ("Delete", "DELETE"), ("End", "END"), ("PgDn", "NPAGE"))):
        draw_key(Key(label, primary=primary),
                 (20 + index % 3 * PITCH_X, 686 + index // 3 * PITCH_Y))
    for label, primary, column, row in (
            ("↑", "UP", 1, 0), ("←", "LEFT", 0, 1),
            ("↓", "DOWN", 1, 1), ("→", "RIGHT", 2, 1)):
        draw_key(Key(label, primary=primary),
                 (290 + column * PITCH_X, 686 + row * PITCH_Y))

    for column, label in enumerate(("Num Lock", "/", "*", "−")):
        draw_key(Key(label), (660 + column * PITCH_X, 610))
    for row, digits in enumerate(("789", "456", "123"), start=1):
        for column, digit in enumerate(digits):
            draw_key(Key(digit, primary=f"NUMPAD_{digit}"),
                     (660 + column * PITCH_X, 610 + row * PITCH_Y))
    draw_key(Key("+", height=2), (852, 686))
    draw_key(Key("Enter", primary="RETURN", height=2), (852, 838))
    draw_key(Key("0", 2, "NUMPAD_0"), (660, 914))
    draw_key(Key(".", primary="NUMPAD_PERIOD"), (788, 914))

    def first_binding(action):
        bindings = [binding["key"] for binding in entries[action].get("bindings", [])
                    if binding.get("input_method") == "keyboard"]
        return bindings[0].replace("CTRL+", "Ctrl+").replace("RETURN", "Enter") if bindings else "(unbound)"

    peek_keys = " ".join(first_binding(action).removeprefix("Ctrl+") for action in PEEK_ACTIONS)
    legend = (
        'Select tile keys are unbound; right-click selects without spending time.',
        f'Ctrl + {peek_keys}: physical peek (200 moves); cancel returns.',
        'Arrows: free aim reticle. Tab / Shift+Tab: next / previous hostile.',
        'f attacks selection; guns use normal aim. Bump attacks still work.',
        f'{first_binding("wait")} waits/rests; Shift+X cycles walk/run/crouch/prone.',
        'Modern curses: Ctrl+C/Z are game chords, not quit/suspend signals.',
    )
    for index, note in enumerate(legend):
        add(f'<text x="20" y="{850 + index * 26}" font-size="13">{esc(note)}</text>')

    notes = (
        f'{first_binding("action_menu")}: all action groups; Info → character sheet and body/status screens.',
        f'{first_binding("use_contextual")}: use item by kind. Inventory: F5 crafts; Tab opens advanced inventory; Shift+Tab selects categories.',
        f'{first_binding("player_data")}: character; {first_binding("messages")}: messages; '
        f'{first_binding("butcher")}: butcher; {first_binding("select_fire_mode")}: fire mode; '
        f'{first_binding("advinv")}: advanced inventory.',
        'Space: nearby or selected-tile actions; a loaded trunk opens pickup. Shift+Space toggles curtains.',
        'RMB selects; Select tile keys are unbound by default; Jump and Smash require an explicit choice.',
        'Map RMB opens object actions without running one; closing keeps selection. Hostiles are only locked.',
        f'{first_binding("pickup")}: pick up a lone item or open the picker; {first_binding("pickup_list")}: pickup list; {first_binding("drop")}: drop.',
        'Menus: Space confirms the highlight; text spaces stay literal. Classic controls are unchanged.',
        'Classic terminal Ctrl+C/Z retain normal quit/suspend signal behavior.',
    )
    add('<text x="20" y="1024" font-size="16" font-weight="700">Compact action families</text>')
    for index, note in enumerate(notes):
        add(f'<text x="20" y="{1052 + index * 25}" font-size="14">{esc(note)}</text>')
    add('</svg>')
    return "\n".join(lines) + "\n", conflicts


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    entries = load_entries()
    keymap = build_keymap(entries)

    svg, conflicts = render_svg(keymap, entries)
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
