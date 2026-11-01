"""Mouse back side button in the real controls UI: Modern binds it to Cancel, Classic does not.

The terminal cannot deliver X1 to the game unless ncurses was built with the extended mouse
protocol, so these checks read what the player sees in the in-game Controls screen: Modern's
Cancel offers the back button, while Classic keeps its Escape-only Cancel. Real X1 presses are
covered by the tiles harness, `tiles.py side_buttons`.
"""
from concurrent.futures import ThreadPoolExecutor

from fixtures import shared_game
from helpers import wait_until

CANCEL_ACTION = "Cancel menu"
MOUSE_BACK = "mouse back"


def open_controls(game):
    game.keys("?", delay=0.5)
    game.wait_for("Keybindings")


def close_controls(game):
    game.keys("Escape", delay=0.3)
    game.wait_gone("Keybindings")


def action_row(game, name):
    """The Controls row of `name`, matched on the action label rather than key spelling."""
    prefix = name + ":"
    line = next((line for line in game.screen().splitlines() if prefix in line), None)
    assert line, f"the controls screen must list {name!r}\n" + game.screen()
    return line.lower()


def search_row(game, phrase, name):
    game.type(phrase, delay=0.3)
    assert wait_until(lambda: name + ":" in game.screen(), 10), (
        f"searching {phrase!r} must show {name!r}\n" + game.screen())
    return action_row(game, name)


def in_list_menu(game, check):
    """Runs `check` while a real list menu is open, and always leaves that menu."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        query = executor.submit(
            game.lua,
            "local menu=UiList.new() menu:title('Side buttons') "
            "menu:add(1,'Row one') out(menu:query())")
        try:
            game.wait_for("< Side buttons >")
            check(game)
            game.keys("Escape", delay=0.4)
            game.wait_gone("< Side buttons >")
        finally:
            if not query.done():
                game.keys("Escape", delay=0.3)
                game.keys("Escape", delay=0.3)
                game.wait_gone("< Side buttons >", timeout=10)
        query.result(timeout=20)


def test_modern_cancel_offers_back_side_button(_g):
    with shared_game("bn-e2e-side-buttons-modern",
                     options={"CONTROL_SCHEME": "modern"}) as game:
        def cancel_row(game):
            open_controls(game)
            row = search_row(game, "cancel", CANCEL_ACTION)
            assert MOUSE_BACK in row, (
                "Cancel must offer the back side button\n" + game.screen())
            assert "unbound" not in row, (
                "Cancel must stay bound\n" + game.screen())
            close_controls(game)

        in_list_menu(game, cancel_row)


def test_classic_cancel_has_no_side_button(_g):
    with shared_game("bn-e2e-side-buttons-classic",
                     options={"CONTROL_SCHEME": "classic"}) as game:
        def cancel_row(game):
            open_controls(game)
            row = search_row(game, "cancel", CANCEL_ACTION)
            screen = game.screen()
            assert MOUSE_BACK not in row, (
                "Classic's Cancel must keep upstream's keys only\n" + screen)
            # Compare key names case-insensitively: the UI writes "ESC", not "Esc".
            assert "esc" in row, "Classic's Cancel still cancels with Escape\n" + screen
            assert "unbound" not in row, "Classic's Cancel must stay bound\n" + screen
            close_controls(game)

        in_list_menu(game, cancel_row)


TESTS = [
    test_modern_cancel_offers_back_side_button,
    test_classic_cancel_has_no_side_button,
]
