"""Floating HUD windows: collapse, restore, drag, persistence and the keyboard path.

The windows are the slide-2 layout: weather/time, combat, needs and vehicle readings,
each with a title row and a collapse control over the map.
"""
import re

from crafting import load_first_save
from helpers import HELPERS, action_menu, bub_pos, save_and_quit, settle
from tmux_game import Game, start_new_game


def action_clock(game):
    return tuple(int(value) for value in game.lua(
        "out(gapi.current_turn():to_turn(), -gapi.get_avatar():get_moves())")[0].split(","))


def hud_game(name, **options):
    game = Game(name=name, cols=140, rows=45,
                options={"SAFEMODE": "false", "SHOW_WELCOME": "false",
                         "ANIMATIONS": "false", "HUD_ICONS": "ascii", **options})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        settle(game)
    except Exception:
        game.close()
        raise
    return game


def find_titles(screen, name):
    """Every title row for one window, matched at a box interior."""
    rows = []
    for y, line in enumerate(screen.splitlines()):
        start = 0
        while True:
            found = line.find(name, start)
            if found < 0:
                break
            if line[max(0, found - 2):found] == "│ ":
                controls = [(line.find(token, found), token)
                            for token in ("[-]", "[+]")]
                controls = [(at, token) for at, token in controls if at >= 0]
                if controls:
                    control_at, _ = min(controls)
                    # A border between the name and the control means the control
                    # belongs to a later window on the same screen row.
                    if "│" not in line[found:control_at]:
                        rows.append((y, line))
                        break
            start = found + 1
    return rows


def title_row(screen, name):
    rows = find_titles(screen, name)
    assert len(rows) == 1, f"expected one {name} title row:\n{screen}"
    return rows[0]


def title_column(line, name):
    """The name's column where it starts a box whose control is on the same row."""
    start = 0
    while True:
        found = line.find(name, start)
        if found < 0:
            break
        if line[max(0, found - 2):found] == "│ ":
            controls = [(line.find(token, found), token)
                        for token in ("[-]", "[+]")]
            controls = [(at, token) for at, token in controls if at >= 0]
            if controls:
                control_at, _ = min(controls)
                if "│" not in line[found:control_at]:
                    return found
        start = found + 1
    raise AssertionError(f"no title {name} in " + line)


def control(line, name):
    """The window's own control: take the nearest control token after its name.

    Two windows can share a title row, and the window being clicked may be collapsed
    while a later window on the same row shows `[-]`, so checking one token at a time
    in a fixed order picks the wrong box.
    """
    start = title_column(line, name)
    found = [(line.find(token, start), token) for token in ("[-]", "[+]")]
    found = [(at, token) for at, token in found if at >= 0]
    assert found, f"no control after {name} in " + line
    return min(found)


def summary(line, name):
    """The live state between the window name and its control."""
    start = title_column(line, name) + len(name)
    end = min(i for i in (line.find("[-]", start), line.find("[+]", start)) if i >= 0)
    return line[start:end].strip()


def marker_on(game, label):
    """Whether the Sidebar Options cursor (>>) is on a HUD window row."""
    for line in game.screen().splitlines():
        marker = line.find(">>")
        if marker > 40 and label in line[marker:]:
            return True
    return False


def goto_hud_row(game, label):
    """Navigates down the third column to a HUD row; assumes the cursor is in that column."""
    for _ in range(20):
        if marker_on(game, label):
            return
        game.keys("Down", delay=0.2)
    assert marker_on(game, label), "the HUD window rows must be reachable:\n" + game.screen()


def reach_hud_row(game, label):
    game.keys("Right", delay=0.4)
    goto_hud_row(game, label)


def menu_lines(game):
    """The rows covered by the open Sidebar Options window."""
    lines = game.screen().splitlines()
    top = next(i for i, line in enumerate(lines) if "SIDEBAR OPTIONS" in line)
    return lines[top:top + 21]


