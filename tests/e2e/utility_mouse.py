"""Modern scheme mouse support in the utility menus.

Real UI assertions on the auto pickup rules list (rows, columns, tabs, header
labels, scrollbar arrows and track, wheel, and the first click only selecting a
row while a second click on it runs Enter) and on the Lua console / string
editor (text entry survives clicks, scrollbar clicks only scroll).

Smoke recipes for the consumers without a dedicated test (Esc opens the
in-game menu that lists every manager with a hotkey):

- Auto notes ("8 Autonotes manager"): with at least two discovered map extras,
  click a row: the yellow ">>" moves.  Click the scrollbar track: the selection
  jumps to the clicked part.  Click the header "<S>witch": the
  "Auto notes enabled:" value flips True/False.
- Colors ("b Color manager"): click a color name row to select it, click a
  cell right of the column separator at x=48 to select the Invert column,
  click the scrollbar to move the selection.  Enter must still open the picker
  for the clicked column only.
- Distractions manager ("0 Distractions manager"): click a row to select it,
  click the scrollbar arrows to move one row, Enter still toggles the selected
  distraction.
- Safemode manager ("9 Safe Mode manager"): click "[<Character>]" to switch
  tabs, click a rule cell to select that rule and column, click the scrollbar,
  click "<S>witch" to flip "Safe Mode enabled:".
"""
import json
import re
import time

from tmux_game import Game, start_new_game


def open_manager(g, label, title):
    """Open the named manager using the menu's displayed keyboard hotkey."""
    deadline = time.time() + 15
    while "MAIN MENU" not in g.screen():
        assert time.time() < deadline, "Esc should open the in-game menu\n" + g.screen()
        g.keys("Escape", delay=0.3)
    screen = g.screen()
    match = re.search(r"│\s+(\S)\s+" + re.escape(label) + r"\s+│", screen)
    assert match, f"no menu entry for {label!r}\n{screen}"
    g.keys(match.group(1), delay=1)
    g.wait_for(title, timeout=10)


def marker_row(g, text=">>"):
    """Screen row of the selection marker, or None."""
    for y, line in enumerate(g.screen().splitlines()):
        if text in line:
            return y
    return None


def marker_rule(g):
    """1-based index of the rule carrying the selection marker, or None."""
    for line in g.screen().splitlines():
        if ">>" in line:
            match = re.search(r"rule(\d+)", line)
            assert match, f"marker row without a rule: {line!r}"
            return int(match.group(1))
    return None


def wait_marker(g, rule, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if marker_rule(g) == rule:
            return
        time.sleep(0.1)
    raise AssertionError(f"the selection never reached rule{rule:03d}\n{g.screen()}")


def seed_rules(g, count):
    path = g.userdir / "config" / "auto_pickup.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([
        {"rule": f"rule{i:03d}", "active": True, "exclude": False}
        for i in range(1, count + 1)
    ]))


