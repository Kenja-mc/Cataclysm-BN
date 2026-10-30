"""Modern NPC contact: Space talks to a neighbour instead of examining the floor, replies are
numbered, and W/S move the highlighted reply."""
from helpers import HELPERS, arena, settle
from tmux_game import Game, start_new_game

OPTIONS = {"SAFEMODE": "false", "CONTROL_SCHEME": "modern"}


def test_space_talks_to_a_neighbour_and_replies_are_numbered(_g):
    game = Game(name="bn-e2e-npc-talk", options=OPTIONS, cols=140, rows=45)
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        assert game.lua("N=M:place_npc(here(1,0),'farmer') N.name='Talky' "
                        "N:set_attitude(NpcAttitude.NPCATT_NULL) out('ok')") == ["ok"]
        settle(game)
        game.keys("space", delay=1.0)
        screen = game.screen()
        assert "Talk to Talky" in screen or "What to do with Talky" in screen, screen
        assert "examine the" not in screen, screen
        for _ in range(2):
            game.keys("t", delay=1.0)
            if "Dialogue: Talky" in game.screen():
                break
        game.wait_for("Dialogue: Talky", timeout=15)
        screen = game.screen()
        assert "1 " in screen and " a " not in screen.split("Your response:")[1][:200], screen
        game.keys("s", delay=0.4)
        assert "Dialogue: Talky" in game.screen(), "s moves the highlight, it must not answer"
        game.keys("4", delay=1.0)
        game.wait_gone("Dialogue: Talky", timeout=15)
    finally:
        game.close()


TESTS = [test_space_talks_to_a_neighbour_and_replies_are_numbered]