def row_slice(screen, row, first, last):
    lines = screen.splitlines()
    return lines[row][first:last] if row < len(lines) else ""


def menu_column(game):
    # The menu's third column starts at screen column 90; stop at its right border.
    return "\n".join(line[90:107] for line in menu_lines(game))


def test_collapse_restore_drag_and_needs(_g):
    game = hud_game("bn-e2e-hud-windows")
    try:
        screen = game.screen()
        for name in ("Weather", "Combat", "Needs", "Limbs", "Stats", "Movement",
                     "Weight", "Compass", "Log"):
            title_row(screen, name)
        weather_y, weather = title_row(screen, "Weather")
        assert control(weather, "Weather")[1] == "[-]", weather
        live = summary(weather, "Weather")
        assert live, "the title row must carry live weather state:\n" + weather
        assert "Light:" in screen and "Wind:" in screen
        assert "North:" in screen, "the compass must keep its direction labels:\n" + screen
        assert "Str" in screen, "the stats window must keep its stat rows:\n" + screen
        assert "No wounds" in screen, "the limbs window must keep its summary:\n" + screen
        assert not any("Vehicle" in line and ("[-]" in line or "[+]" in line)
                       for line in screen.splitlines()), \
            "the vehicle window must not exist on foot:\n" + screen

        # Right clicks on a window are consumed too.
        right_clock = action_clock(game)
        right_pos = bub_pos(game)
        game.click(title_column(weather, "Weather") + 4, weather_y + 1, button=2)
        assert "Mouse View" not in game.screen(), \
            "a right click on a window must not select the map tile under it"
        assert bub_pos(game) == right_pos and action_clock(game) == right_clock

        # Collapsing keeps one line of live state and the click never reaches the map.
        before_clock = action_clock(game)
        before_pos = bub_pos(game)
        game.click(control(weather, "Weather")[0], weather_y)
        assert "Mouse View" not in game.screen(), \
            "a window click must not select the map tile under it"
        assert bub_pos(game) == before_pos, "a window click must not move the avatar"
        assert action_clock(game) == before_clock, "a window click must not act on the map"
        screen = game.screen()
        collapsed_y, collapsed = title_row(screen, "Weather")
        assert control(collapsed, "Weather")[1] == "[+]", "the control must offer restore:\n" + collapsed
        assert live in collapsed, "a collapsed window must keep its live state:\n" + collapsed
        assert "Light:" not in screen, "the collapsed body must be hidden:\n" + screen

        # Clicking the name restores the window in place.
        game.click(title_column(collapsed, "Weather"), collapsed_y)
        screen = game.screen()
        restored_y, restored = title_row(screen, "Weather")
        assert control(restored, "Weather")[1] == "[-]", "the title click must restore:\n" + restored
        assert "Light:" in screen and "Wind:" in screen
        assert restored_y == weather_y, "restoring must not move the window"

        # A collapsed window still has a drag handle beside its name.
        game.click(control(restored, "Weather")[0], restored_y)
        screen = game.screen()
        collapsed_y, collapsed = title_row(screen, "Weather")
        name_x = title_column(collapsed, "Weather")
        grab_x = name_x + len("Weather") + 2
        assert grab_x < control(collapsed, "Weather")[0], collapsed
        game.click(grab_x, collapsed_y)
        game.hover(grab_x + 40, collapsed_y)
        game.click(grab_x + 40, collapsed_y)
        screen = game.screen()
        dragged_y, dragged = title_row(screen, "Weather")
        assert control(dragged, "Weather")[1] == "[+]", \
            "dragging a collapsed title must keep it collapsed:\n" + dragged
        assert (title_column(dragged, "Weather"), dragged_y) == (name_x + 40, collapsed_y), \
            "a collapsed window must be movable:\n" + dragged
        game.click(title_column(dragged, "Weather"), dragged_y)
        screen = game.screen()
        restored_y, restored = title_row(screen, "Weather")
        assert control(restored, "Weather")[1] == "[-]", \
            "the name must restore the moved collapsed window:\n" + restored

        # Click a title, move the pointer, click again: the window follows inside the map.
        target_row = restored_y + 3
        game.click(title_column(restored, "Weather"), restored_y)
        game.hover(14, target_row)
        game.click(14, target_row)
        screen = game.screen()
        moved_y, moved = title_row(screen, "Weather")
        assert (title_column(moved, "Weather"), moved_y) == (14, target_row), \
            "the title drag must move the window:\n" + moved
        assert "Mouse View" not in screen, \
            "dropping a window must not select the map tile under it"
        # The sidebar starts at column 96 on this profile.
        assert control(moved, "Weather")[0] < 96, "the window must not cover the sidebar:\n" + moved

        # A drag into the map's right edge stops there, clear of the sidebar and the log.
        game.click(title_column(moved, "Weather"), moved_y)
        game.hover(139, 24)
        game.click(139, 24)
        screen = game.screen()
        edge_y, edge = title_row(screen, "Weather")
        assert control(edge, "Weather")[0] < 96, "the window must not cover the sidebar:\n" + edge
        assert edge_y < 45, "the window must stay on screen:\n" + edge

        # Every window carries the same control; the limb window is the new-layout example.
        limbs_y, limbs = title_row(screen, "Limbs")
        assert "HEAD" in screen
        game.click(control(limbs, "Limbs")[0], limbs_y)
        screen = game.screen()
        assert control(title_row(screen, "Limbs")[1], "Limbs")[1] == "[+]"
        assert "HEAD" not in screen, "the collapsed limbs body must be hidden:\n" + screen
        game.click(title_column(title_row(screen, "Limbs")[1], "Limbs"), limbs_y)
        screen = game.screen()
        assert control(title_row(screen, "Limbs")[1], "Limbs")[1] == "[-]"
        assert "HEAD" in screen

        # A pressing need lists its glyph and label, never the adjective.
        assert game.lua("gapi.get_avatar():set_thirst(300) out('ok')") == ["ok"]
        settle(game)
        screen = game.screen()
        needs_y, needs = title_row(screen, "Needs")
        assert "Thirst" in needs, "the title must keep the pressing need:\n" + needs
        assert "Thirst" in screen.splitlines()[needs_y + 1], \
            "the body must list the pressing need:\n" + screen
        assert "very thirsty" not in screen.lower(), \
            "the needs window must use glyphs, not adjectives:\n" + screen
    finally:
        game.close()


