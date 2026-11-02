"""The item action menu shows each action's time and main effect after its label."""
import re

from fixtures import shared_game
from helpers import HELPERS, arena, empty_inventory, give
from inventory_mouse import display_name, row_of

ON = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false", "ACTION_COSTS": "true"}
OFF = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false", "ACTION_COSTS": "false"}


def fresh(game):
    empty_inventory(game)
    arena(game)


def hold_pipe(game):
    assert game.lua(
        "local a=gapi.get_avatar() a:set_moves(100000) "
        "local p=a:create_item(ItypeId.new('pipe'),-1) out(a:wield(p))") == ["true"]


def loaded_gun(game):
    assert game.lua(
        "local a=gapi.get_avatar() local w=a:create_item(ItypeId.new('model_10_revolver'),-1) "
        "w:ammo_set(ItypeId.new('38_special'),6) out('ok')") == ["ok"]


def open_inventory(game):
    game.keys("i", delay=1)
    game.wait_for("Inventory", timeout=10)
    game.settle_screen()


def open_item_menu(game, name):
    game.click(*row_of(game, name), button=2)
    game.wait_for("Disassemble", timeout=10)
    game.settle_screen()
    return game.screen()


def close_item_menu(game):
    game.keys("Escape", delay=0.6)
    game.wait_for("Inventory", timeout=10)
    game.settle_screen()


def annotated_row(screen, label):
    match = re.search(rf"│[^│]*\b{label}\s{{2,}}[^\s│][^│]*│", screen)
    assert match, f"the {label} row must show its cost:\n{screen}"
    return match.group(0)


def test_item_menu_shows_times_and_where_the_held_weapon_goes(_game):
    with shared_game("bn-e2e-action-costs", options=ON, define=HELPERS, setup=fresh) as game:
        hold_pipe(game)
        pipe = display_name(game, "pipe")
        loaded_gun(game)
        give(game, "textbook_mechanics")
        give(game, "tshirt")
        gun = re.sub(r"\s*\(.*\)$", "", display_name(game, "model_10_revolver"))
        book = display_name(game, "textbook_mechanics")
        shirt = display_name(game, "tshirt")

        open_inventory(game)

        screen = open_item_menu(game, gun)
        assert re.search(r"\b\d+\s*s\b", annotated_row(screen, "Unload")), (
            "the Unload row must show its time:\n" + screen)
        wield = annotated_row(screen, "Wield")
        assert pipe in wield, f"Wield must name the held weapon: {wield!r}\n{screen}"
        assert "→" in wield or "drops" in wield, (
            f"Wield must say where the held weapon goes: {wield!r}\n{screen}")
        assert re.search(r"\b\d+\s*s\b", wield), f"Wield must show its time: {wield!r}\n{screen}"
        close_item_menu(game)

        screen = open_item_menu(game, book)
        assert re.search(r"\b\d+\s*(?:s|m|h)\b", annotated_row(screen, "Read")), (
            "the Read row must show its reading time:\n" + screen)
        close_item_menu(game)

        screen = open_item_menu(game, shirt)
        assert re.search(r"\b\d+\s*s\b", annotated_row(screen, "Wear")), (
            "the Wear row must show its time:\n" + screen)
        close_item_menu(game)

        game.keys("Escape", delay=0.6)
        empty_inventory(game)
        arena(game)


def test_item_menu_action_costs_off_leaves_rows_alone(_game):
    with shared_game("bn-e2e-action-costs-off", options=OFF, define=HELPERS, setup=fresh) as game:
        hold_pipe(game)
        pipe = display_name(game, "pipe")
        loaded_gun(game)
        gun = re.sub(r"\s*\(.*\)$", "", display_name(game, "model_10_revolver"))

        open_inventory(game)
        screen = open_item_menu(game, gun)
        assert "Unload" in screen and "Wield" in screen, screen
        assert not re.search(r"│[^│]*\b(?:Unload|Wield|Disassemble)\s{2,}[^\s│][^│]*│",
                             screen), (
            "the option off must leave the rows as they were:\n" + screen)
        assert f"{pipe} →" not in screen and f"{pipe} drops" not in screen, (
            "the option off must not name the held weapon's destination:\n" + screen)
        close_item_menu(game)

        game.keys("Escape", delay=0.6)
        empty_inventory(game)
        arena(game)


TESTS = [test_item_menu_shows_times_and_where_the_held_weapon_goes,
         test_item_menu_action_costs_off_leaves_rows_alone]
