"""Modern mouse clicks in crafting, construction and character creation.

Covers the shared scrollbar geometry (track jumps, arrows step one row), the
click-then-confirm rule for action rows, and that Classic keeps its keyboard-only
menus.  The creation test also clicks the world mod list on the way in.
"""
import re
import time

from fixtures import shared_game
from helpers import HELPERS, action_menu, arena, count_at, count_carried, give, open_crafting, spawn, wait_until
from tmux_game import Game


def _fresh(g):
    assert g.lua(
        "local u=gapi.get_avatar() u:clear_bionics() u:clear_mutations() "
        "u:clear_morale() u:drop_all_items() out('ok')"
    ) == ["ok"]
    arena(g)
    give(g, "glass_shard", 3)


def _crafted(g):
    return count_carried(g, "glass_shard_trap") + count_at(g, 0, 0, "glass_shard_trap")


def _row_of(g, text, max_x=32):
    """First screen row where `text` starts inside a menu's left list column."""
    for y, line in enumerate(g.screen().splitlines()):
        index = line.find(text)
        if y >= 5 and 0 <= index < max_x:
            return index, y
    raise AssertionError(f"no list row for {text!r}\n{g.screen()}")


def _points_line(screen):
    return next((line for line in screen.splitlines() if "Points left:" in line), "")


def _open_filtered_recipe(g, name):
    open_crafting(g)
    g.wait_for("[f]ilter", timeout=15)
    g.keys("f", delay=0.8)
    g.wait_for("Search:", timeout=10)
    g.type(name)
    g.keys("Enter", delay=1.5)
    g.wait_for("Searched", timeout=15)


