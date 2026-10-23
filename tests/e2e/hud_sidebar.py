import json
import os
import re
import tempfile
from pathlib import Path

from helpers import HELPERS, action_menu, arena, give
from tmux_game import Game, start_new_game
from hud_status import regions, resized_frame


def test_classic_weather_resize_preserves_facts_and_help(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-weather-layout-"))
    config = userdir / "config"
    config.mkdir()
    (config / "panel_options.json").write_text(json.dumps([{
        "current_layout_id": "classic",
        "layouts": [{"layout_id": "classic", "panels": [
            {"name": name, "toggle": True} for name in ("Wind", "Time", "Lighting", "Controls")
        ]}],
    }]))
    game = Game(name=f"bn-e2e-weather-layout-{os.getpid()}", cols=90, rows=45,
                userdir=userdir, options={"SAFEMODE": "false", "HUD_WEATHER_BOX": "top_left",
                                         "HUD_COMBAT_BOX": "off", "HUD_VEHICLE_BOX": "off",
                                         "HUD_ICONS": "ascii", "SIDEBAR_POSITION": "right",
                                         "CONTROL_SCHEME": "classic"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        give(game, "diving_watch", 1)
        for cols in (90, 140, 80, 140, 90):
            game.resize(cols, 45)

            def ready(screen):
                sidebar = regions(screen, cols)[1]
                return "all keys" in sidebar and "khjl move" in sidebar

            screen = resized_frame(game, cols, 45, ready)
            clocks = re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?\b", screen)
            assert len(clocks) == 1, "the visible clock must not be duplicated:\n" + screen
            # Fit policy can retain an overlay on a smaller map; facts, not breakpoints, are the contract.
            for label in (r"Light(?:ing)?", "Wind"):
                readings = re.findall(r"\b" + label + r"\s*:\s*(\S+)", screen)
                assert len(readings) == 1, f"{label} must stay visible exactly once:\n{screen}"
            assert len(re.findall(r"\b(?:Spring|Summer|Autumn|Winter)(?:,\s*Day)?\s+\d+", screen)) == 1, screen
            assert len(re.findall(r"[-+]?\d+(?:\.\d+)?\s*°\s*[CFK]", screen)) == 1, \
                "the watch's temperature must stay visible without duplication:\n" + screen
            assert "all keys" in screen and "khjl move" in screen, \
                "Classic help must survive resizing:\n" + screen
    finally:
        game.close()


def test_modern_reaches_sidebar_options_from_the_menu(_g):
    """Modern leaves the sidebar options key unbound, so the Enter menu must still reach them."""
    game = Game(name=f"bn-e2e-sidebar-route-{os.getpid()}", options={
        "SAFEMODE": "false", "SHOW_WELCOME": "false", "CONTROL_SCHEME": "modern"})
    try:
        start_new_game(game)
        action_menu(game, "Misc", "Sidebar Options")
        game.wait_for("SIDEBAR OPTIONS")
    finally:
        game.close()


TESTS = [test_classic_weather_resize_preserves_facts_and_help,
         test_modern_reaches_sidebar_options_from_the_menu]
