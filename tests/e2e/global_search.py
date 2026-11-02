import re

from fixtures import shared_game
from helpers import HELPERS, arena, bub_pos, settle
from map_mouse import mouse_view
from safe_click import see_everything

OPTIONS = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false", "EDGE_SCROLL": "-1"}
PALETTE = "Enter: run or select"
ACTION_MENU = "Actions"
BOTTOMS = ("╰", "└", "+")


def palette_footer(game):
    lines = game.screen().splitlines()
    hint = next((y for y, line in enumerate(lines) if PALETTE in line), None)
    assert hint is not None, f"the palette is not open:\n{game.screen()}"
    left = lines[hint].rfind("│", 0, lines[hint].index(PALETTE))
    bottom = next((y for y in range(hint, len(lines))
                   if len(lines[y]) > left and lines[y][left] in BOTTOMS), None)
    assert left >= 0 and bottom is not None, f"no palette box:\n{game.screen()}"
    return lines[bottom - 1][left:]


def palette_selection(game):
    found = re.search(r"(\d+)/(\d+)", palette_footer(game))
    assert found, f"no counter in the palette footer:\n{game.screen()}"
    return int(found.group(1)), int(found.group(2))


def match_total(game):
    if "Nothing matches." in palette_footer(game):
        return 0
    return palette_selection(game)[1]


def search_total(game, query):
    game.keys("C-f", delay=0.8)
    game.wait_for(PALETTE)
    game.type(query)
    game.settle_screen(minimum=0.4)
    total = match_total(game)
    game.keys("Escape", delay=0.6)
    game.wait_gone(PALETTE)
    return total


def test_ctrl_space_runs_a_map_control(_g):
    with shared_game("bn-e2e-global-search", options=OPTIONS, define=HELPERS) as game:
        game.keys("C-Space", delay=0.8)
        game.wait_for(PALETTE)
        game.type("main menu")
        game.settle_screen(minimum=0.4)
        assert palette_selection(game) == (1, 1), game.screen()
        game.keys("Enter", delay=1.0)
        game.wait_for("MAIN MENU")
        game.wait_gone(PALETTE)
        game.keys("Escape", delay=0.6)
        game.wait_gone("MAIN MENU")


def test_ctrl_f_escape_restores_the_cursor(_g):
    with shared_game("bn-e2e-global-search-escape", options=OPTIONS,
                     define=HELPERS) as game:
        arena(game)
        see_everything(game, True)
        settle(game)
        assert game.lua("local p=here(4,0) M:set_ter_at(p, TerId.new('t_floor'):int_id()) "
                        "M:set_furn_at(p, FurnId.new('f_chair'):int_id()) out('ok')") == ["ok"]
        game.keys("C-f", delay=0.8)
        game.wait_for(PALETTE)
        game.type("chair")
        game.wait_gone("Type to search.")
        game.wait_for("Mouse View")
        game.keys("Escape", delay=0.8)
        game.wait_gone(PALETTE)
        game.wait_gone("Mouse View")


def test_ctrl_f_runs_a_menu_control(_g):
    with shared_game("bn-e2e-global-search-menu", options=OPTIONS,
                     define=HELPERS) as game:
        game.keys("Enter", delay=0.8)
        game.wait_for(ACTION_MENU)
        game.keys("C-f", delay=0.8)
        game.wait_for(PALETTE)
        assert "Type to search." in game.screen(), game.screen()
        game.type("cancel")
        game.settle_screen(minimum=0.4)
        assert palette_selection(game) == (1, 1), game.screen()
        game.keys("Enter", delay=0.8)
        game.wait_gone(PALETTE)
        game.wait_gone(ACTION_MENU)