def test_positions_and_collapse_survive_reload(_g):
    game = hud_game("bn-e2e-hud-persist")
    try:
        y, line = title_row(game.screen(), "Weather")
        start_x = title_column(line, "Weather")
        game.click(start_x, y)
        game.hover(start_x + 10, y + 2)
        game.click(start_x + 10, y + 2)
        moved_y, moved = title_row(game.screen(), "Weather")
        placed_x, placed_y = title_column(moved, "Weather"), moved_y
        assert (placed_x, placed_y) == (start_x + 10, y + 2), \
            "the drag must place the window where it was dropped:\n" + moved
        # Collapse after moving, so both pieces of state are saved together.
        game.click(control(moved, "Weather")[0], moved_y)
        assert control(title_row(game.screen(), "Weather")[1], "Weather")[1] == "[+]"

        save_and_quit(game)
        load_first_save(game)
        settle(game)
        screen = game.screen()
        reloaded_y, reloaded = title_row(screen, "Weather")
        assert (title_column(reloaded, "Weather"), reloaded_y) == (placed_x, placed_y), \
            "the saved position must survive the reload:\n" + reloaded
        assert control(reloaded, "Weather")[1] == "[+]", "the saved collapse must survive:\n" + reloaded
        assert "Light:" not in screen
        # The restored window expands again after the reload.
        game.click(title_column(reloaded, "Weather"), reloaded_y)
        screen = game.screen()
        restored_y, restored = title_row(screen, "Weather")
        assert control(restored, "Weather")[1] == "[-]", "the title must expand after reload:\n" + restored
        assert "Light:" in screen and restored_y == reloaded_y
    finally:
        game.close()