def test_autopickup_clicks_select_rows_columns_tabs_and_switch(_g):
    g = Game(name="bn-e2e-utility-apu", cols=80, rows=25)
    try:
        seed_rules(g, 30)
        start_new_game(g)
        open_manager(g, "Autopickup manager", "AUTO PICKUP MANAGER")
        screen = g.screen()
        assert "AUTO PICKUP MANAGER" in screen, screen
        # 30 rules in 19 visible rows: the scrollbar is drawn with its arrows
        # at screen rows 5 and 23, and the selection starts at rule 1.
        assert marker_rule(g) == 1, f"the first rule should carry the selection marker\n{screen}"

        # Down arrow click moves the selection one row.
        g.click(0, 23)
        wait_marker(g, 2)

        # Track click jumps to the clicked part of the list.
        g.click(0, 14)
        wait_marker(g, 11)
        assert "Pickup Rule:" not in g.screen(), \
            "a scrollbar click must not open the rule editor\n" + g.screen()

        # A wheel notch moves the selection one row, like the arrow click.
        y = marker_row(g)
        g.type(f"\x1b[<65;21;{y + 1}M", delay=1)
        wait_marker(g, 12)

        # Clicking a rule text cell selects that row and the rule column...
        g.click(10, 8)
        wait_marker(g, 6)
        g.keys("Enter", delay=1)
        assert "Pickup Rule:" in g.screen(), \
            "Enter on the rule column must open the rule editor\n" + g.screen()
        assert "rule006" in g.screen(), "the clicked row must be the edited rule\n" + g.screen()
        g.keys("Escape", delay=1)
        g.wait_gone("Pickup Rule:", timeout=10)

        # ...clicking the I/E cell selects the exclude/include column instead.
        g.click(55, 8)
        wait_marker(g, 4)
        g.keys("Enter", delay=1)
        line = next(l for l in g.screen().splitlines() if "rule004" in l)
        assert "Exclude" in line, f"Enter on the I/E column must toggle the clicked rule\n{g.screen()}"

        # Clicking the character tab switches to the (empty) character list...
        if "[Character]" in g.screen():
            g.click(30, 3)
            screen = g.screen()
            assert ">>" not in screen and "rule001" not in screen, \
                "the character tab must show its own empty rules\n" + screen
            # ...and back.
            g.click(20, 3)
            wait_marker(g, 1)

        # Clicking the header switch flips the global auto pickup option.
        def switch_value():
            return re.search(r"(True|False)", g.screen().splitlines()[2]).group(1)
        before = switch_value()
        g.click(64, 2)
        assert switch_value() != before, "the <S>witch click must flip the global option\n" + g.screen()
        g.click(64, 2)
        assert switch_value() == before, "the <S>witch click must flip the global option back\n" + g.screen()

        # Keyboard still works after all the clicks.
        g.keys("Down", delay=0.5)
        wait_marker(g, 2)

        # The row the keyboard already selected still needs a full click pair:
        # the first click must not activate it.
        g.click(10, 6)
        wait_marker(g, 2)
        assert "Pickup Rule:" not in g.screen(), \
            "a single click must not activate the keyboard selected row\n" + g.screen()

        # A second click on the same row runs Enter and opens the rule editor.
        g.click(10, 6)
        g.wait_for("Pickup Rule:", timeout=10)
        assert "rule002" in g.screen(), f"the double clicked row must be edited\n{g.screen()}"
        g.keys("Escape", delay=1)
        g.wait_gone("Pickup Rule:", timeout=10)

        # Clicking another row between the clicks starts a new pair.
        g.click(10, 11)
        wait_marker(g, 7)
        assert "Pickup Rule:" not in g.screen(), \
            "a click on a different row must not activate the previous one\n" + g.screen()

        # The visible "<A>dd" label opens the same prompt as the keyboard.
        g.click(2, 1)
        g.wait_for("Pickup Rule:", timeout=10)
        g.keys("Escape", delay=1)
        g.wait_gone("Pickup Rule:", timeout=10)

        # The visible "<R>emove" label drops the selected rule.
        g.click(10, 1)
        deadline = time.time() + 5
        while time.time() < deadline and "rule007" in g.screen():
            time.sleep(0.1)
        assert "rule007" not in g.screen(), \
            "the remove label must drop the selected rule\n" + g.screen()

        g.keys("Escape", delay=1)
        if "Save changes?" in g.screen():
            g.keys("Escape", delay=0.5)
        g.wait_gone("AUTO PICKUP MANAGER", timeout=10)
    finally:
        g.close()


def open_console(g):
    for _ in range(3):
        g.keys("`", delay=0)
        try:
            g.wait_for("to enter/edit command", timeout=15)
            return
        except AssertionError:
            g.keys("Escape", delay=0.5)
    raise AssertionError("could not open the Lua console\n" + g.screen())


def log_row(g, y):
    """Screen text of a console log row, stripped of the scrollbar gutter."""
    return g.screen().splitlines()[y].strip("│^v ").strip()


