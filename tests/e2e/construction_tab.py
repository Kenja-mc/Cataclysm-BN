"""The construction menu opens on a tab with content, not the empty Favorite tab."""
import json
import os
import re

from helpers import HELPERS, action_menu, arena, settle
from tmux_game import ROOT, Game, start_new_game


def construction_names():
    """Every construction group name the game data defines."""
    groups = json.loads((ROOT / "data/json/construction_group.json").read_text())
    return [g["name"] for g in groups if g.get("name")]


def list_pane(screen):
    """The text drawn inside the menu's construction list pane."""
    lines = screen.splitlines()
    top = next((l for l in lines if "┴" in l), None)
    if top is None:
        return ""
    left = top.index("╭")
    rows = []
    for line in lines:
        if len(line) > left + 1 and line[left] == "│":
            end = line.find("│", left + 1)
            if end > left:
                rows.append(line[left + 1:end])
    return "\n".join(rows)


def listed_names(screen):
    pane = list_pane(screen)
    return [name for name in construction_names() if name in pane]


def favorite_key(screen):
    """The favorite hotkey the menu footer advertises."""
    found = re.search(r"Press \[([^\]]+)\] to add", screen)
    assert found, "the footer must name the favorite key:\n" + screen
    return found[1]


def open_menu(game):
    action_menu(game, "Craft", "Construct Terrain")
    game.wait_for("Construction speed")
    return game.screen()


def test_construction_opens_on_content(_g):
    game = Game(name=f"bn-e2e-construction-tab-{os.getpid()}", cols=140, rows=45,
                options={"SAFEMODE": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        settle(game)

        screen = open_menu(game)
        assert "<│Favorite│>" not in screen, (
            "the construction menu must not open on the empty Favorite tab:\n" + screen)
        assert "<│All│>" in screen, "the next non-empty tab (All) should be active:\n" + screen
        shown = listed_names(screen)
        assert shown, "the construction list must show at least one construction:\n" + screen

        # Favorite the selected construction, then close and reopen.
        game.keys(favorite_key(screen), delay=0.8)
        game.keys("Escape", delay=0.8)
        screen = open_menu(game)
        assert "<│Favorite│>" in screen, (
            "with a favorite, the menu must open on Favorite:\n" + screen)
        assert "* No hidden recipe - 1 in category *" in screen, (
            "the Favorite tab must hold the one favorited construction:\n" + screen)
        assert listed_names(screen), (
            "the Favorite tab must list the favorited construction:\n" + screen)
        game.keys("Escape", delay=0.8)
    finally:
        game.close()


TESTS = [test_construction_opens_on_content]
