"""The fusion HUD: status card, ribbon and loadout deck over the map, ruled sidebar beside it."""
import re

from fixtures import shared_game
from helpers import HELPERS, arena, empty_inventory
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


TESTS = [test_fusion_layout_draws_overlays_and_ruled_sidebar,
         test_fusion_is_the_fresh_default_and_small_screens_fall_back]
