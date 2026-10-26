"""Scrollbar clicks in list menus, options and the keybindings editor.

The bars are drawn over a border, so the tests find the real '^'/'v' pair on the
screen instead of assuming a terminal size, then click cells inside that bar.
"""
import time
from concurrent.futures import ThreadPoolExecutor

from fixtures import shared_game
from helpers import HELPERS, wait_until
from agent_actions import menu_rows
from options_menu import close_options
from tmux_game import Game, start_new_game


def find_scrollbar(screen, title=None):
    """Locate a vertical scrollbar, optionally on a titled menu's left border."""
    lines = screen.splitlines()
    menu_left = None
    if title is not None:
        title_row = next((line for line in lines if title in line), None)
        if title_row is None:
            return None
        menu_left = title_row.rfind("╭", 0, title_row.index(title))
        if menu_left < 0:
            return None
    best = None
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if menu_left is not None and x != menu_left:
                continue
            if char != "^" or y + 1 >= len(lines):
                continue
            below = lines[y + 1]
            if x >= len(below) or below[x] not in "│|":
                continue
            for bottom in range(y + 2, len(lines)):
                row = lines[bottom]
                if x < len(row) and row[x] == "v":
                    if best is None or bottom - y > best[1] - best[0]:
                        best = (y, bottom, x)
                    break
    return best


def menu_scrollbar(g, title):
    assert g.wait_for(title, timeout=20), g.screen()
    bar = find_scrollbar(g.screen(), title)
    assert bar, "no drawn scrollbar in the open menu\n" + g.screen()
    return bar


def open_main_menu(g):
    deadline = time.time() + 20
    while "MAIN MENU" not in g.screen():
        assert time.time() < deadline, "Escape should open the main menu\n" + g.screen()
        g.keys("Escape", delay=0.4)

def selection_row(screen):
    rows = [y for y, line in enumerate(screen.splitlines()) if ">>" in line]
    assert rows, "the list has no selected row\n" + screen
    return rows[0]


def test_uilist_scrollbar_jumps_and_arrows(g):
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(
            g.lua,
            "local menu=UiList.new() menu:title('Scrollbar probe') "
            "for i=0,99 do menu:add(i,string.format('Item %03d',i)) end out(menu:query())")
        top, bottom, x = menu_scrollbar(g, "< Scrollbar probe >")

        g.click(x, bottom - 1)
        screen = g.screen()
        assert "Item 099" in screen, "the lower track must jump to the end\n" + screen
        assert "< Scrollbar probe >" in screen, "a scrollbar click must not act on an item"

        g.click(x, top + 1)
        assert "Item 000" in g.screen(), "the upper track must jump back to the start\n" + g.screen()

        g.click(x, bottom)
        screen = g.screen()
        assert "Item 000" not in screen and "Item 001" in screen, \
            "the down arrow must move exactly one row\n" + screen

        g.click(x, bottom)
        screen = g.screen()
        assert "Item 001" not in screen and "Item 002" in screen, \
            "a second down-arrow click must move exactly one row\n" + screen

        g.click(x, top)
        screen = g.screen()
        assert "Item 001" in screen and "Item 000" not in screen, \
            "the up arrow must move exactly one row\n" + screen

        g.click(x, top)
        g.click(x, top)
        screen = g.screen()
        assert "Item 000" in screen, "the up arrow must not wrap past the first row\n" + screen

        g.click(x, bottom - 1)
        g.click(x, bottom)
        assert "Item 099" in g.screen(), "the down arrow must not wrap past the last row"
        g.keys("Enter", delay=0.5)
        assert result.result() == ["0"], "scrollbar clicks must not change the selection"


def test_uilist_scrollbar_after_resize(g):
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(
                g.lua,
                "local menu=UiList.new() menu:title('Resize probe') "
                "for i=0,199 do menu:add(i,string.format('Row %03d',i)) end out(menu:query())")
            old = menu_scrollbar(g, "< Resize probe >")
            g.resize(100, 30)
            assert wait_until(
                lambda: (bar := find_scrollbar(g.screen(), "< Resize probe >")) and bar[1] != old[1],
                timeout=10), "the scrollbar must follow the resized window\n" + g.screen()
            top, bottom, x = find_scrollbar(g.screen(), "< Resize probe >")

            g.click(x, bottom - 1)
            assert "Row 199" in g.screen(), "the resized bar must map to the resized list\n" + g.screen()
            g.click(x, top + 1)
            assert "Row 000" in g.screen(), "the resized upper track must jump to the start"
            g.keys("Enter", delay=0.5)
            assert result.result() == ["0"]
    finally:
        try:
            g.resize(140, 45)
        except Exception:
            pass


def test_options_and_keybindings_scrollbars(_g):
    g = Game(name="bn-e2e-menu-scrollbars-keys", cols=140, rows=45)
    try:
        start_new_game(g)
        open_main_menu(g)
        # Pick the row by label: the menu's auto-assigned hotkeys shift with the scheme.
        rows = {row.label: row.hotkey for row in menu_rows(g.screen())}
        options = next(hotkey for label, hotkey in rows.items() if "Options" in label)
        g.keys(options, delay=0.8)
        g.wait_for(" OPTIONS ", timeout=10)
        for _ in range(8):
            bar = find_scrollbar(g.screen())
            if bar:
                break
            g.keys("Tab", delay=0.5)
        assert bar, "an options page should be long enough for a scrollbar\n" + g.screen()
        top, bottom, x = bar
        first = selection_row(g.screen())
        g.click(x, bottom - 1)
        screen = g.screen()
        assert selection_row(screen) > top + 10, \
            "the options track must select toward the clicked row\n" + screen
        assert "OPTIONS" in screen, "a scrollbar click must keep the options screen open"
        g.click(x, top + 1)
        assert selection_row(g.screen()) == first, "the upper track must return to the first option"
        close_options(g)

        open_main_menu(g)
        g.keys("4", delay=0.8)
        g.wait_for("Unbound keys", timeout=15)
        bar = find_scrollbar(g.screen())
        assert bar, "the keybindings screen should draw a list scrollbar\n" + g.screen()
        top, bottom, x = bar
        before = g.screen().splitlines()[top + 5]
        g.click(x, bottom - 1)
        assert g.screen().splitlines()[top + 5] != before, \
            "the keybindings track must scroll the action list\n" + g.screen()
        g.click(x, top + 1)
        assert g.screen().splitlines()[top + 5] == before, \
            "the keybindings upper track must scroll back\n" + g.screen()
        g.keys("Escape", delay=0.5)
    finally:
        g.close()


def test_classic_uilist_scrollbar_ignores_click(_g):
    with shared_game("bn-e2e-menu-scrollbars-classic", options={
            "CONTROL_SCHEME": "classic"}, define=HELPERS) as g:
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(
                g.lua,
                "local menu=UiList.new() menu:title('Classic probe') "
                "for i=0,99 do menu:add(i,string.format('Item %03d',i)) end out(menu:query())")
            top, bottom, x = menu_scrollbar(g, "< Classic probe >")
            g.click(x, bottom - 1)
            screen = g.screen()
            assert "Item 000" in screen and "Item 099" not in screen, \
                "classic must keep ignoring mouse scrollbar clicks\n" + screen
            g.keys("Escape", delay=0.5)
            result.result()


TESTS = [test_uilist_scrollbar_jumps_and_arrows, test_uilist_scrollbar_after_resize,
         test_options_and_keybindings_scrollbars, test_classic_uilist_scrollbar_ignores_click]
