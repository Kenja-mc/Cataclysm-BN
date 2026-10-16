import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from helpers import HELPERS, arena, give
from tmux_game import Game, start_new_game


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
            subprocess.run(["tmux", "resize-window", "-t", game.name, "-x", str(cols), "-y", "45"], check=True)
            for _ in range(100):
                screen = game.screen()
                terrain = "\n".join(line[:cols - 44] for line in screen.splitlines())
                clocks = re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?\b", screen)
                if bool(re.search(r"\bLight\s*:", terrain)) == (cols >= 90) and len(clocks) == 1:
                    break
                time.sleep(0.1)
            sidebar = "\n".join(line[cols - 44:] for line in screen.splitlines())
            clocks = re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?\b", screen)
            assert len(clocks) == 1, "the visible clock must not be duplicated:\n" + screen
            terrain = "\n".join(line[:cols - 44] for line in screen.splitlines())
            overlay = bool(re.search(r"\bLight\s*:", terrain))
            assert overlay == (cols >= 90), screen
            assert bool(re.search(r"Wind\s*:", sidebar)) == (not overlay), screen
            assert bool(re.search(r"(Spring|Summer|Autumn|Winter),\s*Day\s+\d+", sidebar)) == (not overlay), screen
            assert bool(re.search(r"Temp\s*:", sidebar)) == (not overlay), screen
    finally:
        game.close()


TESTS = [test_classic_weather_resize_preserves_facts_and_help]
