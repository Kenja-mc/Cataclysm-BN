"""Numbered mission list rows in the tiles build: 1-9 and 0 select a visible row, Enter activates it.

The curses build assigns a deterministic set of real, inert mission types to the avatar, then reads
the mission screen row by row: the details pane's name line and the offsets of every text line in
that pane.  The tiles runs therefore check what a digit really selected from two places instead of
OCR: the mission Enter made active in the saved player, and the rendered number gutter, row names
and details pane against that recorded layout.

`build_numbered_mission_world` prepares the `tiles.py` session; `run_numbered_mission` is its case.
"""
import json

from helpers import HELPERS
from tmux_game import Game, start_new_game

from numbered_menu_cases import bind_keys, read_player, require_menu, run_script, screen_size

MANIFEST = "numbered-missions-manifest.json"

# Real mission types whose `assign` starts nothing: no target, no deadline, no NPC and no world
# changes.  The items cannot be in a fresh shelter's crafting inventory, so `mission::process`
# never completes one on its own while the fixture waits.  Mixed goals keep the details pane
# varied: some only print a name, some add a folded description.
MISSIONS = [
    "MISSION_GET_BLACK_BOX",                  # find a black box (a vehicle part)
    "MISSION_GET_DEPUTY_BADGE",
    "MISSION_GET_FLAG",
    "MISSION_GET_CITY_COP_MOMENTO",
    "MISSION_OLD_GUARD_NEC_1",
    "MISSION_ISHERWOOD_LUKE_1",               # a book
    "MISSION_ISHERWOOD_LUKE_2",               # a book
    "MISSION_REFUGEE_Fatima_1",               # a holy book
    "MISSION_REFUGEE_Draco_GET_GUITAR",
    "MISSION_REFUGEE_Vanessa_1",
    "MISSION_RANCH_FOREMAN_15",               # a book
    "MISSION_RANCH_NURSE_5",
    "MISSION_RANCH_NURSE_9",
    "MISSION_RANCH_NURSE_10",
    "MISSION_RANCH_NURSE_11",
    "MISSION_ISHERWOOD_CARLOS_1",             # an anvil or bronze anvil
    "MISSION_GET_DRIVEBELTS",                 # drive belts
    "MISSION_NULL",                           # cannot complete at all
    "MISSION_OLD_GUARD_NEC_COMMO_2",          # computer toggle: needs step 1
    "MISSION_BUILD_CAMP_3",                   # condition: needs the mission giver
    "MISSION_PROVE_YOU_ARE_A_SURVIVOR",       # condition: needs the mission giver
    "MISSION_REFUGEE_Boris_CLEANUP",          # condition: needs the mission giver
    "MISSION_BEGGAR_2_PERMISSION",            # condition: needs the mission giver
    "MISSION_OLD_GUARD_NEC_COMMO_3",          # computer toggle: needs step 1
]

# The tiles mission window: new_centered_win( FULL_SCREEN_HEIGHT, FULL_SCREEN_WIDTH ), i.e. 24x80
# cells centred on the 132x50 terminal.  The list body and the details pane both start at window
# row 3, the divider is at window column 30 and the details pane is 80 - 33 = 47 cells wide.
WINDOW_COLUMNS = 80
WINDOW_ROWS = 24
LIST_TOP = 3
RULE_COLUMN = 30
DETAILS_LEFT = 31
DETAILS_COLUMNS = 47
# A two-cell gutter is reserved in front of the name, which keeps 28 - 2 = 26 cells.
NAME_COLUMN = 3
NAME_COLUMNS = 26
ROW_NUMBERS = 10                          # 1-9 address rows 1-9, 0 addresses row 10


# ---------------------------------------------------------------- curses fixture

def _assign_script(type_ids):
    """Lua that reserves, assigns and counts real mission instances in assignment order.

    A mission type that is not registered in this world would make reserve_new dereference a
    null type and crash. Validate the id first and report it instead.
    """
    ids = ", ".join(f"'{type_id}'" for type_id in type_ids)
    return (
        "local av=gapi.get_avatar() local bad={} "
        f"for _,id in ipairs({{{ids}}}) do "
        "local mid=MissionTypeIdRaw.new(id) "
        "if not mid:is_valid() then bad[#bad+1]=id "
        "else local m=Mission.reserve_new(mid, CharacterId.new(-1)) "
        "if m==nil then bad[#bad+1]=id..':null' else m:assign(av) end end end "
        "out(#av:get_active_missions()) "
        "out('invalid:'..table.concat(bad,','))"
    )


