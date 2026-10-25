"""Typing searches keybindings; navigation stays on dedicated keys and the wheel."""
from fixtures import shared_game
from helpers import HELPERS, wait_until
from menu_scrollbars import find_scrollbar, open_main_menu


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


TESTS = [test_letters_search_keybindings_after_scrolling]
