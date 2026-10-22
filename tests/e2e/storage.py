"""Quick stack and sort pile: what moves into nearby storage and what stays.

Tests that take `g` run on the runner's main game.
"""
import re

from helpers import action_menu, arena, count_at, count_carried, give, settle, spawn


def test_quick_stack(g):
    arena(g)
    spawn(g, 2, 0, "usb_drive", furn="f_rack")
    give(g, "usb_drive", 3)
    give(g, "plastic_six_dice", 1)
    assert count_carried(g, "usb_drive") == 3
    action_menu(g, "Interact", "Quick stack to nearby storage")
    settle(g)
    assert count_at(g, 2, 0, "usb_drive") == 4, "drives should join the rack"
    assert count_carried(g, "usb_drive") == 0
    assert count_carried(g, "plastic_six_dice") == 1, "nothing nearby holds dice, so they stay"
    # The random starting profession may carry something of the drives' category, which also goes.
    assert re.search(r"Stashed \d+ items into 1 spot", g.screen()), g.screen()


def test_quick_stack_not_through_windows(g):
    arena(g)
    assert g.lua("M:set_ter_at(here(1,0), TerId.new('t_window'):int_id()) out('ok')") == ["ok"]
    spawn(g, 2, 0, "usb_drive", furn="f_rack")
    give(g, "usb_drive", 2)
    action_menu(g, "Interact", "Quick stack to nearby storage")
    settle(g)
    assert count_carried(g, "usb_drive") == 2, "a shelf behind a window is out of reach"
    assert count_at(g, 2, 0, "usb_drive") == 1
    g.lua("M:set_ter_at(here(1,0), TerId.new('t_floor'):int_id()) out('ok')")


def test_sort_pile(g):
    arena(g)
    spawn(g, 3, 0, "usb_drive", furn="f_rack")
    spawn(g, -3, 0, "flyer", furn="f_rack")
    spawn(g, 0, 0, "usb_drive", 2)
    spawn(g, 0, 0, "character_sheet", 1)
    spawn(g, 0, 0, "plastic_six_dice", 1)
    action_menu(g, "Interact", "Sort the pile you're standing on")
    settle(g)
    assert count_at(g, 3, 0, "usb_drive") == 3, "same item goes to the same shelf"
    assert count_at(g, -3, 0, "character_sheet") == 1, "books follow books"
    assert count_at(g, 0, 0, "plastic_six_dice") == 1, "unmatched items stay in the pile"


TESTS = [
    test_quick_stack,
    test_quick_stack_not_through_windows,
    test_sort_pile,
]
