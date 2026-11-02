"""Numbered list rows in the tiles build: 1-9 and 0 select visible rows; Enter confirms.

The fixture world is played by the curses build first: it carries ten distinct items and leaves
twenty-seven distinct kinds on the avatar's tile.  The curses inventory and pickup screens are read
only to record the real row order, so the tiles runs can assert which row a digit selected through
the saved player data instead of OCR.  The first pickup row is then topped up to five so the
''#' amount prompt can be checked.

`build_numbered_rows_world` prepares the `tiles.py` session; `run_numbered_rows` is its case.
"""
import json
import re
import time
from collections import Counter

from helpers import HELPERS, arena, empty_inventory, give, spawn
from numbered_menu_cases import Grid, bind_keys, read_player, save_and_quit, save_file, screen_size
from tmux_game import Game, start_new_game

MANIFEST = "numbered-rows-manifest.json"

# Ten carried rows: the digits address each one.
INVENTORY_ITEMS = ["rock", "pipe", "stick", "wrench", "crowbar",
                   "knife_combat", "machete", "hatchet", "shovel", "tshirt"]

# Ground rows, disjoint from the carried set so a pickup changes exactly one type.
PICKUP_ITEMS = ["hoe", "pickaxe", "screwdriver", "bat", "knife_steak", "fire_ax",
                "knife_butcher", "tongs", "boltcutters", "hacksaw", "scissors", "geiger_off",
                "flashlight", "lighter", "string_6", "rag", "leather", "nail", "matches",
                "whistle", "bone", "charcoal", "tinder", "paper", "thread", "wire", "spike"]

