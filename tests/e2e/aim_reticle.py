"""Sword of the Stars: The Pit style aim reticle: arrow keys aim, F fires."""
from helpers import HELPERS, arena, bub_pos, empty_inventory, settle, start_new_game
from tmux_game import Game


def action_clock(g):
    return tuple(int(value) for value in g.lua(
        "out(gapi.current_turn():to_turn(), -gapi.get_avatar():get_moves())")[0].split(","))


def test_arrow_keys_aim_and_attack(game):
    empty_inventory(game)
    arena(game)
    settle(game)
    try:
        # Adjacent, so F can swing at what the reticle covers without a ranged weapon.
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) "
                        "out(m ~= nil)") == ["true"]

        turn = action_clock(game)
        pos = bub_pos(game)
        # The first arrow key puts the reticle on the nearest visible hostile, for free.
        game.keys("Left", delay=1)
        # Read the screen first: the Lua console key used below hides the Mouse View box.
        assert "Mouse View" in game.screen(), game.screen()
        assert bub_pos(game) == pos, "an arrow key aims instead of walking"
        assert action_clock(game) == turn, "aiming spends no time"

        # Moving the reticle over the map costs nothing either.
        for key in ("Right", "Left", "Left", "Right"):
            game.keys(key, delay=0.8)
            assert bub_pos(game) == pos, "the reticle moves, the player stays"
        assert action_clock(game) == turn, "moving the reticle spends no time"

        # A swing spends moves even when it misses or finishes within the current turn.
        game.keys("F", delay=1.2)
        assert action_clock(game) > turn, "F must spend moves attacking"

        # With the reticle on bare floor, F says so instead of taking a turn.
        still = action_clock(game)
        for _ in range(3):
            game.keys("Right", delay=0.7)
        assert action_clock(game) == still, "the reticle keeps moving for free after the attack"
        game.keys("F", delay=1)
        assert "There's nothing there to attack." in game.screen(), game.screen()
        assert action_clock(game) == still, "attacking empty ground must not spend time"
    finally:
        game.keys("Escape", delay=0.6)
        arena(game)


def test_arrow_keys_walk_when_aim_disabled(_game):
    for scheme in ("modern", "classic"):
        game = Game(name=f"bn-e2e-arrow-walk-{scheme}",
                    options={"CONTROL_SCHEME": scheme, "ARROW_KEY_AIM": "false", "SAFEMODE": "false"})
        try:
            start_new_game(game)
            game.define_lua(HELPERS)
            arena(game)
            settle(game)
            before = bub_pos(game)
            game.keys("Right", delay=1)
            assert bub_pos(game) == (before[0] + 1, before[1], before[2])
        finally:
            game.close()


TESTS = [test_arrow_keys_aim_and_attack, test_arrow_keys_walk_when_aim_disabled]
