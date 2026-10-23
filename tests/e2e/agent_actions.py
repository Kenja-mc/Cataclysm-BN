"""Closed action lists for the agentic playtest: one screen, one set of real actions.

The decision model may only choose from these lists, so every action here is one the screen
really accepts:

* keys come from the shipped binding data, ``data/raw/keybindings/*.json`` overridden by
  ``data/raw/control_schemes/<scheme>.json``.  This fork ships only ``modern.json``; the base
  files are the classic layout, so an unbound action in a scheme is dropped instead of guessed.
* menu hotkeys and click targets are read out of the pane the game is showing right now, because
  uilist assigns those letters at draw time (``MENU_AUTOASSIGN`` in ``src/ui.cpp``).

``keys`` holds tmux key names (``k``, ``Escape``, ``C-x``, ``Space``).  ``agent_state.send_action``
translates them to X11 keysyms for the tiles build, so callers never translate anything.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYBINDING_DIR = ROOT / "data" / "raw" / "keybindings"
SCHEME_DIR = ROOT / "data" / "raw" / "control_schemes"
GLOBAL_CONTEXT = "default"  # the data files write the global context as "default" or omit it
MAX_MENU_ROWS = 14
MAX_LABEL = 72


@dataclass(frozen=True)
class ActionSpec:
    id: str                                  # stable id sent to the model, e.g. "move_north"
    label: str                               # one line the model reads
    keys: tuple[str, ...] = ()               # keys to send, e.g. ("k",) or ("Shift_L", "bracketright")
    click: tuple[int, int] | None = None     # mouse action for the tiles build


# ---------------------------------------------------------------- binding data

_TMUX_NAMES = {
    "RETURN": "Enter", "SPACE": "Space", "ESC": "Escape", "BACKTAB": "BTab", "TAB": "Tab",
    "PPAGE": "PageUp", "NPAGE": "PageDown", "BACKSPACE": "BSpace", "DELETE": "DC", "INSERT": "IC",
    "UP": "Up", "DOWN": "Down", "LEFT": "Left", "RIGHT": "Right", "HOME": "Home", "END": "End",
}

_X11_NAMES = {
    "Enter": "Return", "Space": "space", "Escape": "Escape", "Tab": "Tab", "BTab": "ISO_Left_Tab",
    "PageUp": "Prior", "PageDown": "Next", "BSpace": "BackSpace", "DC": "Delete", "IC": "Insert",
    "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right", "Home": "Home", "End": "End",
}


def tmux_key(key: str) -> str:
    """A data-file key name as tmux sends it (``CTRL+P`` -> ``C-p``, ``SPACE`` -> ``Space``)."""
    if len(key) == 1:
        return key
    if key.startswith("CTRL+"):
        rest = key[5:]
        return "C-" + (rest.lower() if len(rest) == 1 else tmux_key(rest))
    if key.startswith("ALT+"):
        rest = key[4:]
        return "M-" + (rest.lower() if len(rest) == 1 else tmux_key(rest))
    if key.startswith("NUMPAD_"):
        return "KP" + key[7:]
    return _TMUX_NAMES.get(key.upper(), key)


def x11_keys(keys: tuple[str, ...]) -> tuple[str, ...]:
    """The same keys as X11 keysyms; an uppercase letter becomes Shift plus the letter."""
    out: list[str] = []
    for key in keys:
        if len(key) == 1:
            if key.isupper() and key.isalpha():
                out += ["Shift_L", key.lower()]
            else:
                out.append(key)
        elif key.startswith("C-") and len(key) == 3:
            out += ["Control_L", key[2]]
        elif key.startswith("M-") and len(key) == 3:
            out += ["Alt_L", key[2]]
        else:
            out.append(_X11_NAMES.get(key, key))
    return tuple(out)


def _context(row: dict) -> str:
    return row.get("category") or GLOBAL_CONTEXT


@lru_cache(maxsize=None)
def _table(scheme: str) -> dict[tuple[str, str], tuple[tuple[str, ...], str]]:
    """(context, action id) -> (keys, name), with the control scheme applied over the base data."""
    table: dict[tuple[str, str], tuple[tuple[str, ...], str]] = {}
    for path in sorted(KEYBINDING_DIR.glob("*.json")):
        for row in json.loads(path.read_text()):
            if row.get("type") != "keybinding":
                continue
            keys = tuple(tmux_key(b["key"]) for b in row.get("bindings", [])
                         if b.get("input_method") == "keyboard" and b.get("key"))
            table[(_context(row), row["id"])] = (keys, row.get("name", row["id"]))
    scheme_file = SCHEME_DIR / f"{scheme}.json"
    if scheme_file.exists():
        for row in json.loads(scheme_file.read_text()):
            keys = tuple(tmux_key(b["key"]) for b in row.get("bindings", [])
                         if b.get("input_method") == "keyboard" and b.get("key"))
            table[(_context(row), row["id"])] = (keys, row.get("name", row["id"]))
    return table


def bound_keys(scheme: str, context: str, action: str) -> tuple[str, ...]:
    """Keys for one action in one context, falling back to the global context like input_context."""
    table = _table(scheme)
    for key in ((context, action), (GLOBAL_CONTEXT, action)):
        if key in table:
            return table[key][0]
    return ()


def bound_name(scheme: str, context: str, action: str) -> str:
    table = _table(scheme)
    for key in ((context, action), (GLOBAL_CONTEXT, action)):
        if key in table:
            return table[key][1]
    return action


def _arrow(keys: tuple[str, ...], name: str) -> tuple[str, ...]:
    """Prefer the arrow keysym: menus keep it in every scheme, scheme letters do not."""
    return (name,) if name in keys else keys[:1]


def _spec(action_id: str, label: str, keys: tuple[str, ...]) -> ActionSpec:
    return ActionSpec(action_id, label[:MAX_LABEL], keys)


# ---------------------------------------------------------------- screen text

_ROW_RE = re.compile(r"^[^\w]*[│|┃]\s*([0-9A-Za-z])\s+(\S.*?)\s*[│|┃]?\s*$")
_BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class Row:
    y: int
    x: int
    hotkey: str
    label: str


def _colored_chars(line: str) -> list[tuple[str, str]]:
    """Characters of one pane line with the ANSI color sequence that was active on each."""
    chars: list[tuple[str, str]] = []
    code = ""
    index = 0
    while index < len(line):
        match = _ANSI_RE.match(line, index)
        if match:
            code = match.group(0)
            index = match.end()
            continue
        chars.append((line[index], code))
        index += 1
    return chars


def colored_hotkey(colored_line: str, label: str) -> str:
    """The hotkey of a ``[New Game]`` style main-menu entry, read from its color.

    The main menu prints ``<N|n>ew Game`` as the whole label inside brackets with only the
    shortcut letter colorized, so a plain capture cannot show which letter it is.
    """
    chars = _colored_chars(colored_line)
    text = "".join(char for char, _code in chars)
    for match in _BRACKET_RE.finditer(text):
        inner = match.group(1)
        if not inner or label not in inner:
            continue
        codes = [code for char, code in chars[match.start() + 1:match.end() - 1]]
        if len(set(codes)) < 2:
            continue
        counts: dict[str, int] = {}
        for code in codes:
            counts[code] = counts.get(code, 0) + 1
        plain = max(counts, key=lambda code: counts[code])
        for (char, code), in zip(chars[match.start() + 1:match.end() - 1]):
            if code != plain and char.isalnum():
                return char
    return ""


def menu_rows(screen: str, limit: int = MAX_MENU_ROWS, colored: str = "") -> tuple[Row, ...]:
    """Hotkey rows of the menu on screen: uilist rows and the main menu's ``[New Game]`` form.

    ``colored`` is the same pane captured with ``capture-pane -e``; it is what makes the main
    menu's shortcut letters readable.
    """
    rows: list[Row] = []
    seen: set[str] = set()
    colored_lines = colored.splitlines()
    lines = screen.splitlines()
    frame = next(((y, match) for y, line in enumerate(lines)
                  if (match := _UILIST_TITLE_RE.search(line))), None)
    left, right, top, bottom = 0, None, -1, len(lines)
    if frame:
        top, title = frame
        left, right = title.start(), title.end() + 1
        bottom = next((y for y in range(top + 1, len(lines))
                       if lines[y][left:left + 1] in ("╰", "└", "+")
                       and lines[y][right - 1:right] in ("╯", "┘", "+")), len(lines))
    for y in range(top + 1, bottom):
        line = lines[y]
        match = _ROW_RE.match(line[left:right])
        if match:
            candidates = [(left + match.start(2), match.group(1),
                           re.split(r"[│|┃]", match.group(2))[0].strip())]
        else:
            # A titled menu owns its rectangle; background HUD/log text is not a menu row.
            if frame:
                continue
            # The main menu puts every entry on one line, each in its own bracket.
            candidates = [(bracketed.start(), colored_hotkey(colored_lines[y], bracketed.group(1))
                           if y < len(colored_lines) else "", bracketed.group(1).strip())
                          for bracketed in _BRACKET_RE.finditer(line)]
        for x, hotkey, label in candidates:
            if not hotkey or hotkey in seen or not label:
                continue
            seen.add(hotkey)
            rows.append(Row(y, x, hotkey, label[:MAX_LABEL]))
            if len(rows) >= limit:
                return tuple(rows)
    return tuple(rows)


_SCREEN_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("language_prompt", ("Select your language",)),
    ("death_choice", ("How should death work",)),
    ("welcome_card", ("Welcome to Bright Nights",)),
    ("world_gen", ("Finalize World",)),
    ("ingame_menu", ("MAIN MENU",)),
    ("create_character", ("Points left:",)),
    ("missions", ("ACTIVE MISSIONS",)),
    ("body_status", ("Bandages stop bleeding",)),
    ("options", ("[Interface]", "[Graphics]")),
    ("pickup", ("Pick up", "Weight")),
    ("item_actions", ("Store in inventory", "Drop item")),
    ("crafting", ("[f]ilter", "Missing:")),
    ("inventory", ("Inventory",)),
    ("look", ("Mouse View",)),
    ("map", (" - Create/Edit Note", " - List Notes")),
    ("action_menu", ("Interact…", "Inventory…")),
)

# Screens whose uilist title is the reliable marker, so a menu row that repeats the words
# ("Active World Mods" in the in-game main menu) cannot be mistaken for the screen itself.
_TITLE_RULES = (("world_mods", "World Mods"), ("ingame_menu", "MAIN MENU"))

_MAIN_MENU_MARKERS = ("[New Game]", "[MOTD]", "Tip of the day", "Cataclysm: Bright Nights")
_NEW_GAME_MARKERS = ("Custom Character", "Preset Character", "Defence mode", "Play Now!")
_FRAME_TITLE_RE = re.compile(r"[─-]{4,}\s*([^│|┃─-┤├┌┐└┘]{1,60}?)\s*[─-]{4,}")
_UILIST_TITLE_RE = re.compile(r"[╭┌+][─-]*<\s*([^<>│|┃]{1,60}?)\s*>[─-]{2,}")


def framed_title(screen: str) -> str:
    """Title of a menu frame, including top-aligned uilists.

    Explicit uilist title brackets distinguish menus from corner HUD boxes. Other frame titles
    still need to be in the middle band so ordinary corner readings do not become menus.
    """
    lines = screen.splitlines()
    if not lines:
        return ""
    for y, line in enumerate(lines):
        match = _UILIST_TITLE_RE.search(line)
        if match:
            return match.group(1).strip()
        if not 0.25 * len(lines) <= y <= 0.75 * len(lines):
            continue
        match = _FRAME_TITLE_RE.search(line)
        if match:
            return match.group(1).strip()
    return ""


def classify_screen(screen: str) -> str:
    """Name the screen the pane is showing: a state label, an open menu id, or "unknown"."""
    if not screen or not screen.strip():
        return "unknown"
    if _NEW_GAME_MARKERS[2] in screen or "Play Now!  (Default Scenario)" in screen:
        return "new_game_menu"
    title = framed_title(screen)
    for menu, prefix in _TITLE_RULES:
        if title.startswith(prefix):
            return menu
    if title.startswith("Actions"):
        return "action_menu"
    if title:
        return "menu"
    for menu, markers in _SCREEN_RULES:
        if all(marker in screen for marker in markers):
            return menu
    if any(marker in screen for marker in _MAIN_MENU_MARKERS):
        return "new_game_menu" if any(m in screen for m in _NEW_GAME_MARKERS) else "main_menu"
    from tmux_game import in_game  # local: keeps this module importable without the harness
    return "game" if in_game(screen) else "unknown"


# ---------------------------------------------------------------- action lists

# (action id, label, context, data action ids to try in order)
_GAME_ACTIONS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("move_north", "step north", "DEFAULTMODE", ("UP",)),
    ("move_south", "step south", "DEFAULTMODE", ("DOWN",)),
    ("move_west", "step west", "DEFAULTMODE", ("LEFT",)),
    ("move_east", "step east", "DEFAULTMODE", ("RIGHT",)),
    ("move_northwest", "step northwest", "DEFAULTMODE", ("LEFTUP",)),
    ("move_northeast", "step northeast", "DEFAULTMODE", ("RIGHTUP",)),
    ("move_southwest", "step southwest", "DEFAULTMODE", ("LEFTDOWN",)),
    ("move_southeast", "step southeast", "DEFAULTMODE", ("RIGHTDOWN",)),
    ("wait", "wait one turn", "DEFAULTMODE", ("pause",)),
    ("rest", "wait several minutes", "DEFAULTMODE", ("wait",)),
    ("inventory", "open the inventory", "DEFAULTMODE", ("inventory",)),
    ("action_menu", "open the action menu: every grouped action", "DEFAULTMODE", ("action_menu",)),
    ("interact", "interact with the selected or nearby tile", "DEFAULTMODE", ("examine",)),
    ("pickup", "pick up items", "DEFAULTMODE", ("pickup", "pickup_all")),
    ("pickup_all", "pick up from all nearby tiles", "DEFAULTMODE", ("pickup_all",)),
    ("look", "look around", "DEFAULTMODE", ("look",)),
    ("look_north", "look north", "DEFAULTMODE", ("shift_n",)),
    ("look_east", "look east", "DEFAULTMODE", ("shift_e",)),
    ("look_south", "look south", "DEFAULTMODE", ("shift_s",)),
    ("look_west", "look west", "DEFAULTMODE", ("shift_w",)),
    ("peek", "peek around a corner", "DEFAULTMODE", ("peek",)),
    ("peek_north", "peek north", "DEFAULTMODE", ("PEEK_N",)),
    ("peek_east", "peek east", "DEFAULTMODE", ("PEEK_E",)),
    ("peek_south", "peek south", "DEFAULTMODE", ("PEEK_S",)),
    ("peek_west", "peek west", "DEFAULTMODE", ("PEEK_W",)),
    ("craft", "open crafting", "DEFAULTMODE", ("craft",)),
    ("map", "view the map", "DEFAULTMODE", ("map",)),
    ("missions", "view missions", "DEFAULTMODE", ("missions",)),
    ("factions", "view factions", "DEFAULTMODE", ("factions",)),
    ("messages", "read the message log", "DEFAULTMODE", ("messages",)),
    ("morale", "view morale", "DEFAULTMODE", ("morale",)),
    ("player_info", "view player info", "DEFAULTMODE", ("player_data",)),
    ("bionics", "view or activate bionics", "DEFAULTMODE", ("bionics",)),
    ("mutations", "view or activate mutations", "DEFAULTMODE", ("mutations",)),
    ("fire", "fire the wielded item", "DEFAULTMODE", ("fire",)),
    ("cycle_stance", "cycle walk, run, crouch, prone", "DEFAULTMODE", ("cycle_move",)),
    ("auto_explore", "explore the nearest unexplored area", "DEFAULTMODE", ("auto_explore",)),
    ("open_door", "open a door", "DEFAULTMODE", ("open",)),
    ("close_door", "close a door", "DEFAULTMODE", ("close",)),
    ("smash", "smash nearby terrain", "DEFAULTMODE", ("smash",)),
    ("jump", "jump across an adjacent tile", "DEFAULTMODE", ("jump",)),
    ("wield", "wield an item", "DEFAULTMODE", ("wield",)),
    ("eat", "eat", "DEFAULTMODE", ("eat",)),
    ("read", "read", "DEFAULTMODE", ("read",)),
    ("drop", "drop an item", "DEFAULTMODE", ("drop",)),
    ("apply", "apply or use an item", "DEFAULTMODE", ("apply",)),
    ("advanced_inventory", "advanced inventory management", "DEFAULTMODE", ("advinv",)),
    ("save", "save and quit", "DEFAULTMODE", ("save",)),
    ("main_menu", "open the main menu", "DEFAULTMODE", ("main_menu",)),
)

_CRAFT_FALLBACK = ("i", "F5")  # modern: inventory, then the Craft hub command (INVENTORY/CRAFT)


def _game_actions(scheme: str) -> list[ActionSpec]:
    actions: list[ActionSpec] = []
    used: set[tuple[str, ...]] = set()
    for action_id, label, context, candidates in _GAME_ACTIONS:
        for candidate in candidates:
            keys = bound_keys(scheme, context, candidate)[:1]  # one key: aliases are alternatives
            if keys:
                if keys not in used:  # modern resolves pickup and pickup_all to the same key
                    actions.append(_spec(action_id, label, keys))
                    used.add(keys)
                break
        else:
            if action_id == "craft":
                actions.append(_spec("craft", "open the inventory, then crafting", _CRAFT_FALLBACK))
    return actions


_BORDER_CHARS = "│┃"  # box drawing only: ASCII art full of "|" must not read as a frame


def _frames(screen: str) -> list[tuple[int, int, int, set[int]]]:
    """Bordered frames as (row count, left column, right column, rows), innermost left border.

    A menu can overlap the sidebar (the inventory panel starts inside it), so each right border
    pairs with the nearest border column on its left: that is the frame's own left edge.
    """
    lines = screen.splitlines()
    columns: dict[int, set[int]] = {}
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char in _BORDER_CHARS:
                columns.setdefault(x, set()).add(y)
    frames: list[tuple[int, int, int, set[int]]] = []
    for right in sorted(columns):
        for left in sorted((c for c in columns if c < right), reverse=True):
            rows = columns[left] & columns[right]
            if len(rows) >= 3:
                frames.append((len(rows), left, right, rows))
                break
    return frames


def list_rows(screen: str, limit: int = MAX_MENU_ROWS) -> tuple[Row, ...]:
    """Content rows of the biggest bordered list on screen, hotkey or not.

    Clicks need these: the modern inventory assigns no invlets, so its rows carry no hotkey and
    the only way to pick one is to click it.  Keeping the frame with the most rows leaves the
    sidebar's rows out.
    """
    frames = _frames(screen)
    if not frames:
        return ()
    _count, left, right, rows = max(frames, key=lambda f: (f[0], f[2] - f[1]))
    lines = screen.splitlines()
    found: list[Row] = []
    for y in sorted(rows):
        line = lines[y]
        inner = line[left + 1:right]
        text = re.split(r"\s{3,}", inner.strip())[0].strip()  # two-column lists: first cell only
        if len(text) < 3 or set(text) <= set("─-=_ "):
            continue
        if text.isupper() and len(text) <= 24:
            continue  # column heading, not a row the game accepts a click on
        x = left + 1 + (len(inner) - len(inner.lstrip()))
        found.append(Row(y, x, "", text[:MAX_LABEL]))
        if len(found) >= limit:
            break
    return tuple(found)


# Screens whose mouse handling is verified: uilist rows (src/ui.cpp selects the row under the
# cursor in the modern scheme) and the fork's inventory (tests/e2e/inventory_mouse.py).  The title
# screen builds button rectangles but never reads them, so it gets keys only.
_CLICK_MENUS = frozenset({"ingame_menu", "action_menu", "inventory", "item_actions", "menu"})


def _menu_actions(scheme: str, text: str, mouse: bool, menu: str, colored: str = "") -> list[ActionSpec]:
    clicks = mouse and scheme == "modern" and menu in _CLICK_MENUS
    actions = [
        _spec("menu_up", "move the selection up", _arrow(bound_keys(scheme, "UILIST", "UP"), "Up")),
        _spec("menu_down", "move the selection down",
              _arrow(bound_keys(scheme, "UILIST", "DOWN"), "Down")),
        _spec("menu_select", "confirm the selected row", bound_keys(scheme, GLOBAL_CONTEXT, "CONFIRM")),
        _spec("menu_cancel", "close this screen", bound_keys(scheme, GLOBAL_CONTEXT, "QUIT")[:1]),
        _spec("menu_filter", "filter the list", bound_keys(scheme, GLOBAL_CONTEXT, "FILTER")[:1]),
        _spec("menu_page_up", "page up", bound_keys(scheme, GLOBAL_CONTEXT, "PAGE_UP")[:1]),
        _spec("menu_page_down", "page down", bound_keys(scheme, GLOBAL_CONTEXT, "PAGE_DOWN")[:1]),
    ]
    rows = menu_rows(text, colored=colored) if text and "\n" in text else ()
    hotkey_rows = {row.y for row in rows}
    for row in rows:
        actions.append(_spec(f"press_{row.hotkey}", f"press {row.hotkey}: {row.label}",
                             (row.hotkey,)))
        if clicks:
            actions.append(ActionSpec(f"click_{row.hotkey}", f"click the {row.label} row",
                                      (), (row.x, row.y)))
    if clicks and text and "\n" in text:
        listed = [row for row in list_rows(text) if row.y not in hotkey_rows]
        for row in listed:
            actions.append(ActionSpec(f"click_row_{row.y}", f"click the row: {row.label}",
                                      (), (row.x, row.y)))
        if menu in ("inventory", "item_actions"):
            for row in listed[:4]:
                actions.append(ActionSpec(f"secondary_click_row_{row.y}",
                                          f"right click the row for its item actions: {row.label}",
                                          (), (row.x, row.y)))
        # The tested way out of an item screen without a key: a right click on empty ground.
        actions.append(ActionSpec("secondary_click_outside", "right click outside the menu to close",
                                  (), (0, 0)))
    return [a for a in actions if a.keys or a.click]


def actions_for(screen: str, *, mode: str, scheme: str = "modern", mouse: bool = False,
                text: str | None = None, colored: str = "") -> tuple[ActionSpec, ...]:
    """The closed action list for one screen.

    ``screen`` is either a menu id from :func:`classify_screen` or the raw pane text, which is
    classified first.  ``text`` (defaults to ``screen`` when it looks like a pane) supplies the
    menu rows whose hotkeys and click targets exist only at draw time; ``colored`` is the same
    pane captured with colors, which the main menu needs for its shortcut letters.  The tiles
    build has no text channel, so it gets the gameplay keys only: no invented clicks.
    """
    menu = screen if screen in _KNOWN_MENUS else classify_screen(screen)
    pane = text if text is not None else (screen if "\n" in (screen or "") else "")
    if mode == "tiles":
        pane = text or ""
    if menu in ("game", "tutorial", "unknown"):
        return tuple(_game_actions(scheme))
    return tuple(_menu_actions(scheme, pane, mouse, menu, colored))


_KNOWN_MENUS = frozenset(
    [menu for menu, _ in _SCREEN_RULES]
    + ["main_menu", "new_game_menu", "game", "tutorial", "unknown", "menu"]
)
