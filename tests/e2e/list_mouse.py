import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fixtures import shared_game
from helpers import (HELPERS, action_menu, arena, choose_menu_entry, count_carried,
                     empty_inventory, give, spawn)
from inventory_mouse import display_name, row_of, wielded
from keybinding_search import _hotkey_for_action, _selected_pickup_item
from menu_space import cell_of
from tmux_game import Game, start_new_game


def _modern(name="bn-e2e-list-mouse-modern", **options):
    return shared_game(name, define=HELPERS,
                       options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false", **options})


def _classic():
    return shared_game("bn-e2e-list-mouse-classic", define=HELPERS,
                       options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false"})


def _single_pipe(g):
    arena(g)
    empty_inventory(g)
    arena(g)
    give(g, "pipe")


def test_double_click_runs_enter_action_and_its_prompt(_g):
    with _modern("bn-e2e-list-mouse-prompt") as g:
        for _ in range(6):
            if "Save and Quit" in g.screen():
                break
            g.keys("Escape", delay=0.8)
        g.wait_for("Save and Quit", timeout=15)
        choose_menu_entry(g, "Save and Quit")
        assert g.wait_for("Save and quit?", timeout=15), \
            "the double click must run the row's confirmation\n" + g.screen()
        g.keys("Escape", delay=0.8)
        g.wait_gone("Save and quit?", timeout=10)
        assert "Save and Quit" not in g.screen(), \
            "answering No to the double-clicked row must return to play\n" + g.screen()


def test_existing_space_and_user_rebind_stay_in_the_list(_g):
    userdir = tempfile.mkdtemp(prefix="bn-e2e-list-mouse-rebind-")
    game = None
    try:
        game = Game(name="bn-e2e-list-mouse-rebind", userdir=userdir,
                    options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"})
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        empty_inventory(game)
        arena(game)
        spawn(game, 0, 0, "rock")
        spawn(game, 0, 0, "stick")

        game.keys("C-g", delay=0.8)
        game.wait_for("Pick up")
        game.keys("Space", delay=1.2)
        assert "Pick up" not in game.screen(), "Space must still confirm a pickup row\n" + game.screen()
        assert count_carried(game, "rock") + count_carried(game, "stick") == 1

        game.lua("gapi.get_avatar():drop_all_items() out('ok')")
        arena(game)
        spawn(game, 0, 0, "rock")
        spawn(game, 0, 0, "stick")
        game.keys("C-g", delay=0.8)
        game.wait_for("Pick up")
        previous = _selected_pickup_item(game.screen())
        game.keys("?", delay=0.5)
        game.wait_for("Keybindings")
        game.type("next item", delay=0.2)
        game.wait_for("Next item:")
        game.keys("+", delay=0.3)
        hotkey = _hotkey_for_action(game.screen(), "Next item")
        game.keys(hotkey, delay=0.4)
        game.wait_for("New key for Next item", timeout=10)
        game.keys("Space", delay=0.4)
        game.wait_for("This key conflicts with", timeout=10)
        game.keys("y", "Enter", delay=0.5)
        game.wait_gone("This key conflicts with", timeout=10)
        game.keys("Escape", delay=0.5)
        game.wait_for("Save changes?")
        game.keys("y", "Enter", delay=0.8)
        game.wait_gone("Save changes?", timeout=10)
        game.wait_for("Pick up")

        current = _selected_pickup_item(game.screen())
        game.keys("Space", delay=0.6)
        assert "Pick up" in game.screen(), "the rebound Space must move, not confirm\n" + game.screen()
        moved = _selected_pickup_item(game.screen())
        assert moved != current, f"Space must run Next item: {current!r} -> {moved!r}"
    finally:
        if game is not None:
            game.close()
        shutil.rmtree(userdir, ignore_errors=True)


def test_option_off_keeps_single_click_confirm(_g):
    with _modern("bn-e2e-list-mouse-off", MODERN_LIST_MOUSE="false") as g:
        body = ("local m=UiList.new() m:title('List mouse off') "
                "m:add(10,'First choice') m:add(20,'Second choice') out(m:query())")
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(g.lua, body)
            g.wait_for("< List mouse off >", timeout=15)
            g.click(*cell_of(g, "Second choice"))
            assert result.result() == ["20"], "with the option off one click must confirm\n" + g.screen()


def test_option_off_keeps_single_click_inventory_pick(_g):
    with _modern("bn-e2e-list-mouse-inventory-off", MODERN_LIST_MOUSE="false") as g:
        _single_pipe(g)
        pipe = display_name(g, "pipe")
        action_menu(g, "Inventory", "Wield")
        assert "Wield item" in g.screen(), g.screen()
        g.click(*row_of(g, pipe))
        assert "Wield item" not in g.screen(), "with the option off one click must pick\n" + g.screen()
        assert wielded(g) == ["pipe"], wielded(g)


def test_right_click_leaves_a_list_without_an_action_menu(_g):
    with _modern("bn-e2e-list-mouse-right") as g:
        body = ("local m=UiList.new() m:title('List mouse right') "
                "m:add(10,'First choice') m:add(20,'Second choice') out(m:query())")
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(g.lua, body)
            g.wait_for("< List mouse right >", timeout=15)
            g.click(*cell_of(g, "Second choice"), button=2)
            assert result.result() == ["-1027"], "right click must still cancel a plain list\n" + g.screen()


def test_classic_ignores_list_row_clicks(_g):
    with _classic() as g:
        body = ("local m=UiList.new() m:title('List mouse classic') "
                "m:add(10,'First choice') m:add(20,'Second choice') out(m:query())")
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(g.lua, body)
            g.wait_for("< List mouse classic >", timeout=15)
            g.click(*cell_of(g, "Second choice"))
            assert "< List mouse classic >" in g.screen(), "Classic must ignore row clicks\n" + g.screen()
            g.keys("Down", "Enter", delay=1)
            assert result.result() == ["20"], "Classic must still confirm with the keyboard\n" + g.screen()


TESTS = [test_double_click_runs_enter_action_and_its_prompt,
         test_existing_space_and_user_rebind_stay_in_the_list,
         test_option_off_keeps_single_click_confirm,
         test_option_off_keeps_single_click_inventory_pick,
         test_right_click_leaves_a_list_without_an_action_menu,
         test_classic_ignores_list_row_clicks]