def _mission_window(screen):
    """The mission window's (column, row) origin, read from the tab strip it draws.

    draw_tab puts the first tab's corner at window column 2 and its text at column 3 on window
    row 1, so the tab text locates the window without assuming terminal sizes.
    """
    for row, line in enumerate(screen.splitlines()):
        column = line.find("ACTIVE MISSIONS")
        if column >= 3 and row >= 1:
            return column - 3, row - 1
    raise AssertionError(f"the mission screen is not open:\n{screen}")


def _detail_layout(screen):
    """The details pane's name line and the offsets of its non-empty lines."""
    lines = screen.splitlines()
    origin_x, origin_y = _mission_window(screen)
    rule = origin_x + RULE_COLUMN
    pane = []
    row = origin_y + LIST_TOP
    while row < len(lines) and rule < len(lines[row]) and lines[row][rule] == "\u2502":
        pane.append(lines[row][rule + 1:rule + 1 + DETAILS_COLUMNS])
        row += 1
    assert pane, f"the mission screen drew no details pane:\n{screen}"
    occupied = [offset for offset, text in enumerate(pane) if text.strip()]
    assert occupied and occupied[0] == 0, f"the details pane does not start with the name: {pane!r}"
    return pane[0].strip(), occupied


def _record_layouts(game, count):
    """Walk the real mission screen and read each row's details layout in list order."""
    game.keys("F8", delay=1.0)
    game.wait_for("ACTIVE MISSIONS", timeout=20)
    game.dismiss_error_popup()
    game.settle_screen(minimum=0.3)
    layouts = []
    for index in range(count):
        if index:
            game.keys("Down", delay=0.25)
            game.settle_screen(minimum=0.2)
        name, offsets = _detail_layout(game.screen())
        layouts.append((name, offsets))
    game.keys("Escape", delay=0.8)
    return layouts


def _curses_save(userdir, world):
    saves = list((userdir / "save" / world).glob("*.sav"))
    assert len(saves) == 1, f"expected one character save, found {saves}"
    return saves[0]


