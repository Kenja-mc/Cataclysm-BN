import json
import shutil
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

SAVE_KEY = "F6"
OPTIONS_KEY = "F9"
CONSTRUCT_KEY = "F8"
FAVORITE_KEY = "F10"

FULL_SCREEN_WIDTH = 80
OPTIONS_TOOLTIP_ROWS = 4
OPTIONS_FOOTER_ROWS = 2
OPTIONS_LIST_FIRST_ROW = OPTIONS_TOOLTIP_ROWS + 2
OPTIONS_GUTTER_CELL = 1
OPTIONS_NAME_CELL = 5
OPTIONS_VALUE_CELL = 62
CONSTRUCTION_LIST_FIRST_ROW = 3
CONSTRUCTION_LIST_CELL = 1

BASE_OPTIONS = {
    "CONTROL_SCHEME": "modern",
    "MENU_SCROLL": "false",
    "NUMBERED_LIST_ROWS": "true",
    "HIDE_CURSOR": "show",
    "MOUSE_MOVE": "false",
    "SOUND_ENABLED": "true",
    "MUSIC_ENABLED": "true",
    "USE_METRIC_WEIGHTS": "kg",
}

DEFAULT_BINDINGS = {
    "DEFAULTMODE": {"save": SAVE_KEY, "construct": CONSTRUCT_KEY, "open_options": OPTIONS_KEY},
    "CONSTRUCTION": {"TOGGLE_FAVORITE": FAVORITE_KEY},
}


def bind_keys(session, bindings=None):
    wanted = DEFAULT_BINDINGS if bindings is None else bindings
    path = session.curses_userdir / "config" / "keybindings.json"
    rows = json.loads(path.read_text()) if path.exists() else []
    replaced = {(category, action) for category, actions in wanted.items() for action in actions}
    rows = [row for row in rows if (row.get("category"), row.get("id")) not in replaced]
    rows += [{"type": "keybinding", "id": action, "category": category,
              "bindings": [{"input_method": "keyboard", "key": key}]}
             for category, actions in wanted.items() for action, key in actions.items()]
    path.write_text(json.dumps(rows))


def screen_size():
    import tiles
    return (int(tiles.DETERMINISTIC_OPTIONS["TERMINAL_X"]),
            int(tiles.DETERMINISTIC_OPTIONS["TERMINAL_Y"]))


def frame(path):
    import tiles
    return tiles.frame_rgb(path)