def _modern_crafting():
    # Few rows keep the default recipe list longer than its viewport, so the scrollbar is drawn.
    return shared_game("bn-e2e-creation-crafting-modern", cols=80, rows=24,
                       define=HELPERS, setup=_fresh,
                       options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"})


def _modern_construction():
    return shared_game("bn-e2e-creation-construction-modern",
                       define=HELPERS, setup=_fresh,
                       options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"})


def _classic_menus():
    return shared_game("bn-e2e-creation-menus-classic",
                       define=HELPERS, setup=_fresh,
                       options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false"})


def _open_construction(g):
    action_menu(g, "Craft", "Construct Terrain")
    g.wait_for("Construction speed", timeout=15)
    return _window_left(g.screen())


def _window_left(screen):
    """Screen column of the construction window's left border."""
    top = next((line for line in screen.splitlines() if "┴" in line), None)
    assert top is not None, screen
    return top.index("╭")


def test_modern_crafting_row_click_selects_then_crafts(_g):
    with _modern_crafting() as g:
        _fresh(g)
        spawn(g, 3, 0, "glass_shard", 3)
        _open_filtered_recipe(g, "glass shard trap")
        x, y = _row_of(g, "glass shard trap")
        before = _crafted(g)
        g.click(x, y)
        assert "Searched" in g.screen(), (
            "the first row click must only select and keep the menu\n" + g.screen())
        assert _crafted(g) == before, "the first row click must not craft"
        g.click(x, y)
        assert wait_until(lambda: _crafted(g) == before + 1, timeout=45), g.screen()
        assert not g.dismiss_error_popup(), "crafting by click must not raise an error"


def test_modern_crafting_scrollbar_moves_selection_without_crafting(_g):
    with _modern_crafting() as g:
        _fresh(g)
        spawn(g, 3, 0, "glass_shard", 3)
        open_crafting(g)
        g.wait_for("[f]ilter", timeout=15)
        g.keys("f", delay=0.8)
        g.wait_for("Search:", timeout=10)
        g.type("a")
        g.keys("Enter", delay=1.5)
        g.wait_for("Searched", timeout=15)
        before_screen = g.screen()
        before_crafted = _crafted(g)
        # Left list scrollbar sits in window column 0; the window starts at screen row 5.
        g.click(0, 10)
        after_track = g.screen()
        assert before_screen != after_track, "a scrollbar track click must move the list"
        assert _crafted(g) == before_crafted, "scrollbar clicks must never craft"
        g.click(0, 5)
        after_arrow = g.screen()
        assert after_arrow != after_track, "the up arrow must step the selection"
        assert _crafted(g) == before_crafted, "scrollbar clicks must never craft"
        g.keys("Escape", delay=0.8)


def test_modern_construction_scrollbar_and_tab_click(_g):
    with _modern_construction() as g:
        _fresh(g)
        left = _open_construction(g)
        before = g.screen()
        g.click(left, 10)
        moved = g.screen()
        assert "Construction speed" in moved, "a scrollbar click must keep the menu open\n" + moved
        assert moved != before, "a construction scrollbar click must move the list"

        # The first list row click only selects; it must not start a construction.
        g.click(left + 5, 8)
        assert "Construction speed" in g.screen(), (
            "the first list row click must only select\n" + g.screen())

        # Click a category tab that is not the selected one (it may be empty).
        row = moved.splitlines()[1]
        tabs = [(m.start(), m.group(1)) for m in re.finditer(r"│([^│]+)│", row)]
        selected = re.search(r"<│([^│]+)│>", row)
        assert selected, row
        target = next(((x, name) for x, name in tabs
                       if name != selected.group(1)), None)
        assert target, row
        g.click(target[0] + 1, 1)
        switched = g.screen()
        assert f"<│{target[1]}│>" in switched, (
            f"clicking tab {target[1]!r} must select it\n" + switched)
        g.keys("Escape", delay=0.8)


def test_classic_crafting_and_construction_ignore_mouse(_g):
    with _classic_menus() as g:
        _fresh(g)
        left = _open_construction(g)
        before = g.screen()
        g.click(left, 10)
        g.click(left + 5, 8)
        assert g.screen() == before, "Classic construction must ignore mouse clicks"

        g.keys("Escape", delay=0.8)
        open_crafting(g)
        g.wait_for("[f]ilter", timeout=15)
        before = g.screen()
        g.click(0, 12)
        g.click(3, 8)
        assert g.screen() == before, "Classic crafting must ignore mouse clicks"
        g.keys("Escape", delay=0.8)


def _reach_custom_character(g):
    """Follow the fork's default menu flow to the character-creation scenario page."""
    for _ in range(240):
        s = g.screen()
        if "Select your language" in s:
            g.keys("1", delay=0.5)
        elif "[New Game]" in s or "Play Now" in s:
            line = next((l for l in s.splitlines() if "Custom Character" in l), "")
            if "Custom Character" in line and "»" in line:
                g.keys("Enter", delay=1)
                continue
            g.keys("Down", delay=0.2)
        elif "Welcome to Bright Nights" in s:
            g.keys("Escape", delay=1)
        elif "How should death work" in s:
            g.keys("r", delay=1)
        elif not s.strip():
            g.keys("F5", delay=1)
        elif "World Mods" in s and "Mod List" in s:
            # The available-mod list starts at screen column 30 in the centred 80-column dialog.
            g.click(30, 14)
            assert "Mod List" in g.screen(), "a world mod scrollbar click must keep the dialog\n" + g.screen()
            g.keys("Tab", "Tab", delay=1)
        elif "World Options" in s:
            g.keys("Tab", delay=1)
        elif "SCENARIO" in s and "POINTS" in s and "World" not in s:
            return
        else:
            time.sleep(0.5)
    raise AssertionError("could not reach character creation\n" + g.screen())


def test_modern_creation_traits_scrollbar_and_first_click_are_safe(_g):
    g = Game(name="bn-e2e-creation-mouse", cols=140, rows=45,
             options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"})
    try:
        _reach_custom_character(g)
        for _ in range(16):
            if "<│TRAITS│>" in g.screen():
                break
            g.keys("Tab", delay=0.7)
        screen = g.screen()
        assert "<│TRAITS│>" in screen, screen
        points_before = _points_line(screen)
        assert points_before, screen

        # First trait column scrollbar: arrows and track must not spend points.
        g.click(0, 10)
        g.click(0, 5)
        screen = g.screen()
        assert "<│TRAITS│>" in screen, screen
        assert _points_line(screen) == points_before, (
            "scrollbar clicks must not toggle traits or spend points\n" + screen)

        # A row click only selects; it must not toggle the initially selected trait.
        g.click(5, 10)
        screen = g.screen()
        assert "<│TRAITS│>" in screen, screen
        assert _points_line(screen) == points_before, (
            "the first row click must not toggle a trait\n" + screen)
        g.keys("Escape", delay=0.8)
        if "Return to main menu?" in g.screen():
            g.keys("Enter", delay=1)
    finally:
        g.close()


TESTS = [
    test_modern_crafting_row_click_selects_then_crafts,
    test_modern_crafting_scrollbar_moves_selection_without_crafting,
    test_modern_construction_scrollbar_and_tab_click,
    test_classic_crafting_and_construction_ignore_mouse,
    test_modern_creation_traits_scrollbar_and_first_click_are_safe,
]
