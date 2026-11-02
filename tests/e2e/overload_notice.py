from fixtures import shared_game
from helpers import HELPERS, arena

OPTIONS = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false", "SHOW_WELCOME": "false",
           "SHOW_TIPS": "false", "ANIMATIONS": "false"}


def bare_avatar(game):
    arena(game)
    assert game.lua("local a=gapi.get_avatar() a:clear_bionics() a:clear_mutations() "
                    "a:clear_morale() a:drop_all_items() out('ok')") == ["ok"]
    arena(game)


def test_pickup_states_the_weight_and_volume_consequence(_g):
    with shared_game("bn-e2e-overload-notice", options=OPTIONS, cols=160, rows=45,
                     define=HELPERS, setup=bare_avatar) as game:
        assert game.lua("M:create_item_at(here(0,0), ItypeId.new('rock'), 200) out('ok')") == ["ok"]
        game.keys("C-g", delay=0.4)
        game.wait_for("Pick up")
        assert "Over by" not in game.screen(), "nothing is marked yet:\n" + game.screen()

        game.keys(",", delay=0.6)
        game.wait_for("Over by", timeout=10)
        marked = game.screen()
        assert "stamina drains" in marked, "the weight line must name the stamina cost:\n" + marked
        assert "% faster while moving" in marked, marked
        assert "Over volume" in marked, "the volume line must say what happens:\n" + marked

        game.keys(",", delay=0.6)
        game.wait_gone("Over by", timeout=10)
        unmarked = game.screen()
        assert "stamina drains" not in unmarked, "unmarking clears the weight line:\n" + unmarked
        assert "Over volume" not in unmarked, "unmarking clears the volume line:\n" + unmarked

        game.keys("Escape", delay=0.5)
        game.wait_gone("Pick up", timeout=10)
        arena(game)


TESTS = [test_pickup_states_the_weight_and_volume_consequence]