class Grid:
    def __init__(self, data, columns, rows):
        import tiles
        self.width, self.height, self.rgb = data
        tiles.require(self.width % columns == 0 and self.height % rows == 0,
                      f"capture {self.width}x{self.height} is not a {columns}x{rows} cell grid")
        self.columns, self.rows = columns, rows
        self.cell_width = self.width // columns
        self.cell_height = self.height // rows
        tiles.require(self.cell_width >= 4 and self.cell_height >= 8,
                      f"implausible cell size {self.cell_width}x{self.cell_height}")

    def centre(self, column, row):
        return (column * self.cell_width + self.cell_width // 2,
                row * self.cell_height + self.cell_height // 2)

    def _pixels(self, row, first, last):
        for y in range(row * self.cell_height, (row + 1) * self.cell_height):
            for x in range(first * self.cell_width, last * self.cell_width):
                offset = 3 * (y * self.width + x)
                yield self.rgb[offset:offset + 3]

    def mask(self, column, row, cells=1):
        values = list(self._pixels(row, column, column + cells))
        background = Counter(values).most_common(1)[0][0]
        return bytes(value != background for value in values)

    def blank(self, column, row, cells=1):
        return not any(self.mask(column, row, cells))

    def has_text(self, row, first, last):
        values = list(self._pixels(row, first, last))
        background = Counter(values).most_common(1)[0][0]
        return any(value != background for value in values)

    def row_bytes(self, row, first, last):
        return b"".join(self._pixels(row, first, last))


def option_cells(columns=None, rows=None):
    if columns is None or rows is None:
        columns, rows = screen_size()
    width = max(FULL_SCREEN_WIDTH, columns // 2)
    left = (columns - width) // 2 + 1
    return {"gutter": left + OPTIONS_GUTTER_CELL,
            "name": left + OPTIONS_NAME_CELL,
            "value": left + OPTIONS_VALUE_CELL,
            "first_row": OPTIONS_LIST_FIRST_ROW,
            "height": rows - 3 - OPTIONS_TOOLTIP_ROWS - OPTIONS_FOOTER_ROWS}


def construction_cells(columns=None, rows=None):
    if columns is None or rows is None:
        columns, rows = screen_size()
    width = max(FULL_SCREEN_WIDTH, columns * 2 // 3)
    left = (columns - width) // 2 + CONSTRUCTION_LIST_CELL
    return {"gutter": left,
            "name": left + 2,
            "first_row": CONSTRUCTION_LIST_FIRST_ROW,
            "width": int(0.375 * width),
            "height": rows - 4}


def save_file(live, world):
    import tiles
    saves = list((live.run / "userdir" / "save" / world).glob("*.sav"))
    tiles.require(len(saves) == 1, f"expected one character save, found {saves}")
    return saves[0]


def read_player(save):
    return json.loads(Path(save).read_text().split("\n", 1)[1])["player"]


def read_uistate(live, world):
    return json.loads((live.run / "userdir" / "save" / world / "uistate.json").read_text())


def save_and_quit(x11, save, timeout=30):
    import tiles
    stamp = Path(save).stat().st_mtime_ns
    x11.key(SAVE_KEY, delay=0.7)
    x11.key("Left", delay=0.3)
    x11.key("Return", delay=0.8)
    deadline = time.monotonic() + timeout
    while Path(save).stat().st_mtime_ns == stamp and time.monotonic() < deadline:
        time.sleep(0.2)
    tiles.require(Path(save).stat().st_mtime_ns != stamp,
                  "save-and-quit did not write the character save")


class Launch:
    def __init__(self, session, live, x11, window, label):
        self.session, self.live, self.x11, self.window = session, live, x11, window
        self.label = label
        self.columns, self.rows = screen_size()
        self.captures = {}
        self.frames = {}
        self.map_frame = self.keep(live.frame, "map")
        self.grid = Grid(self.frames["map"], self.columns, self.rows)

    def keep(self, path, name):
        dest = self.session.artifacts / f"{self.label}-{name}.png"
        shutil.copy(path, dest)
        self.captures[name] = dest
        self.frames[name] = frame(dest)
        return dest

    def grid_for(self, name):
        return Grid(self.frames[name], self.columns, self.rows)

    def settle(self, name, minimum=0.4, timeout=10):
        import tiles
        dest = self.session.artifacts / f"{self.label}-{name}.png"
        previous, started = None, time.monotonic()
        while True:
            tiles.capture(self.session.display, self.window, dest)
            data = tiles.frame_rgb(dest)
            now = time.monotonic()
            if data == previous and now - started >= minimum:
                self.captures[name] = dest
                self.frames[name] = data
                return dest
            if now - started > timeout:
                raise tiles.Failure(f"{self.label}: {name} never reached a still frame")
            previous = data
            time.sleep(0.2)

    def same(self, first, second):
        return self.frames[first] == self.frames[second]

    def key(self, *chord, delay=0.5):
        self.x11.key(*chord, delay=delay)

    def keys(self, chords, delay=0.14):
        for chord in chords:
            self.x11.key(*chord, delay=delay)

    def hover(self, column, row, name, delay=0.35):
        self.x11.focus_local(self.window, *self.grid.centre(column, row))
        time.sleep(delay)
        return self.settle(name)

    def click(self, column, row, delay=0.4):
        self.x11.focus_local(self.window, *self.grid.centre(column, row))
        time.sleep(0.2)
        self.x11.click(1, delay=delay)


@contextmanager
def launch(session, label, options):
    import tiles
    with session.running_game(label, options) as live:
        x11 = tiles.X11(session.display)
        try:
            window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
            tiles.require(window is not None, f"{label}: the game window disappeared")
            x11.focus_local(window, 40, 40)
            time.sleep(0.5)
            yield Launch(session, live, x11, window, label)
        finally:
            x11.close()


class Run:
    def __init__(self, label, options, captures, frames, live, save=None, player=None):
        self.label, self.options = label, options
        self.captures, self.frames, self.live = captures, frames, live
        self.save, self.player = save, player


def run_script(session, label, steps, options=None, save=False):
    merged = {**BASE_OPTIONS, **(options or {})}
    with launch(session, label, merged) as live:
        for step in steps:
            kind = step[0]
            if kind == "key":
                chord = step[1] if isinstance(step[1], tuple) else (step[1],)
                live.key(*chord, delay=step[2] if len(step) > 2 else 0.5)
            elif kind == "keys":
                live.keys(step[1])
            elif kind == "hover":
                live.hover(step[1][0], step[1][1], step[2])
            elif kind == "click":
                live.click(step[1][0], step[1][1])
            elif kind == "capture":
                live.settle(step[1])
            else:
                raise AssertionError(f"unknown script step {kind!r}")
        saved = player = None
        if save:
            saved = save_file(live.live, session.world)
            save_and_quit(live.x11, saved)
            player = read_player(saved)
        return Run(label, merged, live.captures, live.frames, live.live, saved, player)


def require_menu(frames, label, name):
    import tiles
    base, menu = frames["map"], frames[name]
    tiles.require(base[:2] == menu[:2], f"{label}: the capture size changed with the menu")
    pixels = base[0] * base[1]
    changed = sum(1 for i in range(0, len(base[2]), 3) if base[2][i:i + 3] != menu[2][i:i + 3])
    tiles.require(changed * 100 >= pixels, f"{label}: {name} did not draw a menu over the map")


def check_gutter(failures, label, grid, column, row, count=10):
    masks = [grid.mask(column, row + offset) for offset in range(count)]
    if not all(any(mask) for mask in masks):
        failures.append(f"{label}: a numbered row has no digit in the gutter")
    if len(set(masks)) != count:
        failures.append(f"{label}: the ten visible row numbers are not ten distinct glyphs")
    if not grid.blank(column, row + count):
        failures.append(f"{label}: row {count + 1} still shows a row number")
    return masks


def favorites(live, world):
    return sorted(read_uistate(live, world).get("favorite_construct_recipes", []))


def _options_paths(live):
    return (live.run / "userdir" / "config" / "options.json",
            live.run / "xdg" / "cataclysm-bn" / "options.json")


def _read_all_options(live):
    values = {}
    for path in _options_paths(live):
        try:
            values[str(path)] = {row["name"]: row.get("value")
                                 for row in json.loads(path.read_text())}
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return values


def _changed_options(before, after):
    changes = {}
    for path, values in after.items():
        old = before.get(path, {})
        for name, value in values.items():
            if name in old and old[name] != value:
                changes[name] = value
    return changes


def run_numbered_options(session):
    bind_keys(session)
    failures, observations = [], {}
    layout = option_cells()
    name_cell = layout["name"] + 2

    with launch(session, "numbered-options-interface", BASE_OPTIONS) as live:
        before = _read_all_options(live.live)
        live.key(OPTIONS_KEY)
        live.settle("open")
        require_menu(live.frames, live.label, "open")
        live.key("Tab")
        live.settle("interface")
        require_menu(live.frames, live.label, "interface")
        live.keys([("Up",)] * 40)
        live.settle("top")
        top_grid = live.grid_for("top")
        check_gutter(failures, "options", top_grid, layout["gutter"], layout["first_row"])
        if not top_grid.blank(layout["gutter"] + 1, layout["first_row"] + 9):
            failures.append("options: the tenth row shows a two-digit number with row numbers on")

        live.hover(name_cell, layout["first_row"] + 2, "hover-row-3")
        live.hover(name_cell, layout["first_row"] + 9, "hover-row-10")
        if live.same("hover-row-3", "hover-row-10"):
            failures.append("options: hovering different rows left one row selected")
        live.hover(name_cell, layout["first_row"] + 2, "hover-row-3-fresh")
        live.hover(name_cell, layout["first_row"] + 5, "before-digit-3")
        live.key("3")
        live.settle("digit-3")
        if not live.same("digit-3", "hover-row-3-fresh"):
            failures.append("options: digit 3 did not select the row the pointer names 3")
        live.hover(name_cell, layout["first_row"] + 9, "hover-row-10-fresh")
        live.hover(name_cell, layout["first_row"] + 2, "before-digit-0")
        live.key("0")
        live.settle("digit-0")
        if not live.same("digit-0", "hover-row-10-fresh"):
            failures.append("options: digit 0 did not select the tenth visible row")
        if live.same("digit-0", "hover-row-3-fresh"):
            failures.append("options: digit 0 left the third row selected")

        live.key("Left", delay=0.5)
        live.settle("changed")
        live.keys([("Down",)] * 45)
        live.settle("scrolled")
        scrolled_grid = live.grid_for("scrolled")
        content = (layout["name"] + 3, layout["value"] - 2)
        text_rows = [index for index in range(10)
                     if scrolled_grid.has_text(layout["first_row"] + index, *content)]
        if len(text_rows) < 2:
            failures.append(f"options: the scrolled window shows {len(text_rows)} option rows")
        else:
            middle = text_rows[len(text_rows) // 2]
            digit = "0" if middle + 1 == 10 else str(middle + 1)
            live.hover(name_cell, layout["first_row"] + (text_rows[-1]), "hover-scrolled-other")
            live.hover(name_cell, layout["first_row"] + middle, "hover-scrolled-row")
            live.hover(name_cell, layout["first_row"] + text_rows[-1], "before-digit-scrolled")
            live.key(digit)
            live.settle("digit-scrolled")
            if not live.same("digit-scrolled", "hover-scrolled-row"):
                failures.append(f"options: digit {digit} did not select the row the pointer "
                                "picks after scrolling")
            if live.same("digit-scrolled", "hover-scrolled-other"):
                failures.append(f"options: digit {digit} selected another visible row after "
                                "scrolling")
        live.key("Escape")
        live.settle("prompt")
        live.key("Left")
        live.key("Return")
        live.settle("closed")
        changes = _changed_options(before, _read_all_options(live.live))
        if len(changes) != 1:
            failures.append(f"options: the tenth row did not change exactly one option: {changes}")
        observations["interface"] = {
            "scrolled_text_rows": [index + 1 for index in text_rows],
            "changes": changes,
            "captures": {k: str(v) for k, v in live.captures.items()},
        }

    off = {**BASE_OPTIONS, "NUMBERED_LIST_ROWS": "false"}
    with launch(session, "numbered-options-off", off) as live:
        before = _read_all_options(live.live)
        live.key(OPTIONS_KEY)
        live.settle("open")
        require_menu(live.frames, live.label, "open")
        live.key("Tab")
        live.settle("interface")
        require_menu(live.frames, live.label, "interface")
        top_grid = live.grid_for("interface")
        if top_grid.blank(layout["gutter"] + 1, layout["first_row"] + 9):
            failures.append("options off: the tenth row has no second number digit")
        live.hover(name_cell, layout["first_row"] + 5, "hover-row-6")
        live.key("5")
        live.settle("digit-5")
        if not live.same("digit-5", "hover-row-6"):
            failures.append("options off: digit 5 moved the selection with row numbers off")
        live.keys([("Down",)] * 45)
        live.settle("scrolled")
        scrolled_grid = live.grid_for("scrolled")
        if scrolled_grid.mask(layout["gutter"], layout["first_row"] + 1) == \
                top_grid.mask(layout["gutter"], layout["first_row"] + 1):
            failures.append("options off: row 2 kept its absolute number after scrolling")
        live.key("Escape")
        live.settle("closed")
        changes = _changed_options(before, _read_all_options(live.live))
        if changes:
            failures.append(f"options off: the pass changed {changes}")
        observations["off"] = {"changes": changes,
                               "captures": {k: str(v) for k, v in live.captures.items()}}
    return failures, observations


def _construction_pass(session, label, steps, options=None):
    run = run_script(session, label, [("key", CONSTRUCT_KEY, 0.8), ("capture", "open")] + steps,
                     options=options, save=True)
    require_menu(run.frames, run.label, "open")
    return run, favorites(run.live, session.world)


def run_numbered_construction(session):
    bind_keys(session)
    failures, observations = [], {}
    layout = construction_cells()
    click_column = layout["gutter"] + 4
    first = layout["first_row"]

    pointer_run, pointer = _construction_pass(session, "numbered-construction-pointer", [
        ("click", (click_column, first + 0)), ("key", FAVORITE_KEY, 0.5),
        ("click", (click_column, first + 1)), ("key", FAVORITE_KEY, 0.5),
        ("click", (click_column, first + 9)), ("key", FAVORITE_KEY, 0.5),
        ("key", "Escape", 0.8), ("capture", "closed"),
    ])
    check_gutter(failures, "construction", Grid(pointer_run.frames["open"],
                                               *(screen_size())),
                 layout["gutter"], first)

    digit_run, digits = _construction_pass(session, "numbered-construction-digits", [
        ("key", "1", 0.5), ("key", FAVORITE_KEY, 0.5),
        ("key", "2", 0.5), ("key", FAVORITE_KEY, 0.5),
        ("key", "0", 0.5), ("key", FAVORITE_KEY, 0.5),
        ("click", (click_column, first + 4)), ("capture", "pointer-row-5"),
        ("click", (click_column, first + 2)),
        ("key", "5", 0.5), ("capture", "digit-5"),
        ("key", "Escape", 0.8), ("capture", "closed"),
    ])
    frames = digit_run.frames
    if frames["digit-5"] != frames["pointer-row-5"]:
        failures.append("construction: digit 5 did not select the row the pointer names 5")
    if len(pointer) != 3:
        failures.append(f"construction: clicking three rows favorited {pointer}")
    if sorted(digits) != sorted(pointer):
        failures.append("construction: digits 1, 2 and 0 favorited "
                        f"{digits}, the pointer selected {pointer}")
    observations["digits"] = {"pointer": pointer, "digits": digits,
                              "captures": {k: str(v) for k, v in digit_run.captures.items()}}

    pointer_scrolled_run, pointer_scrolled = _construction_pass(
        session, "numbered-construction-pointer-scrolled", [
            ("keys", [("Down",)] * 50), ("capture", "scrolled"),
            ("click", (click_column, first + 1)), ("key", FAVORITE_KEY, 0.5),
            ("key", "Escape", 0.8), ("capture", "closed"),
        ])
    digit_scrolled_run, digits_scrolled = _construction_pass(
        session, "numbered-construction-digits-scrolled", [
            ("keys", [("Down",)] * 50), ("capture", "scrolled"),
            ("key", "2", 0.5), ("key", FAVORITE_KEY, 0.5),
            ("key", "Escape", 0.8), ("capture", "closed"),
        ])
    if sorted(digits_scrolled) != sorted(pointer_scrolled):
        failures.append("construction: after scrolling, digit 2 favorited "
                        f"{digits_scrolled}, the pointer selected {pointer_scrolled}")
    if not pointer_scrolled:
        failures.append("construction: no construction was favorited after scrolling")
    elif set(pointer_scrolled) & set(pointer):
        failures.append("construction: scrolling did not move row 2 to another construction")
    frames = digit_scrolled_run.frames
    top_grid = Grid(frames["open"], *(screen_size()))
    scrolled_grid = Grid(frames["scrolled"], *(screen_size()))
    if scrolled_grid.mask(layout["gutter"], first + 1) != top_grid.mask(layout["gutter"], first + 1):
        failures.append("construction: row 2 is not numbered 2 again after scrolling")
    content = (layout["name"], layout["gutter"] + layout["width"])
    if scrolled_grid.row_bytes(first + 5, *content) == top_grid.row_bytes(first + 5, *content):
        failures.append("construction: the sixth visible row kept its text after scrolling")
    observations["scrolled"] = {"pointer": pointer_scrolled, "digits": digits_scrolled,
                                "captures": {k: str(v) for k, v in frames.items()}}

    off = {**BASE_OPTIONS, "NUMBERED_LIST_ROWS": "false"}
    gate_steps = [
        ("key", "3", 0.5), ("key", FAVORITE_KEY, 0.5),
        ("click", (click_column, first + 1)), ("key", FAVORITE_KEY, 0.5),
        ("key", "Escape", 0.8), ("capture", "closed"),
    ]
    _, gate_off = _construction_pass(session, "numbered-construction-off", gate_steps, options=off)
    _, gate_base = _construction_pass(session, "numbered-construction-off-base",
                                      gate_steps[1:], options=off)
    if sorted(gate_off) != sorted(gate_base):
        failures.append("construction off: an unbound digit changed the selection: "
                        f"{gate_off} vs baseline {gate_base}")
    observations["gate"] = {"off": gate_off, "baseline": gate_base}
    return failures, observations


def run_numbered_menu(session):
    bind_keys(session)
    failures, observations = [], {}
    for name, runner in (("options", run_numbered_options),
                         ("construction", run_numbered_construction)):
        case_failures, case_observations = runner(session)
        failures += case_failures
        observations[name] = case_observations
    return failures, observations
