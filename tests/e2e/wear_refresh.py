"""Shift+W wear (and wield) keep the inventory open and refresh the lists at once.

The worn or wielded item must move into its section immediately; the selected item
stays selected. Before the fix the row vanished until the menu was closed and reopened.
"""
from fixtures import shared_game
from helpers import HELPERS, arena, empty_inventory, give
from inventory_mouse import row_of

MODERN = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false"}

MENU_MARKERS = ("Inventory", "Origin:", "to enter/edit command")


def to_game(g):
    """Escape until no menu is on screen; Lua calls must only run in game mode."""
    for _ in range(8):
        s = g.screen()
        if not any(marker in s for marker in MENU_MARKERS):
            return
        g.keys("Escape", delay=0.6)
    raise AssertionError("not back in game\n" + g.screen())


def open_inventory(g):
    g.keys("i", delay=0.4)
    g.wait_for("Inventory", timeout=15)


def fresh_items(g, *items):
    arena(g)
    empty_inventory(g)
    arena(g)
    for item in items:
        give(g, item)


def cleanup(g):
    """Leave the shared main game as bare as this test found it."""
    to_game(g)
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)


def select_first_row(g):
    g.keys("Home", delay=0.4)


def test_wear_moves_shirt_into_worn_and_keeps_menu_open(g):
    fresh_items(g, "pipe", "tshirt")
    open_inventory(g)
    select_first_row(g)  # the shirt sorts under CLOTHING, above the other items
    g.keys("W", delay=1.5)
    s = g.screen()
    assert "Inventory" in s, "wearing must keep the inventory open\n" + s
    assert "ITEMS WORN" in s, "the worn list must appear at once\n" + s
    lines = s.splitlines()
    worn_y = next(y for y, line in enumerate(lines) if "ITEMS WORN" in line)
    shirt_x, shirt_y = row_of(g, "t-shirt")
    assert shirt_y > worn_y, "the shirt must sit under the worn list\n" + s
    assert "pipe" in s, "other carried items must stay listed\n" + s

    # The selection follows the item: Enter still opens the shirt, now worn.
    g.keys("Enter", delay=1.2)
    s = g.screen()
    assert "short-sleeved cotton shirt" in s, "Enter must open the worn shirt's item menu\n" + s
    cleanup(g)


def test_wield_moves_pipe_into_weapon_list_and_keeps_menu_open(g):
    fresh_items(g, "rock", "pipe")
    open_inventory(g)
    select_first_row(g)  # the pipe sorts under METAL SCRAP, above the rock
    g.keys("h", delay=1.5)
    s = g.screen()
    assert "Inventory" in s, "wielding must keep the inventory open\n" + s
    assert "WEAPON HELD" in s, "the held weapon must appear at once\n" + s
    lines = s.splitlines()
    weapon_y = next(y for y, line in enumerate(lines) if "WEAPON HELD" in line)
    pipe_x, pipe_y = row_of(g, "pipe")
    assert pipe_y > weapon_y, "the pipe must sit under the held weapon list\n" + s
    assert "rock" in s, "other carried items must stay listed\n" + s

    # The selection follows the item: Enter still opens the pipe, now wielded.
    g.keys("Enter", delay=1.2)
    s = g.screen()
    assert "A steel pipe" in s, "Enter must open the wielded pipe's item menu\n" + s
    cleanup(g)


TESTS = [test_wear_moves_shirt_into_worn_and_keeps_menu_open,
         test_wield_moves_pipe_into_weapon_list_and_keeps_menu_open]
