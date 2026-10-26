"""The World hub gathers the run's info screens behind one key."""
from fixtures import shared_game
from helpers import HELPERS, arena, choose_menu_entry, settle


def test_world_hub_reaches_its_screens(_g):
    with shared_game("bn-e2e-world-hub", define=HELPERS, setup=arena,
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"}) as game:
        settle(game)
        game.keys("M", delay=0.8)
        game.wait_for("< World >")
        screen = game.screen()
        for label in ("Missions", "Factions", "Zones", "Scores"):
            assert label in screen, "the hub must list every screen:\n" + screen
        choose_menu_entry(game, "Zones")
        game.wait_for("Zones manager")
        game.keys("Escape", delay=0.6)
        game.keys("M", delay=0.8)
        choose_menu_entry(game, "Missions")
        game.wait_for("ACTIVE MISSIONS")
        game.keys("Escape", delay=0.6)
        game.keys("M", delay=0.8)
        choose_menu_entry(game, "Scores")
        game.wait_for("ACHIEVEMENTS")
        game.keys("Escape", delay=0.6)
        assert "X,Y,Z" in game.screen(), "leaving the hub must return to play"


TESTS = [test_world_hub_reaches_its_screens]
