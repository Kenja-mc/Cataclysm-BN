"""The fusion HUD: status card, ribbon and loadout deck over the map, ruled sidebar beside it."""
import re

from fixtures import shared_game
from helpers import HELPERS, arena, bub_pos, empty_inventory, give
from hud_status import healthy
from tmux_game import Game, start_new_game

OPTIONS = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false", "SHOW_WELCOME": "false",
           "SHOW_TIPS": "false", "ANIMATIONS": "false"}


def fusion_setup(game):
    game.resize(160, 45)
    empty_inventory(game)
    arena(game)
    healthy(game)
    assert game.lua("local a=gapi.get_avatar() "
                    "a:add_effect(EffectTypeId.new('bleed'),TimeDuration.from_minutes(30),"
                    "BodyPartTypeId.new('arm_l'),1) out('ok')") == ["ok"]


def rule_rows(screen, title):
    return [line for line in screen.splitlines() if re.search(r"├─* *" + title + r"\b", line)]


def assert_fusion(screen):
    for card in ("STATUS", "LOADOUT"):
        assert re.search(r"╭[^\n]*\b" + card + r"\b", screen), f"{card} card missing:\n{screen}"
    for title in ("BODY", "AROUND", "LOG"):
        assert len(rule_rows(screen, title)) == 1, f"one {title} rule expected:\n{screen}"
    assert "bleeding" in screen, "the wound word belongs in BODY:\n" + screen
    assert "all keys" in screen, "the deck carries the key hints:\n" + screen
    # The floating windows and the old sidebar panels are gone.
    for old in ("Compass", "Movement", "Stats ", "Weight"):
        assert old not in screen, f"{old!r} belongs to another layout:\n{screen}"


def test_fusion_layout_draws_overlays_and_ruled_sidebar(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        game.settle_screen()
        assert_fusion(game.screen())


def test_fusion_is_the_fresh_default_and_small_screens_fall_back(_g):
    # No panel_options.json is seeded: this is the real first-run layout.
    game = Game("bn-e2e-fusion-default", options=OPTIONS, layout=None, cols=160, rows=45)
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        fusion_setup(game)
        game.settle_screen()
        assert_fusion(game.screen())
        game.resize(100, 30)
        game.settle_screen()
        small = game.screen()
        assert "LOADOUT" not in small and not rule_rows(small, "BODY"), \
            "below 140x36 the grouped layout must replace fusion:\n" + small
        game.resize(160, 45)
        game.settle_screen()
        assert_fusion(game.screen())
    finally:
        game.close()


def wielded(game):
    return game.lua("local n='' for _,w in ipairs(gapi.get_avatar():wielded_items()) do n=n..w:get_type():str() end out(n)")[0]


def test_hotbar_slot_wields_its_item_and_empty_slot_is_inert(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        give(game, "knife_combat", 1)
        before = bub_pos(game)
        game.keys("1", delay=0.6)
        assert bub_pos(game) == before, "an empty slot must not move the character"
        assert "Hotbar slot 1 is empty" in game.screen(), game.screen()
        assert game.lua("gapi.get_avatar():set_value('hotbar_2','knife_combat') out('ok')") == ["ok"]
        game.settle_screen()
        game.keys("2", delay=0.8)
        game.settle_screen()
        assert "knife" in wielded(game), "slot 2 should wield the combat knife"
        assert bub_pos(game) == before


def test_hotbar_assign_menu_stores_the_chosen_item(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        give(game, "knife_combat", 1)
        game.keys("C-t", delay=0.6)
        game.wait_for("Assign which hotbar slot", timeout=15)
        game.keys("3", delay=0.8)
        game.wait_for("Put which item", timeout=15)
        game.keys("Enter", delay=0.8)
        game.settle_screen()
        assert game.lua("out(gapi.get_avatar():get_value('hotbar_3'))") == ["knife_combat"], game.screen()


def test_clicking_a_hotbar_slot_uses_it_and_overlay_clicks_stay_off_the_map(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        give(game, "knife_combat", 1)
        assert game.lua("gapi.get_avatar():set_value('hotbar_2','knife_combat') out('ok')") == ["ok"]
        game.settle_screen()
        before = bub_pos(game)
        for y, line in enumerate(game.screen().splitlines()):
            if "╭─2" in line:
                x = line.index("╭─2")
                break
        else:
            raise AssertionError("hotbar slot 2 missing:\n" + game.screen())
        game.click(x + 2, y + 1)
        game.settle_screen()
        assert "knife" in wielded(game), "a click on the slot should use it:\n" + game.screen()
        assert bub_pos(game) == before
        # A click on the status card is swallowed, never walked to or selected on the map.
        game.click(5, 2)
        assert bub_pos(game) == before


def test_vehicle_card_replaces_the_floating_vehicle_window_while_aboard(_g):
    from vehicle_box import spawn_vehicle
    game = Game(name="bn-e2e-fusion-vehicle", layout="fusion", cols=160, rows=45,
                options={**OPTIONS, "USE_METRIC_SPEEDS": "mph"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        game.settle_screen()
        assert "VEHICLE" not in game.screen(), game.screen()
        spawn_vehicle(game)
        screen = game.screen()
        assert re.search(r"╭[^\n]*\bVEHICLE\b", screen), screen
        assert "Azimuth" in screen and "Speed: 0 mph" in screen, screen
    finally:
        game.close()


TESTS = [test_vehicle_card_replaces_the_floating_vehicle_window_while_aboard,
         test_clicking_a_hotbar_slot_uses_it_and_overlay_clicks_stay_off_the_map,
         test_hotbar_slot_wields_its_item_and_empty_slot_is_inert,
         test_hotbar_assign_menu_stores_the_chosen_item,
         test_fusion_layout_draws_overlays_and_ruled_sidebar,
         test_fusion_is_the_fresh_default_and_small_screens_fall_back]
