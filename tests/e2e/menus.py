"""List menus, the action menu and the inventory window frame.

Tests that take `g` run on the runner's main game.
"""
import re

from aim_reticle import action_clock
from helpers import action_menu, arena, bub_pos, count_carried, settle, spawn


def test_wasd_menu_navigation(g):
    """Letter shortcuts must not steal WASD from a real list menu."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(g.lua,
                                 "local menu=UiList.new() menu:title('WASD navigation') "
                                 "menu:add(10,'First choice') menu:add(20,'Second choice') "
                                 "menu:add(30,'Third choice') out(menu:query())")
        g.wait_for("< WASD navigation >")
        g.keys("s", "s", "w", "a", "d", "Enter", delay=0.4)
        assert result.result() == ["20"], g.screen()

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(g.lua,
                                 "local menu=UiList.new() menu:title('Filter typing') "
                                 "menu:add(10,'Other item') menu:add(20,'wasd first') "
                                 "menu:add(30,'wasd second') out(menu:query())")
        g.wait_for("< Filter typing >")
        g.keys("/", delay=0.4)
        g.type("wasd")
        g.keys("Down", "Up", "Down", "Enter", "Enter", delay=0.4)
        assert result.result() == ["30"], g.screen()

    arena(g)
    spawn(g, 0, 0, "rock")
    spawn(g, 0, 0, "stick")
    before = {item: count_carried(g, item) for item in ("rock", "stick")}
    g.keys("G", delay=0.8)
    g.wait_for("rock")
    def selected(item):
        return re.search(r"< [^<>]*" + item + r"[^<>]* >", g.screen()) is not None
    first = "rock" if selected("rock") else "stick"
    assert selected(first), g.screen()
    second = "stick" if first == "rock" else "rock"
    g.keys("s", delay=0.4)
    assert selected(second), "S must navigate to the other item\n" + g.screen()
    g.keys("d", "w", delay=0.4)
    assert selected(first), "W must navigate back without wielding\n" + g.screen()
    g.keys("d", "a", "Enter", delay=0.4)
    assert count_carried(g, second) == before[second] + 1, "D marks the selected item"
    assert count_carried(g, first) == before[first], "A unmarks the selected item"


def test_action_menu_opens_character_info(g):
    def character_sheet_visible(screen):
        return all(label in screen for label in ("Strength:", "Dexterity:", "Intelligence:", "Perception:"))

    arena(g)
    settle(g)
    try:
        before = bub_pos(g)
        clock = action_clock(g)
        action_menu(g, "Info", "View Player Info")
        assert character_sheet_visible(g.screen()), "the action menu must open the actual character sheet:\n" + g.screen()
        g.keys("Escape", delay=0.6)
        assert not character_sheet_visible(g.screen()), "Escape must return from the character sheet"
        assert bub_pos(g) == before
        assert action_clock(g) == clock, "browsing character information must not spend moves"
    finally:
        arena(g)


def test_aim_defaults(g):
    action_menu(g, "Inventory", "Advanced Inventory management")
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert "Surrounding area" in s or "Surrounding" in s or "AL" in s, "left pane should show the surroundings"
    assert "Inventory" in s


def test_rounded_frames(g):
    g.keys("i", delay=1)
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert "╭" in s and "╯" in s, "inventory window should have rounded corners"


TESTS = [
    test_wasd_menu_navigation,
    test_action_menu_opens_character_info,
    test_aim_defaults,
    test_rounded_frames,
]
