import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from tmux_game import Game, start_new_game
from helpers import action_menu



def sidebar(screen, cols, width):
    """The sidebar columns only, so map or log text cannot satisfy an assertion."""
    return "\n".join(line[cols - width:] for line in screen.splitlines())


def strip(cols, rows, layout="labels", spacers=False, panels=None):
    """A fresh Modern game with a saved sidebar layout."""
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-keyhints-"))
    config = userdir / "config"
    config.mkdir()
    (config / "panel_options.json").write_text(json.dumps([{
        "current_layout_id": "labels",
        "layouts": [{"layout_id": layout, "panels": panels or []}],
    }]))
    g = Game(name=f"bn-e2e-keyhints-{cols}x{rows}-{os.getpid()}", cols=140, rows=45,
             userdir=userdir,
             options={"SAFEMODE": "false", "SHOW_WELCOME": "false",
                      "CONTROL_SCHEME": "modern", "SIDEBAR_SPACERS": str(spacers).lower()})
    try:
        start_new_game(g)
        if layout != "labels":
            action_menu(g, "Debug", "Sidebar Options")
            g.wait_for("SIDEBAR OPTIONS")
            layouts = ("classic", "compact", "labels", "labels-narrow")
            g.keys("Right", *("Down" for _ in range(layouts.index(layout))),
                   "Enter", "Escape", delay=0.4)
        subprocess.run(["tmux", "resize-window", "-t", g.name,
                        "-x", str(cols), "-y", str(rows)], check=True)
        g.keys("x", delay=0.6)
        screen = g.screen()
        return sidebar(screen, cols, 44 if layout in ("labels", "classic") else 32), screen
    finally:
        g.close()


def move_hint_line(side):
    """Find the movement row without pinning its current shortcut spelling."""
    return next((line for line in side.splitlines() if re.search(r"\bmove\b", line)), "")


def test_controls_strip_shows_on_80x25(_g):
    """The minimum supported terminal height must retain the core controls."""
    side, screen = strip(80, 25)
    assert re.match(r"\s*\S+ +move\b", move_hint_line(side)), \
        "80x25 must still show how to move:\n" + screen


def test_controls_strip_shows_on_100x30(_g):
    side, screen = strip(100, 30)
    assert re.match(r"\s*\S+ +move\b", move_hint_line(side)), \
        "100x30 must still show how to move:\n" + screen


def test_controls_strip_survives_tall_layouts(_g):
    for layout in ("classic", "compact", "labels-narrow", "labels"):
        side, screen = strip(140, 45, layout=layout)
        assert move_hint_line(side), f"{layout}: Controls missing:\n{screen}"
        for direction in ("North:", "East:", "South:", "West:"):
            assert direction in side, f"{layout}: full compass missing {direction}:\n" + screen


def test_controls_strip_with_spacers_and_panel_toggles(_g):
    names = ("Health", "Compass", "Log", "Controls", "Body", "Vehicle", "Location",
             "Mana", "Weather", "Lighting", "Weapon", "Weapon_alt", "Wgt/Vol", "Time",
             "Wind", "Armor", "comp.Armor", "Comp.Compass", "Sim.Compass", "AI Needs")
    enabled = {"Health", "Compass", "Log", "Controls"}
    panels = [{"name": name, "toggle": name in enabled} for name in names]
    side, screen = strip(100, 25, layout="classic", spacers=True, panels=panels)
    assert move_hint_line(side), "spacers must not push Controls off screen:\n" + screen

    for panel in panels:
        if panel["name"] == "Log":
            panel["toggle"] = False
    side, screen = strip(100, 25, layout="classic", spacers=True, panels=panels)
    assert move_hint_line(side), "a hidden Log must not reserve its rows:\n" + screen

    for panel in panels:
        if panel["name"] == "Controls":
            panel["toggle"] = False
    side, screen = strip(100, 25, layout="classic", spacers=True, panels=panels)
    assert not move_hint_line(side), "Controls must still honor its toggle:\n" + screen
    assert "South:" in side, "hiding Controls must leave room for the compass:\n" + screen


TESTS = [test_controls_strip_shows_on_80x25,
         test_controls_strip_shows_on_100x30,
         test_controls_strip_survives_tall_layouts,
         test_controls_strip_with_spacers_and_panel_toggles]
