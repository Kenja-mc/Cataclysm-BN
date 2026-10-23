"""Modern-scheme mouse support on the vehicle work screen.

Clicks select a part or overview row, switch install tabs and run the same
keyboard actions as the drawn labels. Classic keeps the keyboard-only screen
because the mouse actions are only registered under the modern scheme.
"""
import re

from helpers import HELPERS, action_menu, arena, choose_menu_entry, settle, start_new_game
from tmux_game import Game
from vehicle_box import spawn_vehicle

# The work screen's first row of actions stays visible at every supported width.
SCREEN_MARKER = "refill"


def row_of(screen, needle, xmin=0):
    """Absolute x, y of the first occurrence of needle at or after xmin."""
    for y, line in enumerate(screen.splitlines()):
        x = line.find(needle, xmin)
        if x >= 0:
            return x, y
    raise AssertionError(f"no {needle!r} in screen:\n{screen}")


def parts_pane(screen):
    """Text of the left parts list column on the default 140x45 layout."""
    return "\n".join(line[:48] for line in screen.splitlines())


def open_vehicle_work_screen(g):
    """Walk the real examine route instead of calling the screen directly."""
    x, y = g.find("@")
    g.click(x, y, button=2)
    action_menu(g, "Interact", "Examine Nearby Terrain")
    if "Examine where?" in g.screen():
        g.keys("x", delay=0.2)
    if "Interact with what?" in g.screen() or "Interact with the" in g.screen():
        choose_menu_entry(g, "examine the")
    g.wait_for("Examine vehicle")
    choose_menu_entry(g, "Examine vehicle")
    g.wait_for(SCREEN_MARKER)
    g.settle_screen(minimum=0.5, timeout=2)


