"""Modern mouse clicks in crafting, construction and character creation.

Covers the shared scrollbar geometry (track jumps, arrows step one row), the
click-then-confirm rule for action rows, and that Classic keeps its keyboard-only
menus.  The creation test also clicks the world mod list on the way in.
"""
import re
import time

from fixtures import shared_game
from helpers import HELPERS, action_menu, arena, count_at, count_carried, give, open_crafting, wait_until
from menu_scrollbars import find_scrollbar
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


def _click_creation_tab(g, name):
    """Click a visible top tab and wait for its page."""
    row = g.screen().splitlines()[1]
    match = re.search(r"│" + re.escape(name) + r"│", row)
    assert match, f"no {name} tab in:\\n{row}"
    g.click(match.start() + 1, 1)
    assert g.wait_for(f"<│{name}│>", timeout=10), g.screen()


def _points_line(screen):
    # The same row also describes the highlighted trait's cost; selection changes that
    # description without spending points.
    match = re.search(r"Points left:\s*([-+\d=]+)", screen)
    return match.group(1) if match else ""


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
        # Lua opens the console and dismisses menus, so count only outside the recipe UI.
        before = _crafted(g)
        _open_filtered_recipe(g, "glass shard trap")
        x, y = _row_of(g, "glass shard trap")
        g.click(x, y)
        assert "Searched" in g.screen(), (
            "the first row click must only select and keep the menu\n" + g.screen())
        g.click(x, y)
        g.wait_gone("Searched", timeout=15)
        assert wait_until(lambda: _crafted(g) == before + 1, timeout=45), g.screen()
        assert not g.dismiss_error_popup(), "crafting by click must not raise an error"


def test_modern_crafting_scrollbar_moves_selection_without_crafting(_g):
    with _modern_crafting() as g:
        _fresh(g)
        before_crafted = _crafted(g)
        open_crafting(g)
        g.wait_for("[f]ilter", timeout=15)
        g.keys("f", delay=0.8)
        g.wait_for("Search:", timeout=10)
        g.type("a")
        g.keys("Enter", delay=1.5)
        g.wait_for("Searched", timeout=15)
        before_screen = g.screen()
        bar = find_scrollbar(before_screen)
        assert bar, "the recipe list must draw a scrollbar\n" + before_screen
        top, bottom, x = bar
        g.click(x, bottom - 1)
        after_track = g.screen()
        assert "Searched" in after_track, "a scrollbar track must not craft\n" + after_track
        assert before_screen != after_track, "a scrollbar track click must move the list"
        g.click(x, top)
        after_arrow = g.screen()
        assert "Searched" in after_arrow, "a scrollbar arrow must not craft\n" + after_arrow
        assert after_arrow != after_track, "the up arrow must step the selection"
        g.keys("Escape", delay=0.8)
        assert _crafted(g) == before_crafted, "scrollbar clicks must never craft"


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
        after_row = g.screen()
        assert "Construction speed" in after_row, (
            "the first list row click must only select\n" + after_row)
        # A wheel notch moves the cursor one row, with no release packet.
        g.type(f"\x1b[<65;{left + 6};9M", delay=1)
        assert g.screen() != after_row, "a wheel notch must move the construction cursor"

        # Click a category tab that is not the selected one (it may be empty).
        row = g.screen().splitlines()[1]
        tabs = [(m.start() + left, m.group(1))
                for m in re.finditer(r"│([^│]+)│", row[left:])]
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
        elif "Are you SURE you're finished" in s:
            g.keys("Left", "Enter", delay=1)
        elif "Finalize World" in s and "World Name" in s:
            g.keys("Tab", delay=1)
        elif "SCENARIO" in s and "POINTS" in s and "Points left:" in s:
            return
        elif ("[New Game]" in s or "Play Now" in s) and "World Mods" not in s:
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
            row_four = g.screen().splitlines()[4]
            tabs = [m.start() for m in re.finditer(r"\[[^]]+\]", row_four)]
            if tabs:
                g.click(tabs[-1] + 1, 4)
                assert "Mod List" in g.screen(), (
                    "a mod category tab click must keep the dialog\n" + g.screen())
            g.keys("Tab", "Tab", delay=1)
        elif "World Options" in s:
            g.keys("Tab", delay=1)
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

        # Top tabs navigate through the existing pages; they never spend points.
        _click_creation_tab(g, "STATS")
        g.click(5, 6)
        assert "<│STATS│>" in g.screen(), g.screen()

        _click_creation_tab(g, "OVERVIEW")
        g.click(5, 6)
        g.click(5, 6)
        assert g.wait_for("Enter name.", timeout=10), g.screen()
        g.keys("Escape", delay=0.6)
        assert "<│OVERVIEW│>" in g.screen(), g.screen()

        _click_creation_tab(g, "POINTS")
        pool_before = _points_line(g.screen())
        screen = g.screen()
        pool_line = next(line for line in screen.splitlines() if "Single pool" in line)
        pool_x, pool_y = pool_line.index("Single pool"), next(
            y for y, line in enumerate(screen.splitlines()) if "Single pool" in line)
        g.click(pool_x, pool_y)
        assert _points_line(g.screen()) == pool_before, (
            "the first pool click must only select\n" + g.screen())
        g.click(pool_x, pool_y)
        pool_after = _points_line(g.screen())
        assert pool_after and pool_after != pool_before, (
            "the second click must apply the pool like Enter\n" + g.screen())
        assert "=" not in pool_after, "single pool display must be applied\n" + g.screen()

        _click_creation_tab(g, "TRAITS")
        assert _points_line(g.screen()) == pool_after, g.screen()
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
