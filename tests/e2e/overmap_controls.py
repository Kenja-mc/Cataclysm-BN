"""The map shortcut returns to play without confirming a destination."""
from aim_reticle import action_clock
from fixtures import shared_game
from helpers import HELPERS, arena, bub_pos


def test_m_toggles_overmap_without_travel(_g):
    with shared_game("bn-e2e-overmap-toggle", options={
        "CONTROL_SCHEME": "modern", "SAFEMODE": "false", "EDGE_SCROLL": "-1",
    }, define=HELPERS, setup=arena) as game:
        position = bub_pos(game)
        clock = action_clock(game)
        game.keys("m")
        game.wait_for("Center On Character")
        game.keys("d")
        game.keys("m")
        game.wait_gone("Center On Character")
        screen = game.screen()
        assert "Center On Character" not in screen, \
            "the overmap legend must be cleared after closing the map:\n" + screen
        assert "X,Y,Z" in screen or "Place" in screen, \
            "the game sidebar must be redrawn after closing the map:\n" + screen
        assert bub_pos(game) == position, "closing the map must not start travel"
        assert action_clock(game) == clock, "browsing and closing the map must not spend time"


TESTS = [test_m_toggles_overmap_without_travel]
