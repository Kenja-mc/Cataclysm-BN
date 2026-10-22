from contextlib import contextmanager

from aim_reticle import action_clock
from fixtures import shared_game
from helpers import HELPERS, arena, empty_inventory, give
from inventory_mouse import display_name, row_of, wielded


@contextmanager
def inventory_game(name, scheme="modern"):
    with shared_game(f"bn-e2e-inventory-{name}", define=HELPERS, setup=inventory_setup,
                     options={"CONTROL_SCHEME": scheme, "SAFEMODE": "false",
                              "HIGHLIGHT_UNREAD_RECIPES": "false"}) as game:
        yield game


def inventory_setup(game):
    empty_inventory(game)
    arena(game)


def browse_craft_and_cancel(game):
    before = action_clock(game)
    game.keys("i", delay=1)
    screen = game.screen()
    assert "Inventory" in screen, screen
    game.keys("F5", delay=1.5)
    game.wait_for("[f]ilter", timeout=10)
    game.keys("f", delay=0.6)
    game.wait_for("Search:", timeout=10)
    game.type("tinfoil hat")
    game.keys("Enter", delay=1)
    screen = game.screen()
    assert "tinfoil hat" in screen and "aluminum foil" in screen, (
        "Craft must open the real recipe browser, including recipe requirements:\n" + screen)
    game.keys("Escape", delay=0.8)
    assert action_clock(game) == before, "opening, browsing and canceling crafting must be free"


def test_modern_inventory_crafts_with_empty_or_carried_inventory(_game):
    with inventory_game("craft") as game:
        assert game.lua("gapi.get_avatar():learn_recipe(RecipeId.new('tinfoil_hat')) out('ok')") == ["ok"]
        assert game.lua("out(#gapi.get_avatar():all_items(false))") == ["0"]
        before = action_clock(game)
        game.keys("i", delay=1)
        screen = game.screen()
        assert "Inventory" in screen, "i must immediately show the item inventory:\n" + screen
        game.keys("Escape", delay=0.6)
        assert action_clock(game) == before, "canceling an empty inventory must be free"
        browse_craft_and_cancel(game)
        assert game.lua("out(#gapi.get_avatar():all_items(false))") == ["0"]

        give(game, "pipe")
        pipe = display_name(game, "pipe")
        game.keys("i", delay=1)
        screen = game.screen()
        assert pipe in screen, "i must show carried items, not a second launcher menu:\n" + screen
        game.keys("Escape", delay=0.6)
        browse_craft_and_cancel(game)
        assert wielded(game) == [""], "browsing crafting must not equip the carried weapon"


def exercise_inventory_wield(game, key):
    # Leave enough moves to compare exact wield costs.
    result = game.lua(
        "local a=gapi.get_avatar() local it=a:create_item(ItypeId.new('pipe'),-1) "
        "a:set_moves(100000) local before=a:get_moves() "
        "local ok=a:wield(it) out(ok,before-a:get_moves())")
    assert len(result) == 1 and result[0].startswith("true,"), result
    expected = int(result[0].split(",")[1])
    assert expected > 0, "the real wield action must have a move cost"
    assert game.lua("local a=gapi.get_avatar() a:drop_all_items() a:set_moves(100000) out('ok')") == ["ok"]
    arena(game)
    give(game, "pipe")
    pipe = display_name(game, "pipe")
    before = action_clock(game)
    game.keys("i", delay=1)
    assert pipe in game.screen(), game.screen()
    game.click(*row_of(game, pipe), button=2)
    screen = game.screen()
    assert "Wield" in screen and "Drop" in screen, "the existing item action menu must open:\n" + screen
    game.keys(key, delay=1)
    assert wielded(game) == ["pipe"], "the item menu's Wield action must actually equip the selected weapon"
    after = action_clock(game)
    assert after[0] == before[0], "the fixture must retain enough moves to measure the exact cost"
    assert after[1] - before[1] == expected, (
        f"inventory Wield must preserve the real move cost: expected {expected}, got {after[1] - before[1]}")


def test_modern_inventory_item_action_equips_with_normal_cost(_game):
    with inventory_game("wield") as game:
        exercise_inventory_wield(game, "h")


def test_classic_inventory_has_no_craft_hub(_game):
    with inventory_game("classic", "classic") as game:
        before = action_clock(game)
        game.keys("i", delay=1)
        assert "Inventory" in game.screen(), game.screen()
        assert "Craft" not in game.screen(), "Classic inventory must not gain the Modern hub command"
        game.keys("F5", delay=0.6)
        assert "Inventory" in game.screen(), "F5 must not open crafting in Classic inventory"
        game.keys("Escape", delay=0.6)
        assert action_clock(game) == before, "canceling Classic inventory must remain free"
        give(game, "pipe")
        before = action_clock(game)
        game.keys("i", "Enter", delay=1)
        assert "Wield" in game.screen(), game.screen()
        game.keys("w", delay=1)
        assert wielded(game) == ["pipe"], "Classic item-menu Wield must remain unchanged"
        assert action_clock(game) > before, "Classic Wield must still spend moves"


TESTS = [test_modern_inventory_crafts_with_empty_or_carried_inventory,
         test_modern_inventory_item_action_equips_with_normal_cost,
         test_classic_inventory_has_no_craft_hub]