def test_sidebar_options_toggles_a_window_without_a_mouse(_g):
    game = hud_game("bn-e2e-hud-menu")
    try:
        assert title_row(game.screen(), "Weather")
        action_menu(game, "Misc", "Sidebar Options")
        game.wait_for("SIDEBAR OPTIONS")
        game.keys("Right", delay=0.4)
        # The menu's third column lists every window below the layouts.
        for name in ("Weather", "Combat", "Needs", "Limbs", "Stats", "Movement",
                     "Weight", "Compass", "Log", "Vehicle"):
            assert name in menu_column(game), \
                f"{name} must be reachable without a mouse:\n" + game.screen()

        # Classic/compact keep their panels, so the HUD rows disappear there.
        game.keys("Enter", delay=0.6)  # row 0: classic
        column = menu_column(game)
        assert "HUD WINDOWS" not in column and "Weather" not in column, \
            "classic layouts must not list floating windows:\n" + game.screen()
        game.keys("Down", "Down", "Down", "Enter", delay=0.4)  # back to labels
        assert "HUD WINDOWS" in menu_column(game), \
            "labels must list the floating windows:\n" + game.screen()

        goto_hud_row(game, "Stats")
        game.keys("Tab", delay=0.4)
        assert any("Stats" in line[32:56] for line in menu_lines(game)), \
            "the returned sidebar panel must appear in the open menu:\n" + game.screen()
        game.keys("Escape", delay=0.8)
        settle(game)
        screen = game.screen()
        assert not any("Stats" in line and ("[-]" in line or "[+]" in line)
                       for line in screen.splitlines()), \
            "toggling the window off must remove it:\n" + screen
        assert "Str" in screen, "the sidebar must own the readings again:\n" + screen

        # The same keyboard path turns it back on.
        action_menu(game, "Misc", "Sidebar Options")
        game.wait_for("SIDEBAR OPTIONS")
        reach_hud_row(game, "Stats")
        game.keys("Tab", delay=0.4)
        game.keys("Escape", delay=0.8)
        settle(game)
        assert title_row(game.screen(), "Stats")
    finally:
        game.close()


