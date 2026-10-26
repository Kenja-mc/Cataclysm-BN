"""The Controls strip follows the input context, including full-screen menus."""
from fixtures import shared_game
from helpers import (HELPERS, action_menu, arena, empty_inventory, give, settle,
                     spawn, wait_until)


def setup(game):
    empty_inventory(game)
    arena(game)
    give(game, "pipe")
    assert game.lua("gapi.get_avatar():learn_recipe(RecipeId.new('tinfoil_hat')) out('ok')") == ["ok"]
    settle(game)


def footer(game):
    return game.screen().splitlines()[-1].strip()


def assert_footer(game, *hints):
    def matches():
        line = footer(game)
        return line.startswith("Controls:") and all(hint in line for hint in hints)
    assert wait_until(matches, timeout=15), game.screen()
    line = footer(game)
    assert " move " not in line and "throttle" not in line, line
    for internal in ("ANY_INPUT", "COORDINATE", "MOUSE_MOVE", "SEC_SELECT", "Unbound"):
        assert internal not in line, line


def assert_map(game):
    assert wait_until(lambda: not footer(game).startswith("Controls:") and
                      " move " in game.screen(), timeout=15), game.screen()


def test_context_keyhints_inventory_pickup_crafting_and_look(_game):
    with shared_game("bn-e2e-context-keyhints", define=HELPERS, setup=setup, rows=50,
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false",
                              "CONTEXT_KEYHINTS": "true", "NEW_PICKUP_MENU": "false",
                              "HIGHLIGHT_UNREAD_RECIPES": "false"}) as game:
        assert_map(game)
        game.wait_for("g pick up", timeout=15)
        hints = game.screen()
        assert "safe mode" in hints and "auto travel" in hints, \
            "safe mode and auto travel must show their keys in the hints:\n" + hints
        game.keys("i")
        game.wait_for("Inventory", timeout=15)
        assert_footer(game, "F5 Craft", "Confirm your selection")
        game.keys("Escape")
        assert_map(game)

        spawn(game, 0, 0, "rock")
        spawn(game, 0, 0, "stick")
        game.keys("G")
        game.wait_for("Pick up", timeout=15)
        assert_footer(game, ", Select all", "g Confirm Choice")
        game.keys("Escape")
        assert_map(game)

        game.keys("i")
        assert_footer(game, "F5 Craft")
        game.keys("F5")
        game.wait_for("[f]ilter", timeout=15)
        assert_footer(game, "b Batch crafting", "f Filter")
        game.keys("Escape")
        assert_map(game)

        game.keys("Enter")
        game.wait_for("Interact", timeout=15)
        assert_footer(game, "Confirm Choice", "Cancel menu")
        game.keys("Escape")
        assert_map(game)
        action_menu(game, "Look", "Look around")
        assert_footer(game, "0 Center On Character")
        game.keys("Escape")
        assert_map(game)

        assert game.lua("local a=gapi.get_avatar() local gun=a:create_item(ItypeId.new('model_10_revolver'),-1) "
                        "gun:ammo_set(ItypeId.new('38_special'),6) out(a:wield(gun))") == ["true"]
        settle(game)
        game.keys("f")
        assert_footer(game, "f Fire Weapon")
        game.keys("Escape")
        assert_map(game)


def test_context_keyhints_off_keeps_map_strip(_game):
    with shared_game("bn-e2e-context-keyhints-off", define=HELPERS, setup=setup,
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false",
                              "CONTEXT_KEYHINTS": "false"}) as game:
        assert_map(game)
        game.keys("i")
        game.wait_for("Inventory", timeout=15)
        assert not footer(game).startswith("Controls:"), game.screen()
        game.keys("Escape")
        assert_map(game)


def test_context_keyhints_classic_uses_classic_bindings(_game):
    with shared_game("bn-e2e-context-keyhints-classic", define=HELPERS, setup=setup,
                     options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false",
                              "CONTEXT_KEYHINTS": "true"}) as game:
        game.keys("i")
        game.wait_for("Inventory", timeout=15)
        assert_footer(game, "Confirm your selection", "Cancel")
        assert "F5 Craft" not in footer(game), game.screen()
        game.keys("Escape")
        assert_map(game)


TESTS = [test_context_keyhints_inventory_pickup_crafting_and_look,
         test_context_keyhints_off_keeps_map_strip,
         test_context_keyhints_classic_uses_classic_bindings]