def vehicle_game(name, cols=140, rows=45):
    """Spawn a car and stand next to it, before opening the work screen."""
    game = Game(name=name, cols=cols, rows=rows,
                options={"SAFEMODE": "false", "CONTROL_SCHEME": "modern"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        spawn_vehicle(game, "car")
        settle(game)
        return game
    except Exception:
        game.close()
        raise


def vehicle_mouse_game(name, cols=140, rows=45):
    game = vehicle_game(name, cols, rows)
    try:
        open_vehicle_work_screen(game)
        return game
    except Exception:
        game.close()
        raise


def test_vehicle_grid_and_overview_clicks_select_parts(_g):
    g = vehicle_mouse_game("bn-e2e-vehicle-mouse-select")
    try:
        before = g.screen()
        assert "quarterpanel" not in parts_pane(before), before
        # A drawn car part sits just left of the centred cursor cell (24, 9).
        g.click(26, 7)
        selected = g.screen()
        assert "ESC-back" in selected, selected
        assert selected != before
        assert "quarterpanel" in parts_pane(selected), \
            "clicking a drawn part must select the mount it belongs to\n" + selected

        # An overview row is a second way to move the cursor, with no action attached.
        x, y = row_of(selected, "reclining seat", 48)
        g.click(50, y)
        after = g.screen()
        assert "reclining seat" in parts_pane(after), \
            "clicking an overview row must make that part the cursor mount\n" + after
        assert after != selected
        assert "ESC-back" in after
    finally:
        g.close()


def test_action_label_click_opens_the_rename_prompt(_g):
    g = vehicle_mouse_game("bn-e2e-vehicle-mouse-action")
    try:
        x, y = row_of(g.screen(), "rEname")
        assert y == 1, "the action labels own the first row"
        g.click(x + 1, y)
        g.wait_for("Enter new vehicle name:")
        g.keys("Escape", delay=0.8)
        screen = g.screen()
        assert "ESC-back" in screen, "cancelling the prompt must return to the work screen\n" + screen
    finally:
        g.close()


def test_part_clicks_do_not_advance_time_or_start_work(_g):
    g = vehicle_game("bn-e2e-vehicle-mouse-noop")
    try:
        before = g.lua("out(gapi.current_turn():to_turn(),gapi.get_avatar():get_moves())")
        open_vehicle_work_screen(g)
        g.click(26, 7)
        x, y = row_of(g.screen(), "reclining seat", 48)
        g.click(50, y)
        # Cancel the rename prompt, then leave through the drawn ESC-back label.
        x, y = row_of(g.screen(), "rEname")
        g.click(x + 1, y)
        g.wait_for("Enter new vehicle name:")
        g.keys("Escape", delay=0.8)
        x, y = row_of(g.screen(), "ESC-back")
        g.click(x + 1, y)
        g.wait_gone("ESC-back", timeout=5)
        after = g.lua("out(gapi.current_turn():to_turn(),gapi.get_avatar():get_moves())")
        assert after == before, f"browsing parts must not consume time or moves: {before} -> {after}"
    finally:
        g.close()


def test_install_row_and_tab_clicks(_g):
    g = vehicle_mouse_game("bn-e2e-vehicle-mouse-install")
    try:
        g.keys("i", delay=1.5)
        g.wait_for("Choose new part to install here:")
        g.settle_screen(minimum=0.5, timeout=2)
        screen = g.screen()
        lines = screen.splitlines()
        tab_y = next(i for i, l in enumerate(lines) if "<All>" in l)
        # The list starts two rows down; take the second row, which is never the
        # already-selected first entry and does not depend on the starting gear.
        row_line = lines[tab_y + 3]
        entry = row_line[48:93].strip()
        assert len(entry) > 2 and entry[1] == " ", row_line
        part_name = entry[2:].strip()
        g.click(51, tab_y + 3)
        g.settle_screen(minimum=0.5, timeout=2)
        screen = g.screen()
        title = re.search(r"╭─([^─]+?)─+╮", screen)
        assert title and title.group(1) == part_name, \
            f"clicking {part_name!r} must show its details, got {title and title.group(1)!r}\n" + screen

        line = next(l for l in screen.splitlines() if "<All>" in l)
        cargo = re.search(r"<All> +(C)\b", line)
        assert cargo, line
        g.click(cargo.start(1), tab_y)
        screen = g.screen()
        assert "<Cargo>" in screen, "clicking the C tab must select Cargo\n" + screen

        g.keys("Escape", delay=0.8)
        assert "ESC-back" in g.screen()
    finally:
        g.close()


def test_description_hint_click_scrolls_descriptions(_g):
    g = vehicle_mouse_game("bn-e2e-vehicle-mouse-description")
    try:
        screen = g.screen()
        x, y = row_of(screen, "More parts here…  >", 94)
        g.click(x, y)
        after = g.screen()
        assert "<  More parts here…" in after, \
            "clicking the shown-down hint must scroll the description down\n" + after
        assert after != screen
    finally:
        g.close()


def test_parts_list_hint_and_wheel_scroll(_g):
    g = vehicle_mouse_game("bn-e2e-vehicle-mouse-parts-scroll", cols=80, rows=25)
    try:
        screen = g.screen()
        assert "v More parts below…" in screen, screen
        x, y = row_of(screen, "v More parts below…")
        g.click(x + 1, y)
        screen = g.screen()
        assert "^ More parts above…" in screen, "the shown-down hint must scroll one row\n" + screen

        # Wheel notches move the same cursor list one row and stop at the top.
        g.hover(10, 8)
        g.type("\x1b[<64;11;9M", delay=1)
        screen = g.screen()
        assert "^ More parts above…" not in screen, \
            "a wheel-up notch at the top must not wrap past the first row\n" + screen
        assert "v More parts below…" in screen
        g.type("\x1b[<65;11;9M", delay=1)
        screen = g.screen()
        assert "^ More parts above…" in screen, \
            "a wheel-down notch must move the list by one row\n" + screen
    finally:
        g.close()


def test_overview_wheel_and_hint_scroll(_g):
    g = vehicle_mouse_game("bn-e2e-vehicle-mouse-overview-scroll", cols=80, rows=24)
    try:
        screen = g.screen()
        assert "'{' to scroll up" not in screen, screen
        # At 80 columns the overview starts at x=28, so hover over that pane.
        g.hover(40, 5)
        g.type("\x1b[<65;41;6M", delay=1)
        screen = g.screen()
        assert "'{' to scroll up" in screen, "the wheel must scroll the overview\n" + screen
        x, y = row_of(screen, "'{' to scroll up")
        g.click(x, y)
        screen = g.screen()
        assert "'{' to scroll up" not in screen, \
            "clicking the shown-up hint must scroll the overview back to the top\n" + screen
    finally:
        g.close()


def test_resize_rebuilds_the_click_map(_g):
    g = vehicle_mouse_game("bn-e2e-vehicle-mouse-resize")
    try:
        assert "v More parts below…" not in g.screen(), "the full layout fits every part"
        g.resize(80, 25)
        g.settle_screen(minimum=0.8, timeout=3)
        screen = g.screen()
        assert "v More parts below…" in screen, "the resized layout must redraw its hints\n" + screen

        x, y = row_of(screen, "v More parts below…")
        g.click(x + 1, y)
        assert "^ More parts above…" in g.screen(), "the click map must follow the new layout"

        g.resize(140, 45)
        g.settle_screen(minimum=0.8, timeout=3)
        x, y = row_of(g.screen(), "ESC-back")
        g.click(x + 1, y)
        g.wait_gone("ESC-back", timeout=5)
        assert "X,Y,Z" in g.screen() or "Location:" in g.screen()
    finally:
        g.close()


TESTS = [
    test_vehicle_grid_and_overview_clicks_select_parts,
    test_action_label_click_opens_the_rename_prompt,
    test_part_clicks_do_not_advance_time_or_start_work,
    test_install_row_and_tab_clicks,
    test_description_hint_click_scrolls_descriptions,
    test_parts_list_hint_and_wheel_scroll,
    test_overview_wheel_and_hint_scroll,
    test_resize_rebuilds_the_click_map,
]
