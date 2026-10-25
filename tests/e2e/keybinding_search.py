"""Typing searches keybindings; navigation stays on dedicated keys and the wheel."""
import shutil
import subprocess
import tempfile

from fixtures import shared_game
from helpers import HELPERS, arena, empty_inventory, spawn, wait_until
from menu_scrollbars import find_scrollbar, open_main_menu
from tmux_game import Game, start_new_game


def test_letters_search_keybindings_after_scrolling(_g):
    with shared_game("bn-e2e-keybinding-search", options={
            "CONTROL_SCHEME": "modern"}, define=HELPERS) as game:
        open_main_menu(game)
        game.keys("4", delay=0.4)
        game.wait_for("Unbound keys")
        bar = find_scrollbar(game.screen())
        assert bar, "the full keybinding list must be scrollable\n" + game.screen()
        top, _, x = bar
        first_row = game.screen().splitlines()[top][x + 4:]
        game.keys("Down", delay=0.2)
        assert wait_until(lambda: game.screen().splitlines()[top][x + 4:] != first_row, 10), (
            "the arrow key must still scroll\n" + game.screen())

        def filter_text():
            return game.screen().splitlines()[top - 2][x + 4:]

        try:
            game.type("smash", delay=0.2)
            assert wait_until(lambda: filter_text().startswith("smash"), 10), (
                "S must be typed into search, not scroll\n" + game.screen())
            assert wait_until(lambda: "Smash Nearby Terrain:" in game.screen(), 10), (
                "a changed search must show its matching action even after scrolling\n" + game.screen())
            game.type("w", delay=0.2)
            assert wait_until(lambda: filter_text().startswith("smashw"), 10), (
                "W must also be typed into search, not scroll\n" + game.screen())
            assert "Smash Nearby Terrain:" not in game.screen(), (
                "an action that no longer matches must disappear\n" + game.screen())
        finally:
            game.keys("Escape", delay=0.3)
            game.wait_gone("Unbound keys")


def _hotkey_for_action(screen, label):
    marker = f"{label}:"
    rows = [line for line in screen.splitlines() if marker in line]
    assert len(rows) == 1, f"expected one row for {label!r}\n{screen}"
    hotkey = rows[0].split(marker, 1)[0].rstrip()[-1]
    assert hotkey.isalnum(), f"expected a displayed row hotkey for {label!r}\n{screen}"
    return hotkey


def _selected_pickup_item(screen):
    marker = "╭─< "
    row = next((line for line in screen.splitlines() if marker in line), None)
    assert row, f"no selected pickup item\n{screen}"
    return row.split(marker, 1)[1].split(" >", 1)[0]


def test_local_unbind_can_be_readded_globally(_g):
    options = {
        "CONTROL_SCHEME": "classic",
        "QUERY_KEYBIND_REMOVAL": "true",
    }
    userdir = tempfile.mkdtemp(prefix="bn-e2e-keybinding-readd-")
    game = None
    reloaded = None
    try:
        game = Game(name="bn-e2e-keybinding-readd", options=options, userdir=userdir)
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        empty_inventory(game)
        arena(game)
        spawn(game, 0, 0, "rock")
        spawn(game, 0, 0, "stick")
        game.keys(",", delay=0.8)
        game.wait_for("Pick up")
        game.keys("?", delay=0.5)
        game.wait_for("Keybindings")
        game.type("next item", delay=0.2)
        game.wait_for("Next item:")

        game.keys("-", delay=0.3)
        hotkey = _hotkey_for_action(game.screen(), "Next item")
        game.keys(hotkey, delay=0.4)
        game.wait_for("Clear keys for Next item")
        game.keys("Y", delay=0.5)
        game.wait_gone("Clear keys for Next item")

        game.keys("=", delay=0.3)
        game.keys(hotkey, delay=0.4)
        game.wait_for("New key for Next item")
        game.keys("z", delay=0.5)
        game.keys("Escape", delay=0.4)
        game.wait_for("Save changes?")
        game.keys("Y", delay=0.8)
        game.wait_gone("Save changes?", timeout=10)
        game.wait_for("Pick up")
        previous = _selected_pickup_item(game.screen())
        game.keys("z", delay=0.5)
        current = _selected_pickup_item(game.screen())
        assert current != previous, (
            f"the new global key must move to the next item: {previous!r} -> {current!r}\n"
            + game.screen())

        subprocess.run(["tmux", "kill-session", "-t", game.name], check=True)
        reloaded = Game(name="bn-e2e-keybinding-reloaded", options=options, userdir=userdir)
        game = None
        start_new_game(reloaded)
        reloaded.define_lua(HELPERS)
        arena(reloaded)
        empty_inventory(reloaded)
        arena(reloaded)
        spawn(reloaded, 0, 0, "rock")
        spawn(reloaded, 0, 0, "stick")
        reloaded.keys(",", delay=0.8)
        reloaded.wait_for("Pick up")
        previous = _selected_pickup_item(reloaded.screen())
        reloaded.keys("z", delay=0.5)
        current = _selected_pickup_item(reloaded.screen())
        assert current != previous, (
            f"the saved global key must remain active after restart: "
            f"{previous!r} -> {current!r}\n" + reloaded.screen())
    finally:
        if reloaded is not None:
            reloaded.close()
        elif game is not None:
            game.close()
        shutil.rmtree(userdir, ignore_errors=True)


TESTS = [
    test_letters_search_keybindings_after_scrolling,
    test_local_unbind_can_be_readded_globally,
]

