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
        screen = game.screen()
        assert "Cancel popup" in screen, "the first notice teaches the player:\n" + screen
        game.keys("Escape", delay=0.6)
        game.wait_for("X,Y,Z", timeout=15)
        # The second visit must not block the game.
        game.keys("Enter", delay=0.8)
        choose_menu_entry(game, "Misc…")
        game.wait_for("Sound & volume")
        choose_menu_entry(game, "Sound & volume")
        game.wait_for(UNAVAILABLE)
        screen = game.screen()
        assert "Cancel popup" not in screen, "the notice must not block twice:\n" + screen
        assert in_game(screen), "the notice must leave play usable:\n" + screen


TESTS = [test_sound_menu_curses_unavailable]