def build_numbered_mission_world(session):
    """Curses-built fixture: 24 assigned missions, plus their order and details layouts."""
    import subprocess

    import tiles

    tiles.tmux_game.ROOT = session.root
    # The Modern scheme leaves View Missions unbound; the fixture and the tiles runs need it.
    (session.curses_userdir / "config").mkdir(parents=True, exist_ok=True)
    bind_keys(session, {"DEFAULTMODE": {"save": "F6", "missions": "F8"}})
    game = Game(name="bn-tiles-e2e-numbered-missions", userdir=session.curses_userdir,
                options={"SAFEMODE": "false", "INITIAL_TIME": "12", "CONTROL_SCHEME": "modern",
                         "SHOW_WELCOME": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        game.dismiss_error_popup()
        assigned = []
        for start in range(0, len(MISSIONS), 8):
            result = game.lua(_assign_script(MISSIONS[start:start + 8]))
            expected = min(start + 8, len(MISSIONS))
            assigned, invalid = result if len(result) == 2 else (result, ["invalid:?"])
            assert invalid == "invalid:", \
                f"unregistered mission types {invalid}: {MISSIONS[start:start + 8]}\n{game.screen()}"
            assert assigned == [str(expected)], \
                f"assigning missions {start}..{expected} failed: {assigned}\n{game.screen()}"
        # Two turns run mission::process; a mission that can complete on its own would leave now.
        for _ in range(2):
            game.keys("x", delay=0.6)
        game.dismiss_error_popup()
        remaining = game.lua("out(#gapi.get_avatar():get_active_missions())")
        assert remaining == [str(len(MISSIONS))], \
            f"a fixture mission completed on its own: {remaining} of {len(MISSIONS)} remain\n" \
            + game.screen()
        layouts = _record_layouts(game, len(MISSIONS))
        assert game.lua("out(gdebug.save_game())") == ["true"], \
            "saving the fixture failed:\n" + game.screen()
        (session.artifacts / "numbered-missions-curses.txt").write_text(game.screen_colors())
    finally:
        subprocess.run(["tmux", "kill-session", "-t", game.name],
                       stderr=subprocess.DEVNULL, check=False)
    saves = [path for path in (session.curses_userdir / "save").iterdir() if path.is_dir()]
    assert len(saves) == 1, f"expected one saved world, found {saves}"
    session.world = saves[0].name

    player = read_player(_curses_save(session.curses_userdir, session.world))
    uids = player["active_missions"]
    assert len(uids) == len(MISSIONS), \
        f"the saved player lists {len(uids)} active missions, expected {len(MISSIONS)}"
    assert len(set(uids)) == len(uids), f"the saved player repeats a mission id: {uids}"
    assert player.get("active_mission") == uids[-1], \
        "assigning the last fixture mission did not leave it active"
    names = [name for name, _ in layouts]
    assert len(set(names)) == len(names), f"the fixture missions do not have distinct names: {names}"
    assert "Bugged mission type" not in names, \
        f"a fixture mission type is missing from the game data: {names}"
    for index, (name, offsets) in enumerate(layouts):
        assert offsets[0] == 0, f"row {index}: the details pane does not start with {name!r}: {offsets}"
        assert 1 not in offsets, f"row {index}: the mission name {name!r} wraps: {offsets}"
        assert offsets[-1] < WINDOW_ROWS - 1 - LIST_TOP, \
            f"row {index}: {name!r} needs rows {offsets}, which the tiles pane clips"
    manifest = {
        "missions": [{"type": type_id, "uid": uid, "name": name, "detail_rows": offsets}
                     for type_id, uid, (name, offsets) in zip(MISSIONS, uids, layouts)],
    }
    (session.artifacts / MANIFEST).write_text(json.dumps(manifest, indent=2))


# ---------------------------------------------------------------- tiles pixel helpers

class _Frame:
    """One decoded frame, addressed in the game's terminal cells."""

    def __init__(self, data, columns, rows):
        import tiles

        width, height, rgb = data
        tiles.require(width % columns == 0 and height % rows == 0,
                      f"the frame is {width}x{height}, not a whole {columns}x{rows} cell grid")
        self.width, self.height, self.rgb = width, height, rgb
        self.cell_width = width // columns
        self.cell_height = height // rows

    def cell_pixels(self, column, row):
        pixels = []
        for line in range(row * self.cell_height, (row + 1) * self.cell_height):
            base = line * self.width * 3 + column * self.cell_width * 3
            segment = self.rgb[base:base + self.cell_width * 3]
            pixels += [segment[offset:offset + 3] for offset in range(0, len(segment), 3)]
        return pixels

    def cell_mask(self, column, row):
        """The cell's glyph shape: pixels that differ from the cell's most common colour."""
        from collections import Counter

        pixels = self.cell_pixels(column, row)
        background = Counter(pixels).most_common(1)[0][0]
        return tuple(pixel != background for pixel in pixels)

    def ink(self, column, row, background):
        """Whether anything in the cell differs from the window background."""
        blank = background * self.cell_width
        for line in range(row * self.cell_height, (row + 1) * self.cell_height):
            base = line * self.width * 3 + column * self.cell_width * 3
            if self.rgb[base:base + len(blank)] != blank:
                return True
        return False

    def row_ink(self, row, first_column, last_column, background):
        """Which cells of a row differ from the window background."""
        blank = background * self.cell_width
        ink = [False] * (last_column - first_column)
        for line in range(row * self.cell_height, (row + 1) * self.cell_height):
            base = line * self.width * 3 + first_column * self.cell_width * 3
            segment = self.rgb[base:base + (last_column - first_column) * self.cell_width * 3]
            for index in range(len(ink)):
                if not ink[index]:
                    offset = index * self.cell_width * 3
                    ink[index] = segment[offset:offset + len(blank)] != blank
        return ink

    def span(self, row, first_column, last_column, background):
        """First and last painted column offsets in a row, or None when the row is blank."""
        painted = [index for index, painted in
                   enumerate(self.row_ink(row, first_column, last_column, background)) if painted]
        return (painted[0], painted[-1]) if painted else None


def _window_background(frame, origin):
    """The mission window's background colour, sampled right of the details pane."""
    import tiles

    pixels = frame.cell_pixels(origin[0] + WINDOW_COLUMNS - 2, origin[1] + LIST_TOP)
    tiles.require(len(set(pixels)) == 1,
                  f"the mission window's blank cell is not one colour: {set(pixels)}")
    return pixels[0]


def _page_rows(frame, origin, background):
    """How many list rows the window shows, read from the vertical divider it draws."""
    column = origin[0] + RULE_COLUMN
    count = 0
    for offset in range(LIST_TOP, WINDOW_ROWS - 1):
        if not frame.ink(column, origin[1] + offset, background):
            break
        count += 1
    return count


def _digit_shapes(frame, origin, count):
    return [frame.cell_mask(origin[0] + 1, origin[1] + LIST_TOP + offset) for offset in range(count)]


def _check_rows(frame, missions, first, count, origin, background, failures, label):
    """The names of missions[first:first + count] fill their rows; the gutter's gap stays blank."""
    for offset in range(count):
        index = first + offset
        row = origin[1] + LIST_TOP + offset
        span = frame.span(row, origin[0] + NAME_COLUMN, origin[0] + NAME_COLUMN + NAME_COLUMNS,
                          background)
        expected = min(len(missions[index]["name"]), NAME_COLUMNS)
        shown = None if span is None else span[1] + 1
        if shown != expected:
            failures.append(f"{label} row {offset + 1}: the name of mission {index} "
                            f"({missions[index]['name']!r}) fills {shown} cells, expected {expected}")
        if frame.ink(origin[0] + 2, row, background):
            failures.append(f"{label} row {offset + 1}: the number gutter's second cell is painted")


def _check_details(frame, missions, index, origin, background, failures, label):
    """The details pane shows mission `index`: its name and exactly its recorded line layout."""
    mission = missions[index]
    first_column = origin[0] + DETAILS_LEFT
    last_column = first_column + DETAILS_COLUMNS
    first_row = origin[1] + LIST_TOP
    span = frame.span(first_row, first_column, last_column, background)
    if span != (0, len(mission["name"]) - 1):
        failures.append(f"{label}: the details pane's name line is {span}, expected "
                        f"0..{len(mission['name']) - 1} for mission {index} "
                        f"({mission['name']!r})")
    painted = [offset for offset in range(WINDOW_ROWS - 1 - LIST_TOP)
               if frame.span(first_row + offset, first_column, last_column, background)]
    if painted != mission["detail_rows"]:
        failures.append(f"{label}: the details pane shows rows {painted}, expected "
                        f"{mission['detail_rows']} for mission {index} ({mission['name']!r})")


def _check_blank_rows(frame, origin, first, page, background, failures, label):
    """Rows after the page's last mission stay unpainted, gutter and name alike."""
    for offset in range(first, page):
        row = origin[1] + LIST_TOP + offset
        if frame.span(row, origin[0] + 1, origin[0] + NAME_COLUMN + NAME_COLUMNS, background):
            failures.append(f"{label} row {offset + 1}: a row past the last mission is painted")


def _check_numbering(frame, origin, shown, background, failures, label):
    """Rows 1..10 carry ten distinct digits; the rest of the page's gutter stays blank."""
    numbered = min(ROW_NUMBERS, shown)
    shapes = _digit_shapes(frame, origin, numbered)
    if any(not any(shape) for shape in shapes):
        failures.append(f"{label}: a numbered row drew no digit")
    if len(set(shapes)) != numbered:
        failures.append(f"{label}: the {numbered} numbered rows do not draw {numbered} digits")
    for offset in range(numbered, shown):
        row = origin[1] + LIST_TOP + offset
        if frame.ink(origin[0] + 1, row, background):
            failures.append(f"{label} row {offset + 1}: the gutter numbers a row past the tenth")
    return shapes


# ---------------------------------------------------------------- tiles case

def _active_missions(run, manifest, label, expected, failures, observations):
    """The save proves which row Enter confirmed, after rendering did its part."""
    import tiles

    uids = [mission["uid"] for mission in manifest["missions"]]
    tiles.require(run.player is not None, f"{label}: saving the character failed")
    player = run.player
    if player.get("active_missions") != uids:
        failures.append(f"{label}: the saved active mission list no longer matches the fixture")
    active = player.get("active_mission")
    if active != manifest["missions"][expected]["uid"]:
        failures.append(f"{label}: Enter did not activate mission {expected} "
                        f"({manifest['missions'][expected]['name']!r}), the save has {active}")
    observations[label] = {"active_mission": active,
                           "active_missions": player.get("active_missions")}


def run_numbered_mission(session):
    """Drive the number path of the mission list and read the result from the saved player."""
    import tiles

    manifest = json.loads((session.artifacts / MANIFEST).read_text())
    missions = manifest["missions"]
    columns, rows = screen_size()
    origin = ((columns - WINDOW_COLUMNS) // 2, (rows - WINDOW_ROWS) // 2)
    failures, observations = [], {}

    def frame(run, name):
        return _Frame(run.frames[name], columns, rows)

    first = run_script(session, "mission-digit-3",
                       [("key", "F8", 0.8), ("capture", "page-one"), ("key", "3"),
                        ("capture", "details-3"), ("key", "Return")], save=True)
    page_one = frame(first, "page-one")
    require_menu(first.frames, "mission-digit-3", "page-one")
    background = _window_background(page_one, origin)
    page = _page_rows(page_one, origin, background)
    tiles.require(page > ROW_NUMBERS,
                  f"the mission list shows {page} rows; the fixture needs more than ten")
    tiles.require(page < len(missions),
                  f"the fixture's {len(missions)} missions fit one page of {page} rows")
    observations["page_rows"] = page

    _check_rows(page_one, missions, 0, page, origin, background, failures, "page one")
    numbers = _check_numbering(page_one, origin, page, background, failures, "page one")
    _check_details(page_one, missions, 0, origin, background, failures, "page one")
    _check_details(frame(first, "details-3"), missions, 2, origin, background, failures, "digit 3")
    _active_missions(first, manifest, "digit 3", 2, failures, observations)

    # 0 is the tenth row; 6 is also the global RIGHT key, which must not switch tabs.
    second = run_script(session, "mission-digits-0-6",
                        [("key", "F8", 0.8), ("key", "0"), ("capture", "tenth"),
                         ("key", "6"), ("capture", "sixth"), ("key", "Return")], save=True)
    _check_details(frame(second, "tenth"), missions, 9, origin, background, failures, "digit 0")
    _check_details(frame(second, "sixth"), missions, 5, origin, background, failures, "digit 6")
    _active_missions(second, manifest, "digit 6", 5, failures, observations)

    # Scrolling: one Down per visible row lands on the second page, where digits count again.
    third = run_script(session, "mission-scrolled",
                       [("key", "F8", 0.8), ("keys", [("Down",)] * page),
                        ("capture", "page-two"), ("key", "3"),
                        ("capture", "scrolled-details"), ("key", "Return")], save=True)
    page_two = frame(third, "page-two")
    shown = len(missions) - page
    tiles.require(shown > 0, f"the fixture has no second page of {page} rows")
    _check_rows(page_two, missions, page, shown, origin, background, failures, "page two")
    _check_blank_rows(page_two, origin, shown, page, background, failures, "page two")
    restarted = _check_numbering(page_two, origin, shown, background, failures, "page two")
    shared = min(3, len(restarted), len(numbers))
    if restarted[:shared] != numbers[:shared]:
        failures.append("page two: the row numbers do not restart at one after scrolling")
    _check_details(page_two, missions, page, origin, background, failures, "page two")
    _check_details(frame(third, "scrolled-details"), missions, page + 2, origin, background,
                   failures, "scrolled digit 3")
    _active_missions(third, manifest, "scrolled digit 3", page + 2, failures, observations)

    # 8 is also the global UP key and the page has no eighth row: the selection must not move.
    fourth = run_script(session, "mission-scrolled-ignored",
                        [("key", "F8", 0.8), ("keys", [("Down",)] * page),
                         ("key", "8"), ("capture", "after-ignored"), ("key", "Return")], save=True)
    _check_details(frame(fourth, "after-ignored"), missions, page, origin, background, failures,
                   "out-of-range digit")
    _active_missions(fourth, manifest, "out-of-range digit", page, failures, observations)

    return failures, observations