def test_console_clicks_scroll_log_and_leave_text_entry_alone(g):
    # A log far bigger than the 33 visible rows so a track click jumps deep.
    open_console(g)
    g.keys("Enter", delay=0.5)
    g.type("for i=1,400 do print('line ' .. i) end")
    g.keys("C-s", delay=0)
    g.wait_for("line 400", timeout=30)

    # The newest line sits at the bottom of the log area (rows 1..33); the
    # scrollbar occupies column 0 with its arrows at rows 1 and 33.
    assert log_row(g, 33).endswith("line 400"), g.screen()
    top_before = log_row(g, 1)

    g.click(0, 1)
    assert log_row(g, 33).endswith("line 399"), \
        "the up arrow click must scroll the log one line\n" + g.screen()
    assert log_row(g, 1) != top_before, "the up arrow click must move the top of the view\n" + g.screen()

    g.click(0, 17)
    match = re.search(r"line (\d+)$", log_row(g, 33))
    assert match and 10 < int(match.group(1)) < 400, \
        f"a track click must jump into the clicked part of the log\n{g.screen()}"

    # Keyboard scrolling still works after the clicks.
    bottom = log_row(g, 33)
    g.keys("PageUp", delay=0.5)
    assert log_row(g, 33) != bottom, "PageUp must still scroll after clicks\n" + g.screen()
    g.keys("Escape", delay=0.5)
    g.wait_gone("to enter/edit command", timeout=15)

    # Text entry through the editor survives clicks on its window: a click on
    # the scrollbar column of a short text does nothing at all, and Ctrl+S
    # alone runs the input, unchanged.
    open_console(g)
    g.keys("Enter", delay=0.5)
    g.type("return 'ok'")
    g.click(1, 41)
    g.keys("C-s", delay=0)
    g.wait_for("# ok", timeout=20)
    g.wait_gone("to run script", timeout=15)
    g.keys("Escape", delay=0.5)
    g.wait_gone("to enter/edit command", timeout=15)

    # A multi line input draws the editor scrollbar; clicking its up arrow
    # moves the cursor one line, and the next typed character lands there.
    open_console(g)
    g.keys("Enter", delay=0.5)
    g.type("one\ntwo\nthree\nfour\nfive\nsix\nseven\neight", delay=0.5)
    g.click(1, 39)
    g.type("!")
    g.keys("C-s", delay=0)
    g.wait_gone("to run script", timeout=15)
    screen = g.screen()
    rows = [l.strip("│^v ").strip() for l in screen.splitlines()]
    assert any(r.endswith("seven!") for r in rows), \
        f"the arrow click must move the cursor one line up before typing\n{screen}"
    assert not any(r == "eight!" for r in rows), \
        "the click must not move the cursor onto the wrong line\n" + screen
    g.keys("Escape", delay=0.5)
    g.wait_gone("to enter/edit command", timeout=15)


def test_classic_scheme_keeps_the_rules_menu_keyboard_only(_g):
    """Classic must stay upstream-identical: no mouse registration, clicks do nothing."""
    g = Game(name="bn-e2e-utility-classic", cols=80, rows=25,
             options={"CONTROL_SCHEME": "classic"})
    try:
        seed_rules(g, 5)
        start_new_game(g)
        open_manager(g, "Autopickup manager", "AUTO PICKUP MANAGER")
        assert marker_rule(g) == 1, g.screen()
        g.click(10, 8)
        assert marker_rule(g) == 1, "a classic scheme click must not move the selection\n" + g.screen()
        g.keys("Down", delay=0.5)
        assert marker_rule(g) == 2, "classic arrow keys must still work\n" + g.screen()
        g.keys("Escape", delay=1)
        g.wait_gone("AUTO PICKUP MANAGER", timeout=10)
    finally:
        g.close()


TESTS = [test_autopickup_clicks_select_rows_columns_tabs_and_switch,
         test_console_clicks_scroll_log_and_leave_text_entry_alone,
         test_classic_scheme_keeps_the_rules_menu_keyboard_only]
