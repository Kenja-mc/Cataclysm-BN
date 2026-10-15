"""Fire feedback when there is no ranged weapon wielded."""
import os

from helpers import HELPERS, arena, settle
from tmux_game import Game, start_new_game


def _turn_counter(game):
    result = game.lua("out(gapi.current_turn():to_turn())")
    return int(result[0])


def _recent_messages(game):
    result = game.lua("local t=gapi.get_messages(20); local s='' "
                      "for i,v in ipairs(t) do s=s..v.text..' ' end out(s)")
    return result[0] if result else ""


def test_fire_feedback_no_ranged_weapon(_g):
    game = Game(name=f"bn-e2e-fire-feedback-{os.getpid()}", cols=140, rows=45)
    try:
        start_new_game(game)
        settle(game)
        game.define_lua(HELPERS)
        assert game.lua("local a=gapi.get_avatar() "
                        "a:clear_bionics() a:clear_mutations() a:clear_morale() a:drop_all_items() "
                        "out('ok')") == ["ok"]
        arena(game)
        before_turn = _turn_counter(game)
        game.keys("f", delay=1.0)
        screen = game.screen()
        joined = " ".join(screen.splitlines())
        assert ("You have no ranged weapon wielded." in _recent_messages(game)
                or "You have no ranged weapon wielded." in joined), screen
        after_turn = _turn_counter(game)
        assert before_turn == after_turn, (
            f"turn advanced: {before_turn} -> {after_turn}\n{screen}"
        )
    finally:
        game.close()


TESTS = [test_fire_feedback_no_ranged_weapon]