def test_ctrl_f_puts_the_cursor_on_a_detected_creature(_g):
    with shared_game("bn-e2e-global-search-creature", options=OPTIONS,
                     define=HELPERS) as game:
        arena(game)
        see_everything(game, True)
        settle(game)
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), "
                        "here(4,0)) out(m ~= nil)") == ["true"]
        position = bub_pos(game)

        game.keys("C-f", delay=0.8)
        game.wait_for(PALETTE)
        game.type("zombie")
        game.wait_for(", seen")
        game.keys("Enter", delay=1.0)
        game.wait_gone(PALETTE)

        assert "zombie" in mouse_view(game), game.screen()
        assert bub_pos(game) == position, "searching never moves the player"
        game.keys("Escape", delay=0.6)
        game.wait_gone("Mouse View")


def test_ctrl_f_tab_cycles_matches(_g):
    with shared_game("bn-e2e-global-search-furniture", options=OPTIONS,
                     define=HELPERS) as game:
        arena(game)
        see_everything(game, True)
        settle(game)
        assert game.lua("local function put(dx, id) local p=here(dx,0) "
                        "M:set_ter_at(p, TerId.new('t_floor'):int_id()) "
                        "M:set_furn_at(p, FurnId.new(id):int_id()) end "
                        "put(5,'f_chair') put(2,'f_armchair') out('ok')") == ["ok"]
        position = bub_pos(game)

        game.keys("C-f", delay=0.8)
        game.wait_for(PALETTE)
        game.type("chair")
        game.settle_screen(minimum=0.5)

        selected, total = palette_selection(game)
        assert total >= 2, f"expected at least two matches, got {selected}/{total}"
        assert selected == 1, f"the best match is selected first, got {selected}/{total}"

        game.keys("Tab", delay=0.8)
        game.settle_screen(minimum=0.4)
        assert palette_selection(game) == (2, total), "Tab cycles to the next instance"

        game.keys("BTab", delay=0.8)
        game.settle_screen(minimum=0.4)
        assert palette_selection(game) == (1, total), "Shift+Tab cycles back"

        game.keys("Enter", delay=1.0)
        game.wait_gone(PALETTE)
        assert "chair" in mouse_view(game), game.screen()
        assert bub_pos(game) == position, "selecting a tile only moves the cursor"
        game.keys("Escape", delay=0.6)
        game.wait_gone("Mouse View")


def test_ctrl_f_never_lists_what_is_behind_a_wall(_g):
    with shared_game("bn-e2e-global-search-privacy", options=OPTIONS,
                     define=HELPERS) as game:
        arena(game)
        see_everything(game, True)
        settle(game)
        build_the_wall = ("M:set_ter_at(here(1,0), TerId.new('t_wall'):int_id()) "
                          "M:set_ter_at(here(2,0), TerId.new('t_floor'):int_id()) out('ok')")
        assert game.lua(build_the_wall) == ["ok"]

        creatures_before = search_total(game, "zombie")
        items_before = search_total(game, "rock")
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(2,0)) "
                        "out(m ~= nil)") == ["true"]
        assert game.lua("local p=here(2,0) M:create_item_at(p, ItypeId.new('rock'), -1) "
                        "out(#M:get_items_at(p))") == ["1"]
        assert search_total(game, "zombie") == creatures_before, \
            "a wall-hidden creature must not be listed"
        assert search_total(game, "rock") == items_before, \
            "an item on unseen ground must not be listed"

        remove_the_wall = "M:set_ter_at(here(1,0), TerId.new('t_floor'):int_id()) out('ok')"
        assert game.lua(remove_the_wall) == ["ok"]
        assert search_total(game, "zombie") > creatures_before
        assert search_total(game, "rock") > items_before


TESTS = [test_ctrl_space_runs_a_map_control,
         test_ctrl_f_escape_restores_the_cursor,
         test_ctrl_f_runs_a_menu_control,
         test_ctrl_f_puts_the_cursor_on_a_detected_creature,
         test_ctrl_f_tab_cycles_matches,
         test_ctrl_f_never_lists_what_is_behind_a_wall]
