"""Unbound mouse input is idle input, not an unknown keyboard command."""
from aim_reticle import action_clock
from fixtures import shared_game
from helpers import HELPERS, arena, bub_pos, settle


def recent_messages(game):
    return game.lua("for _,message in ipairs(gapi.get_messages(30)) do out(message.text) end")


def test_unbound_mouse_wheel_is_silent():
    with shared_game("bn-e2e-unbound-wheel", options={
        "CONTROL_SCHEME": "modern", "NO_UNKNOWN_COMMAND_MSG": "false",
        "SAFEMODE": "false", "CURSOR_PANNING": "false",
    }, define=HELPERS, setup=arena) as game:
        settle(game)
        before = action_clock(game)
        position = bub_pos(game)
        x, y = game.find("@")
        for button in (64, 65, 64, 65):
            game.click(x, y, button=button)
        messages = recent_messages(game)
        assert not any("SCROLL_UP" in message or "SCROLL_DOWN" in message
                       for message in messages), messages
        assert action_clock(game) == before, "unbound wheel input must not spend time"
        assert bub_pos(game) == position, "unbound wheel input must not move the player"

        game.keys("F8")
        messages = recent_messages(game)
        assert any('Unknown command: "F8"' in message for message in messages), messages
        assert action_clock(game) == before, "an unknown keyboard command must not spend time"


TESTS = [test_unbound_mouse_wheel_is_silent]
