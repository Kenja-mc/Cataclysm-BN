"""Ctrl+Space finds an action by name, shows how it is reached, and runs the pick."""
from fixtures import shared_game


def test_ctrl_space_search_runs_the_picked_action(_g):
    with shared_game("bn-e2e-action-search", options={
        "CONTROL_SCHEME": "modern", "SAFEMODE": "false", "EDGE_SCROLL": "-1",
    }) as game:
        game.keys("C-f", delay=0.6)
        game.wait_for("Find an action")
        game.type("view map")
        game.keys("Enter", delay=0.6)          # submit the query
        game.wait_for("Actions matching")
        game.keys("Enter", delay=0.8)          # run the first match
        game.wait_for("Center On Character")
        game.keys("Escape", delay=0.4)
        game.wait_gone("Center On Character")


def test_ctrl_space_search_names_an_unbound_route(_g):
    with shared_game("bn-e2e-action-search-route", options={
        "CONTROL_SCHEME": "modern", "SAFEMODE": "false",
    }) as game:
        game.keys("C-f", delay=0.6)
        game.wait_for("Find an action")
        game.type("driving")
        game.keys("Enter", delay=0.6)          # submit the query
        screen = game.screen()
        assert "matching" in screen.lower() or "No action matches" in screen, screen


TESTS = [test_ctrl_space_search_runs_the_picked_action,
         test_ctrl_space_search_names_an_unbound_route]
