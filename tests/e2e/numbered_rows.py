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

from helpers import HELPERS, arena, empty_inventory, give, spawn
from numbered_menu_cases import bind_keys, read_player, save_and_quit, save_file
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
    game.keys("G", delay=0.4)
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
    order = []
    for _ in range(len(names) * 3):
        for item_id in _rows_on_screen(game, names):
            if item_id not in order:
                order.append(item_id)
        if len(order) >= len(names):
            break
        game.keys("Down", delay=0.2)
    game.keys("Escape", delay=0.4)
    return order


def build_numbered_rows_world(session):
    """Curses-built fixture: ten carried item rows and twenty-seven ground kinds, plus their order."""
    import subprocess

    import tiles

    tiles.tmux_game.ROOT = session.root
    game = Game(name="bn-tiles-e2e-numbered-rows", userdir=session.curses_userdir,
                options={"SAFEMODE": "false", "INITIAL_TIME": "12", "CONTROL_SCHEME": "modern",
                         "SHOW_WELCOME": "false"})
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
        inventory_order = _inventory_order(game, carried_names)
        for item_id in PICKUP_ITEMS:
            spawn(game, 0, 0, item_id)
        ground_names = _object_names(
            game, PICKUP_ITEMS,
            "for _,it in ipairs(M:get_items_at(here(0,0))) do "
            "out(it:get_type():str()..' | '..it:display_name(1)) end")
        pickup_order, pickup_screens = _pickup_order(game, ground_names)
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
            "pickup": pickup_order,
            "page_size": pickup_page_size(len(pickup_order), rows),
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


def _wait_turns(x11, turns=6):
    """Advance the pickup activity to completion; `x` is the Modern one-turn wait."""
    for _ in range(turns):
        x11.key("x", delay=0.35)


BASE_OPTIONS = {"CONTROL_SCHEME": "modern", "PICKUP_POSITION": "left",
                "SIDEBAR_POSITION": "right", "NEW_PICKUP_MENU": "false",
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
                x11.key(*chord, delay=0.6)
                if "Return" in chord or "i" in chord or chord == ("Shift_L", "g"):
                    _settle(session, window, f"{label}-{index}")
            if wait_turns:
                _wait_turns(x11)
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
    keys = [("Shift_L", "g")]
    keys += [("Tab",)] * page
    keys.append((_row_digit(row + 1),))
    if count is not None:
        keys += [("Shift_L", "3"), (str(count),), ("Return",)]
    keys.append(("Return",))
    return keys


def run_numbered_rows(session):
    """Drive the number path in the tiles build and read the result from the save file."""
    import tiles

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

    page_size = manifest["page_size"]
    player = _run(session, "numbered-pickup-paged",
                  [("Shift_L", "g"), ("Tab",), ("1",), ("Return",)], observations,
                  wait_turns=True)
    if _carried_types(player) != sorted(INVENTORY_ITEMS + [manifest["pickup"][page_size]]):
        failures.append("pickup after scrolling: digit 1 did not take row 1 of the second page: "
                        f"{observations['numbered-pickup-paged']}")


    # A numbered digit must select, not open a popup: with one Enter the menu must close.
    player = _run(session, "numbered-new-pickup",
                  [("Shift_L", "g"), ("3",), ("Return",)], observations,
                  options={"NEW_PICKUP_MENU": "true"}, wait_turns=True)
    if len(_carried_types(player)) != len(INVENTORY_ITEMS) + 1:
        failures.append("new pickup: a digit did not select and Enter did not take one row: "
                        f"{observations['numbered-new-pickup']}")

    player = _run(session, "numbered-new-pickup-count",
                  [("Shift_L", "g"), ("3",), ("Shift_L", "3"), ("1",), ("Return",), ("Return",)],
                  observations, options={"NEW_PICKUP_MENU": "true"}, wait_turns=True)
    if len(_carried_types(player)) != len(INVENTORY_ITEMS) + 1:
        failures.append("new pickup '#': the amount path did not take one row: "
                        f"{observations['numbered-new-pickup-count']}")

    # Option off: digits are unbound, so Enter opens the first row's item menu.
    player = _run(session, "numbered-option-off",
                  [("i",), ("3",), ("Return",), ("h",)], observations,
                  options={"NUMBERED_LIST_ROWS": "false"})
    if _wielded(player) != manifest["inventory"][0]:
        failures.append("number rows off: digit 3 still changed the selection: "
                        f"{observations['numbered-option-off']}")

    return failures, observations
