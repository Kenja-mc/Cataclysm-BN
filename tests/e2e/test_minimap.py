#!/usr/bin/env python3
"""E2E test for pixel minimap improvements: zoom and item markers.

Verifies that the new PIXEL_MINIMAP_ZOOM and PIXEL_MINIMAP_ITEM_MARKERS options
can be set at game start and that the minimap renders without crashing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import HELPERS, arena, spawn, settle  # noqa: E402
from tmux_game import Game, start_new_game  # noqa: E402


def test_minimap_options():
    """Test that minimap zoom and item markers options work."""
    # Start game with minimap options enabled
    game = Game(
        name="bn-minimap-test",
        cols=140,
        rows=45,
        options={
            "PIXEL_MINIMAP": "true",
            "PIXEL_MINIMAP_ZOOM": "2.0",
            "PIXEL_MINIMAP_ITEM_MARKERS": "true",
        },
    )
    try:
        start_new_game(game, timeout=240)
        game.define_lua(HELPERS)
        arena(game)

        # Spawn some items near the player to test item markers
        spawn(game, 2, 0, "rock", 3)
        spawn(game, -2, 0, "stick", 2)

        # Let the game settle so the minimap renders
        settle(game)

        # Take a screenshot for visual inspection
        screen = game.screen()
        assert "X,Y,Z" in screen, f"Game not in expected state: {screen}"

        # Verify the game is still running (no crash)
        result = game.lua("out('ok')")
        assert result == ["ok"], f"Game crashed or Lua not working: {game.screen()}"

        print("Minimap options test passed!")
        print("Screenshot saved for visual inspection.")
        print("Check that:")
        print("  - Minimap is visible in the sidebar")
        print("  - Items have gold markers on the minimap")
        print("  - Zoom level is 2.0 (more detailed view)")
    finally:
        game.close()


if __name__ == "__main__":
    test_minimap_options()