def pickup_page_size(count, rows):
    """The visible pickup rows: itemsH = min(25, TERMY / 2); list height = TERMY - (itemsH + 4)."""
    max_items = rows - (min(25, rows // 2) + 4)
    return max(9, min(count, max_items))


def _object_names(game, item_ids, source):
    """Map each spawned/created instance's real display name to its type id.

    Reading the instances (not fresh prototypes) matters: variants and charge-dependent names can
    differ from a prototype's name, which made one fixture row unmatchable.
    """
    wanted = set(item_ids)
    names = {}
    for raw in game.lua(source):
        item_id, _, name = raw.partition(" | ")
        if item_id not in wanted:
            continue
        name = re.sub(r"</?color[^>]*>", "", name)
        assert name, f"no display name for {item_id}"
        assert name not in names, f"two items are both named {name!r} ({names[name]} and {item_id})"
        names[name] = item_id
    missing = sorted(wanted - set(names.values()))
    assert not missing, f"these items were not created: {missing}"
    return names


def _rows_on_screen(game, names, first=0, count=None, columns=90):
    """Type ids in the order their display names appear on the screen, top to bottom.

    The scan stops left of the sidebar so the message log cannot stand in for a row, and pickup
    callers restrict it to the list rows so the selected item's description cannot either.
    """
    lines = game.screen().splitlines()
    found = []
    for line in lines[first:] if count is None else lines[first:first + count]:
        line = line[:columns]
        matches = [item_id for name, item_id in names.items()
                   if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", line, re.IGNORECASE)]
        assert len(matches) <= 1, f"one screen row names two fixture items: {line!r}"
        if matches and matches[0] not in found:
            found.append(matches[0])
    return found


def _pickup_order(game, names, window_rows=45):
    """The whole pickup list order, paging the curses menu so terminal size cannot shorten it.

    Returns the order and every screen read, so a missing row can be diagnosed from the actual
    menu rather than guessed at.
    """
    game.keys("C-g", delay=0.4)
    game.wait_for("Pick up", timeout=20)
    page_rows = pickup_page_size(len(names), window_rows)
    order = []
    screens = [game.screen()]
    for _ in range(10):
        for item_id in _rows_on_screen(game, names, first=1, count=page_rows):
            if item_id not in order:
                order.append(item_id)
        if len(order) >= len(names):
            break
        game.keys("Tab", delay=0.4)
        screens.append(game.screen())
    game.keys("Escape", delay=0.4)
    return order, screens


def _inventory_order(game, names):
    """The whole inventory row order; moving down scrolls the list past the window height."""
    game.keys("i", delay=0.6)
    game.wait_for("Inventory", timeout=20)
    cells = {}
    for row, line in enumerate(game.screen().splitlines()):
        for name, item_id in names.items():
            match = re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", line[:90], re.IGNORECASE)
            if match:
                cells[item_id] = [match.start() + 8, row]
    order = []
    for _ in range(len(names) * 3):
        for item_id in _rows_on_screen(game, names):
            if item_id not in order:
                order.append(item_id)
        if len(order) >= len(names):
            break
        game.keys("Down", delay=0.2)
    game.keys("Escape", delay=0.4)
    return order, cells


def build_numbered_rows_world(session):
    """Curses-built fixture: ten carried item rows and twenty-seven ground kinds, plus their order."""
    import subprocess

    import tiles

    tiles.tmux_game.ROOT = session.root
    columns, rows = screen_size()
    game = Game(name="bn-tiles-e2e-numbered-rows", userdir=session.curses_userdir,
                cols=columns, rows=rows,
                options={"SAFEMODE": "false", "INITIAL_TIME": "12", "CONTROL_SCHEME": "modern",
                         "SHOW_WELCOME": "false", "NEW_PICKUP_MENU": "false",
                         "PICKUP_POSITION": "left", "SIDEBAR_POSITION": "right"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        empty_inventory(game)
        arena(game)
        for item_id in INVENTORY_ITEMS:
            give(game, item_id)
        carried_names = _object_names(
            game, INVENTORY_ITEMS,
            "for _,it in ipairs(gapi.get_avatar():all_items(false)) do "
            "out(it:get_type():str()..' | '..it:display_name(1)) end")
        inventory_order, inventory_cells = _inventory_order(game, carried_names)
        for item_id in PICKUP_ITEMS:
            spawn(game, 0, 0, item_id)
        ground_names = _object_names(
            game, PICKUP_ITEMS,
            "for _,it in ipairs(M:get_items_at(here(0,0))) do "
            "out(it:get_type():str()..' | '..it:display_name(1)) end")
        pickup_order, pickup_screens = _pickup_order(game, ground_names, window_rows=rows)
        # One reachable non-charge stack so '#', 3 picks three separate items.
        count_index = next( index for index, item_id in enumerate( pickup_order[:9] )
                            if game.lua( "local it=gapi.create_item(ItypeId.new('" + item_id +
                                         "'),-1) out(it:is_stackable())" ) == ["false"] )
        for _ in range(4):
            spawn(game, 0, 0, pickup_order[count_index])
        rows = int(tiles.DETERMINISTIC_OPTIONS["TERMINAL_Y"])
        assert len(inventory_order) == len(INVENTORY_ITEMS), inventory_order
        assert sorted(inventory_order) == sorted(INVENTORY_ITEMS), inventory_order
        missing = sorted(set(PICKUP_ITEMS) - set(pickup_order))
        extra = sorted(set(pickup_order) - set(PICKUP_ITEMS))
        assert (len(pickup_order) == len(PICKUP_ITEMS) and not missing and not extra), (
            f"pickup rows {len(pickup_order)}/{len(PICKUP_ITEMS)}; missing={missing}; "
            f"extra={extra}; ground={ground_names}; order={pickup_order}; "
            f"screens={pickup_screens}")
        assert len(pickup_order) > pickup_page_size(len(pickup_order), rows), \
            "the pickup list must span more than one tiles page"
        assert game.lua("out(gdebug.save_game())") == ["true"], \
            "saving the fixture failed:\n" + game.screen()
        bind_keys(session, {"DEFAULTMODE": {"save": "F6"}})
        (session.artifacts / "numbered-rows-curses.txt").write_text(game.screen_colors())
        (session.artifacts / MANIFEST).write_text(json.dumps({
            "inventory": inventory_order,
            "third_inventory_cell": inventory_cells[inventory_order[2]],
            "pickup": pickup_order,
            "page_size": pickup_page_size(len(pickup_order), rows),
            "third_pickup_letter": pickup_screens[0].splitlines()[3][0],
            "count_index": count_index,
            "rows": rows,
        }, indent=2))
    finally:
        subprocess.run(["tmux", "kill-session", "-t", game.name],
                       stderr=subprocess.DEVNULL, check=False)
    saves = [p for p in (session.curses_userdir / "save").iterdir() if p.is_dir()]
    assert len(saves) == 1, f"expected one saved world, found {saves}"
    session.world = saves[0].name


def _carried_types(player):
    return sorted(item["typeid"] for item in player.get("inv", []))


def _worn_types(player):
    return sorted(item["typeid"] for item in player.get("worn", []))


def _wielded(player):
    return player.get("weapon", {}).get("typeid")


def _open_window(session):
    import tiles

    x11 = tiles.X11(session.display)
    window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
    tiles.require(window is not None, "game window disappeared")
    x11.focus_local(window, 40, 40)
    return x11, window


def _wait_turns(x11, turns=6, key="x"):
    """Advance the pickup activity to completion."""
    for _ in range(turns):
        x11.key(key, delay=0.35)


BASE_OPTIONS = {"CONTROL_SCHEME": "modern", "PICKUP_POSITION": "left",
                "SIDEBAR_POSITION": "right", "NEW_PICKUP_MENU": "false",
                "NUMBERED_LIST_ROWS": "true", "MODERN_LIST_MOUSE": "true",
                "MOUSE_MOVE": "false", "HIDE_CURSOR": "show"}


def _settle(session, window, label):
    """Wait until two consecutive captures match, so the next key hits the drawn menu."""
    import tiles

    dest = session.artifacts / f"{label}-settle.png"
    previous = None
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        tiles.capture(session.display, window, dest)
        data = tiles.frame_rgb(dest)
        if data == previous:
            return
        previous = data
        time.sleep(0.15)
    raise tiles.Failure(f"{label}: the menu never reached a still frame")


def _run(session, label, keys, observations, options=None, wait_turns=False):
    """Play one key script from the fixture save and return the saved player.

    Menu-opening and menu-closing keys settle before the next key: a fixed delay raced the
    item-action menu and left it open, so the save key never reached the map.
    """
    import tiles

    with session.running_game(label, {**BASE_OPTIONS, **(options or {})}) as live:
        x11, window = _open_window(session)
        try:
            for index, chord in enumerate(keys):
                if chord[0] == "double_click":
                    data = tiles.frame_rgb(live.frame)
                    grid = Grid(data, *screen_size())
                    x11.focus_local(window, *grid.centre(*chord[1:]))
                    x11.click(1, delay=0.06)
                    x11.click(1, delay=0.7)
                    _settle(session, window, f"{label}-{index}")
                    continue
                x11.key(*chord, delay=0.6)
                if "Return" in chord or "i" in chord or chord in (("Control_L", "g"), ("g",)):
                    _settle(session, window, f"{label}-{index}")
            if wait_turns:
                scheme = (options or {}).get("CONTROL_SCHEME", BASE_OPTIONS["CONTROL_SCHEME"])
                _wait_turns(x11, key="period" if scheme == "classic" else "x")
            save = save_file(live, session.world)
            save_and_quit(x11, save)
            player = read_player(save)
            observations[label] = {
                "weapon": _wielded(player),
                "carried": _carried_types(player),
            }
            return player
        finally:
            x11.close()


def _row_digit(row):
    """The key for a visible pickup row: 1-9, then 0 for the tenth."""
    return "0" if row == 10 else str(row)


def _pickup_keys(manifest, index, count=None):
    """Keys that take the pickup row at `index`, using digits and pages and an optional '#' count."""
    page_size = manifest["page_size"]
    page, row = divmod(index, page_size)
    assert row < 10, "the fixture only exercises rows 1-10"
    keys = [("Control_L", "g")]
    keys += [("Tab",)] * page
    keys.append((_row_digit(row + 1),))
    if count is not None:
        keys += [("Shift_L", "3"), (str(count),), ("Return",)]
    keys.append(("Return",))
    return keys


def run_numbered_rows(session):
    """Drive the number path in the tiles build and read the result from the save file."""
    manifest = json.loads((session.artifacts / MANIFEST).read_text())
    failures, observations = [], {}

    def inventory_run(label, digit, expected, **extra):
        player = _run(session, label, [("i",), (digit,), ("Return",), ("h",)],
                      observations, **extra)
        if _wielded(player) != expected:
            failures.append(f"{label}: digit {digit} did not select and wield {expected}: "
                            f"{observations[label]}")
        return player

    inventory_run("numbered-inventory-3", "3", manifest["inventory"][2])
    label = "numbered-inventory-double-click-3"
    player = _run(session, label,
                  [("i",), ("double_click", *manifest["third_inventory_cell"]), ("h",)],
                  observations)
    if _wielded(player) != manifest["inventory"][2]:
        failures.append(f"{label}: did not open and wield the third visible inventory row: "
                        f"{observations[label]}")
    inventory_run("numbered-inventory-0", "0", manifest["inventory"][9])
    # 6 and 4 fall back to RIGHT/LEFT in the default key context; numbers must win.
    inventory_run("numbered-inventory-6", "6", manifest["inventory"][5])

    # The item action menu is a uilist with its own input loop: row 5 is Wield.
    player = _run(session, "numbered-uilist-wield",
                  [("i",), ("Return",), ("5",), ("Return",)], observations)
    if _wielded(player) != manifest["inventory"][0]:
        failures.append("uilist row 5: a numbered uilist did not select and confirm Wield: "
                        f"{observations['numbered-uilist-wield']}")

    # Digit 4 is the row-number key that used to fall through to LEFT; row 4 is Wear.
    wear_index = manifest["inventory"].index("tshirt")
    player = _run(session, "numbered-uilist-wear",
                  [("i",), (_row_digit(wear_index + 1),), ("Return",), ("4",), ("Return",)],
                  observations)
    if "tshirt" not in _worn_types(player):
        failures.append("uilist row 4: digit 4 did not confirm Wear: "
                        f"{observations['numbered-uilist-wear']}")

    count_index = manifest["count_index"]
    player = _run(session, "numbered-pickup-count",
                  _pickup_keys(manifest, count_index, count=3), observations, wait_turns=True)
    expected = sorted(INVENTORY_ITEMS + [manifest["pickup"][count_index]] * 3)
    if _carried_types(player) != expected:
        failures.append("pickup '#': three of the counted row were not taken: "
                        f"{observations['numbered-pickup-count']}")

    player = _run(session, "numbered-pickup-0", _pickup_keys(manifest, 9), observations,
                  wait_turns=True)
    if _carried_types(player) != sorted(INVENTORY_ITEMS + [manifest["pickup"][9]]):
        failures.append("pickup row 10: digit 0 did not take the tenth row: "
                        f"{observations['numbered-pickup-0']}")

    expected_third = sorted(INVENTORY_ITEMS +
                            [manifest["pickup"][2]] * (5 if count_index == 2 else 1))
    for label, steps in (
            ("numbered-pickup-3", _pickup_keys(manifest, 2)),
            ("numbered-pickup-double-click-3", [("Control_L", "g"), ("double_click", 16, 3)]),
            ("numbered-pickup-letter-3",
             [("Control_L", "g"), (manifest["third_pickup_letter"],), ("Return",)])):
        player = _run(session, label, steps, observations, wait_turns=True)
        if _carried_types(player) != expected_third:
            failures.append(f"{label}: did not take exactly the third visible pickup row: "
                            f"{observations[label]}")
    player = _run(session, "numbered-classic-count",
                  [("g",), ("3",)] + [("Down",)] * count_index +
                  [("Right",), ("Return",)], observations,
                  options={"CONTROL_SCHEME": "classic"}, wait_turns=True)
    if _carried_types(player) != sorted(INVENTORY_ITEMS + [manifest["pickup"][count_index]] * 3):
        failures.append("Classic: digit 3 no longer supplies the pickup quantity: "
                        f"{observations['numbered-classic-count']}")

    page_size = manifest["page_size"]
    player = _run(session, "numbered-pickup-paged",
                  [("Control_L", "g"), ("Tab",), ("1",), ("Return",)], observations,
                  wait_turns=True)
    if _carried_types(player) != sorted(INVENTORY_ITEMS + [manifest["pickup"][page_size]]):
        failures.append("pickup after scrolling: digit 1 did not take row 1 of the second page: "
                        f"{observations['numbered-pickup-paged']}")


    # The new menu groups items differently. Arrow navigation supplies its actual third row.
    reference = _run(session, "numbered-new-pickup-arrow-reference",
                     [("Control_L", "g"), ("Down",), ("Down",), ("Return",)], observations,
                     options={"NEW_PICKUP_MENU": "true"}, wait_turns=True)
    taken = Counter(_carried_types(reference)) - Counter(INVENTORY_ITEMS)
    assert len(taken) == 1 and sum(taken.values()) >= 1, \
        f"the third-row reference did not take exactly one item kind: {taken}"
    new_third = next(iter(taken))
    player = _run(session, "numbered-new-pickup",
                  [("Control_L", "g"), ("3",), ("Return",)], observations,
                  options={"NEW_PICKUP_MENU": "true"}, wait_turns=True)
    if _carried_types(player) != _carried_types(reference):
        failures.append("new pickup: 3 + Enter did not take exactly the third visible row "
                        f"({new_third}): {observations['numbered-new-pickup']}")

    player = _run(session, "numbered-new-pickup-count",
                  [("Control_L", "g"), ("3",), ("Shift_L", "3"), ("1",), ("Return",), ("Return",)],
                  observations, options={"NEW_PICKUP_MENU": "true"}, wait_turns=True)
    if _carried_types(player) != sorted(INVENTORY_ITEMS + [new_third]):
        failures.append(f"new pickup '#': did not take exactly one {new_third}: "
                        f"{observations['numbered-new-pickup-count']}")

    # Option off: digits are unbound, so Enter opens the first row's item menu.
    player = _run(session, "numbered-option-off",
                  [("i",), ("3",), ("Return",), ("h",)], observations,
                  options={"NUMBERED_LIST_ROWS": "false"})
    if _wielded(player) != manifest["inventory"][0]:
        failures.append("number rows off: digit 3 still changed the selection: "
                        f"{observations['numbered-option-off']}")

    return failures, observations


def _type_ascii(x11, text):
    punctuation = {
        " ": ("space",), "'": ("apostrophe",), '"': ("Shift_L", "apostrophe"),
        "(": ("Shift_L", "9"), ")": ("Shift_L", "0"),
        ":": ("Shift_L", "semicolon"), ";": ("semicolon",), ",": ("comma",),
        ".": ("period",), "=": ("equal",), "-": ("minus",),
        "_": ("Shift_L", "minus"), "/": ("slash",), "\\": ("backslash",),
    }
    for char in text:
        chord = punctuation.get(char)
        if chord is None:
            chord = ("Shift_L", char.lower()) if char.isupper() else (char,)
        x11.key(*chord, delay=0.005)


def _settled_frame(session, label):
    import tiles

    return tiles.frame_rgb(session.artifacts / f"{label}-settle.png")


def _red_pixels(data):
    rgb = data[2]
    return sum(rgb[index] >= 120 and rgb[index + 1] * 3 < rgb[index] and
               rgb[index + 2] * 3 < rgb[index] for index in range(0, len(rgb), 3))


def _require_short_uilist(session, label, header_lines):
    import tiles

    grid = Grid(_settled_frame(session, label), *screen_size())
    # The repeated real header proves the UiList opened, not just a still Lua error/editor.
    for column in range(grid.columns - 5):
        mask = grid.mask(column, 1, 6)
        if sum(mask) <= grid.cell_height * 3:
            continue
        if all(grid.mask(column, row, 6) == mask for row in range(2, header_lines + 1)):
            return
    raise tiles.Failure(f"{label}: the three-row UiList did not open; inspect the capture "
                        "for a Lua runtime error or an editor that did not submit")


def run_numbered_viewport(session):
    """Digits may address only rows currently drawn, even when the list has more entries."""
    failures, observations = [], {}
    for digit, expected in (("0", "1"), ("3", "3")):
        label = "numbered-short-uilist-" + digit
        with session.running_game(label, BASE_OPTIONS) as live:
            x11, window = _open_window(session)
            try:
                header_lines = screen_size()[1] - 6
                script = (
                    "local menu=UiList.new() menu:title('Short viewport') "
                    f"menu:text(string.rep('Header\\n',{header_lines - 1})..'Header') "
                    "for i=1,12 do menu:add(i,'Choice '..i) end "
                    "gapi.get_avatar():set_value('numbered_viewport',tostring(menu:query()))"
                )
                path = session.artifacts / f"{label}.lua"
                path.write_text(script)
                x11.key("grave", delay=0.5)
                _settle(session, window, label + "-console")
                console_red = _red_pixels(_settled_frame(session, label + "-console"))
                x11.key("Return", delay=0.5)
                _settle(session, window, label + "-editor")
                _type_ascii(x11, script)
                x11.key("Control_L", "y", delay=0.7)
                _settle(session, window, label + "-visible")
                _require_short_uilist(session, label + "-visible", header_lines)
                x11.key(digit, delay=0.3)
                _settle(session, window, label + "-selected")
                x11.key("Return", delay=0.6)
                _settle(session, window, label + "-returned")
                returned_red = _red_pixels(_settled_frame(session, label + "-returned"))
                if returned_red > console_red + 20:
                    raise AssertionError(f"{label}: the Lua console returned an error; "
                                         "inspect the returned capture before attempting to save")
                x11.key("Escape", delay=0.5)
                save = save_file(live, session.world)
                save_and_quit(x11, save)
                chosen = read_player(save).get("values", {}).get("numbered_viewport")
                observations[label] = {"chosen": chosen, "expected": expected,
                                       "visible": str(session.artifacts / f"{label}-visible-settle.png")}
                if chosen != expected:
                    failures.append(f"{label}: Enter chose {chosen}, expected visible row {expected}")
            finally:
                x11.close()

    manifest = json.loads((session.artifacts / MANIFEST).read_text())
    player = _run(session, "numbered-short-pickup-0",
                  [("Control_L", "g"), ("0",), ("Return",)], observations,
                  options={"TERMINAL_X": "80", "TERMINAL_Y": "25"}, wait_turns=True)
    expected = sorted(INVENTORY_ITEMS +
                      [manifest["pickup"][0]] * (5 if manifest["count_index"] == 0 else 1))
    if _carried_types(player) != expected:
        failures.append("short pickup: 0 selected an invisible tenth row instead of leaving row 1: "
                        f"{observations['numbered-short-pickup-0']}")
    return failures, observations
