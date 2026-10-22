"""World presets: applying a difficulty preset to a world and to the current world."""
import json
import time
from pathlib import Path

from options_menu import close_options, open_options
from tmux_game import Game


def world_options_path(userdir, timeout=120):
    """The world is saved as soon as it is created, and worldoptions.json holds the values."""
    save_dir = Path(userdir) / "save"
    deadline = time.time() + timeout
    while time.time() < deadline:
        worlds = [p for p in save_dir.glob("*") if p.is_dir()] if save_dir.is_dir() else []
        for world in worlds:
            if (world / "worldoptions.json").is_file():
                return world / "worldoptions.json"
        time.sleep(0.5)
    raise AssertionError(f"no worldoptions.json under {save_dir}")


def read_options(path):
    try:
        return {entry["name"]: entry["value"] for entry in json.loads(path.read_text())}
    except (OSError, ValueError):
        # The world is being written; the caller polls until its value appears.
        return {}


def wait_for_option(path, name, expected, timeout=30):
    deadline = time.time() + timeout
    values = read_options(path)
    while time.time() < deadline:
        values = read_options(path)
        if values.get(name) == expected:
            return values
        time.sleep(0.5)
    raise AssertionError(f"{name} is {values.get(name)!r}, expected {expected!r}\n{values}")


def reach_world_options(g, timeout=240):
    """Language prompt -> New Game -> Custom Character -> world creation -> World Options tab.

    Play Now silently creates a world with defaults, so the interactive flow is Custom Character.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        screen = g.screen()
        if "World Mods" in screen:
            g.keys("Tab", delay=1)
            g.wait_for("World end handling", timeout=30)
            return
        if "Welcome to Bright Nights" in screen:
            g.keys("Escape", delay=1)
        elif "How should death work" in screen:
            g.keys("r", delay=1)
        elif "Select your language" in screen:
            g.keys("1")
        elif "Play Now!  (Default Scenario)" in screen:
            line = next((l for l in screen.splitlines() if "»" in l), "")
            if "Custom Character" in line:
                g.keys("Enter", delay=1)
            else:
                g.keys("Up")
        elif not screen.strip():
            g.keys("F5", delay=1)
        else:
            time.sleep(0.5)
    raise AssertionError("never reached world creation\n" + g.screen())


def ensure_in_game(g):
    """A failed earlier test may leave the main menu or the options open."""
    for _ in range(4):
        screen = g.screen()
        if "MAIN MENU" in screen or " OPTIONS " in screen:
            g.keys("Escape", delay=1)
        else:
            return
    raise AssertionError("could not return to the game\n" + g.screen())


def open_current_world_page(g):
    ensure_in_game(g)
    open_options(g)
    for _ in range(12):
        if "World end handling" in g.screen():
            return
        g.keys("Tab", delay=0.7)
    raise AssertionError("the Current world page is reachable by tabbing\n" + g.screen())


def test_world_preset_during_worldgen(_g):
    """p at world creation applies Scarce: its keys land in worldoptions.json, others keep their defaults."""
    g = Game(name="bn-e2e-world-preset", cols=100, rows=30)
    try:
        reach_world_options(g)
        assert "[p] preset" in g.screen(), "the world page advertises the preset key\n" + g.screen()
        g.keys("p", delay=1)
        g.wait_for("Apply world preset", timeout=15)
        g.wait_for("Scarce", timeout=15)
        g.keys("Down", "Down", "Enter", delay=0.6)
        g.wait_for("Apply the Scarce preset?", timeout=15)
        g.keys("Left", "Enter", delay=0.8)
        # Finish the world so it saves its options.
        g.keys("Tab", delay=1)
        g.wait_for("World Name", timeout=30)
        g.keys("Tab", delay=1)
        g.wait_for("Are you SURE", timeout=30)
        g.keys("Left", "Enter", delay=1)
        path = world_options_path(g.userdir)
        values = wait_for_option(path, "ITEM_SPAWNRATE", "0.80")
        assert values["SPAWN_RATE_guns"] == "0.65", values
        assert values["SPAWN_RATE_ammo"] == "0.65", values
        assert values["VEHICLE_SPAWNRATE"] == "0.50", values
        assert values["VEHICLE_DAMAGE"] == "2.00", values
        # A preset only changes the world page's defaults; the game rules keep their own values.
        assert values["CITY_SIZE"] == "8", values
        assert values["MONSTER_UPGRADE_FACTOR"] == "2.00", values
        assert values["NPC_DENSITY"] == "0.10", values
    finally:
        g.close()


def test_world_defaults_unchanged_without_preset(g):
    """A world made without a preset keeps every shipped default."""
    path = world_options_path(g.userdir, timeout=30)
    values = read_options(path)
    assert values["ITEM_SPAWNRATE"] == "1.00", values
    assert values["SPAWN_DENSITY"] == "1.00", values
    assert values["NPC_DENSITY"] == "0.10", values
    assert values["CITY_SIZE"] == "8", values


def test_world_preset_in_game(g):
    """p on the in-game Current world page applies Relaxed, saves it, and Default restores it."""
    path = world_options_path(g.userdir, timeout=30)
    open_current_world_page(g)
    try:
        g.keys("p", delay=1)
        g.wait_for("Relaxed", timeout=15)
        g.keys("Down", "Enter", delay=0.6)
        g.wait_for("Apply the Relaxed preset?", timeout=15)
        g.keys("Left", "Enter", delay=0.8)
        g.keys("Escape", delay=1)
        g.wait_for("Save changes?", timeout=15)
        g.keys("y", "Enter", delay=1)
        values = wait_for_option(path, "ITEM_SPAWNRATE", "1.25")
        assert values["SPAWN_DENSITY"] == "0.75", values
        assert values["MONSTER_RESILIENCE"] == "80%", values
        assert values["NPC_DENSITY"] == "0.05", values
    finally:
        close_options(g)
    open_current_world_page(g)
    try:
        g.keys("p", delay=1)
        g.wait_for("Default (reset page)", timeout=15)
        g.keys("Enter", delay=0.6)
        g.wait_for("Reset all options on this page", timeout=15)
        g.keys("Left", "Enter", delay=0.8)
        g.keys("Escape", delay=1)
        g.wait_for("Save changes?", timeout=15)
        g.keys("y", "Enter", delay=1)
        wait_for_option(path, "ITEM_SPAWNRATE", "1.00")
    finally:
        close_options(g)


TESTS = [test_world_preset_during_worldgen, test_world_defaults_unchanged_without_preset,
         test_world_preset_in_game]