def test_small_terminal_keeps_the_avatar_and_left_clamp(_g):
    """At the supported 80x25 minimum windows keep off the avatar and inside a left-sidebar map."""
    game = Game(name="bn-e2e-hud-small", cols=80, rows=25,
                options={"SAFEMODE": "false", "SHOW_WELCOME": "false",
                         "ANIMATIONS": "false", "HUD_ICONS": "ascii",
                         "HUD_WINDOWS": "true", "SIDEBAR_POSITION": "left"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        settle(game)
        assert game.lua("gapi.get_avatar():set_thirst(300) out('ok')") == ["ok"]
        settle(game)
        screen = game.screen()
        lines = screen.splitlines()
        # 80 columns with the 44-column sidebar: the map is 36x25, so the avatar sits at
        # map cell (18, 12), screen column 44 + 18, row 12.
        assert len(lines) > 12 and len(lines[12]) > 62 and lines[12][62] == "@", \
            "a default window covered the avatar:\n" + screen
        # Windows that cannot fit hand their readings back to the sidebar.
        if not find_titles(screen, "Stats"):
            assert "Str" in screen, "the skipped stats reading must return to the sidebar:\n" + screen

        y, line = title_row(screen, "Weather")
        before = bub_pos(game)
        game.click(title_column(line, "Weather"), y)
        game.hover(1, y + 2)
        game.click(1, y + 2)
        screen = game.screen()
        placed = [(line.find("Weather"), row) for row, line in enumerate(screen.splitlines())
                  if line.find("Weather") >= 44]
        assert placed, "the window must stay inside the map:\n" + screen
        assert bub_pos(game) == before, "dragging a window must not move the avatar"
    finally:
        game.close()




def test_window_order_raises_and_persists(_g):
    """Clicking a window raises it; Sidebar Options raises by keyboard and the order saves."""
    game = hud_game("bn-e2e-hud-order")
    try:
        y, line = title_row(game.screen(), "Weather")
        game.click(title_column(line, "Weather"), y)
        game.hover(12, 4)
        game.click(12, 4)
        screen = game.screen()
        wy, wline = title_row(screen, "Weather")
        assert (title_column(wline, "Weather"), wy) == (12, 4), wline

        cy, cline = title_row(screen, "Combat")
        game.click(title_column(cline, "Combat"), cy)
        game.hover(32, 7)
        game.click(32, 7)
        screen = game.screen()
        cy, cline = title_row(screen, "Combat")
        assert (title_column(cline, "Combat"), cy) == (32, 7), cline
        assert "Combat" in row_slice(screen, 7, 30, 41), \
            "the last raised window must be drawn on top:\n" + screen

        # Enter on a HUD row brings that window to the front without a mouse.
        action_menu(game, "Misc", "Sidebar Options")
        game.wait_for("SIDEBAR OPTIONS")
        reach_hud_row(game, "Weather")
        game.keys("Enter", delay=0.4)
        game.keys("Escape", delay=0.8)
        settle(game)
        screen = game.screen()
        assert "Combat" not in row_slice(screen, 7, 30, 41), \
            "raising Weather must hide the overlapping Combat title:\n" + screen

        # A click on the visible part of the lower window raises that one.
        game.click(45, 7)
        assert "Combat" in row_slice(game.screen(), 7, 30, 41), \
            "clicking Combat must bring it to the front:\n" + game.screen()
        game.click(12, 4)
        assert "Combat" not in row_slice(game.screen(), 7, 30, 41), \
            "clicking Weather must bring it back to the front:\n" + game.screen()
        game.click(12, 4)  # drop the grab without changing order again

        save_and_quit(game)
        load_first_save(game)
        settle(game)
        screen = game.screen()
        assert "Combat" not in row_slice(screen, 7, 30, 41), \
            "the window order must survive the reload:\n" + screen

        action_menu(game, "Misc", "Sidebar Options")
        game.wait_for("SIDEBAR OPTIONS")
        reach_hud_row(game, "Combat")
        game.keys("Enter", delay=0.4)
        game.keys("Escape", delay=0.8)
        settle(game)
        assert "Combat" in row_slice(game.screen(), 7, 30, 41), \
            "raising Combat again must restore it on top:\n" + game.screen()
    finally:
        game.close()


def test_grouped_fresh_default_uses_the_same_windows(_g):
    """The first-run grouped layout draws the same ten windows, not only its sidebar sections."""
    game = Game(name="bn-e2e-hud-grouped", cols=140, rows=45, layout="grouped",
                options={"SAFEMODE": "false", "SHOW_WELCOME": "false",
                         "ANIMATIONS": "false", "HUD_ICONS": "ascii"})
    try:
        start_new_game(game)
        settle(game)
        screen = game.screen()
        for name in ("Weather", "Combat", "Needs", "Limbs", "Stats", "Movement",
                     "Weight", "Compass", "Log"):
            title_row(screen, name)
    finally:
        game.close()


TESTS = [
    test_collapse_restore_drag_and_needs,
    test_positions_and_collapse_survive_reload,
    test_sidebar_options_toggles_a_window_without_a_mouse,
    test_small_terminal_keeps_the_avatar_and_left_clamp,
    test_window_order_raises_and_persists,
    test_grouped_fresh_default_uses_the_same_windows,
]
