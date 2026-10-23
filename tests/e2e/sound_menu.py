"""Sound & volume: the curses build explains that audio is unavailable."""

from fixtures import shared_game
from helpers import choose_menu_entry
from tmux_game import in_game


UNAVAILABLE = "Sound is unavailable in this build."


def test_sound_menu_curses_unavailable(_game):
    with shared_game("bn-e2e-sound-menu", options={"CONTROL_SCHEME": "modern"}) as game:
        game.keys("Enter")
        game.wait_for("Misc…")
        choose_menu_entry(game, "Misc…")
        game.wait_for("Sound & volume")
        choose_menu_entry(game, "Sound & volume")
        game.wait_for(UNAVAILABLE)
        game.keys("Escape")
        game.wait_gone(UNAVAILABLE)
        assert in_game(game.screen()), "Escape should return to play\n" + game.screen()


TESTS = [test_sound_menu_curses_unavailable]
