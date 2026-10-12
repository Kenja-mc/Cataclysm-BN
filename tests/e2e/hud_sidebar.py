"""Weather ownership keeps narrow classic facts without duplicating the clock or wind."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from helpers import HELPERS, arena, give, settle
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
                                         "HUD_COMBAT_BOX": "off", "HUD_ICONS": "ascii"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        give(game, "diving_watch", 1)
        for cols in (90, 140, 90):
            subprocess.run(["tmux", "resize-window", "-t", game.name, "-x", str(cols), "-y", "45"], check=True)
            settle(game)
            screen = game.screen()
            sidebar = "\n".join(line[cols - 44:] for line in screen.splitlines())
            clocks = re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?\b", screen)
            assert len(clocks) == 1, "the visible clock must not be duplicated:\n" + screen
            assert "? all keys" in sidebar, "the full-controls entry must remain discoverable:\n" + screen
            assert "n explore" in sidebar, "prior controls hints must remain visible:\n" + screen
            narrow = cols == 90
            assert bool(re.search(r"Wind\s*:", sidebar)) == narrow, screen
            assert bool(re.search(r"(Spring|Summer|Autumn|Winter),\s*Day\s+\d+", sidebar)) == narrow, screen
            assert bool(re.search(r"Temp\s*:", sidebar)) == narrow, screen
    finally:
        game.close()


TESTS = [test_classic_weather_resize_preserves_facts_and_help]
