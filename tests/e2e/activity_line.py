"""A running activity gets one line in the existing Log panel."""
import re

from helpers import HELPERS, Game, settle, start_new_game


def test_activity_line_names_progress_in_the_log_panel(_g):
    game = Game(name="bn-e2e-activity-line", layout="classic",
                options={"SAFEMODE": "false", "SHOW_TIPS": "false", "SHOW_WELCOME": "false",
                         "ANIMATIONS": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        settle(game)
        assert "Activity:" not in game.screen(), \
            "an idle player should not reserve a line:\n" + game.screen()

        # A Lua-backed activity survives the console long enough to redraw once; pressing a
        # turn key would let the wait action replace it.
        assert game.lua(
            "local a=gapi.get_avatar() "
            "a:assign_lua_activity({type=ActivityTypeId.new('ACT_HEATING'), "
            "duration=TimeDuration.from_minutes(5), name='activity line check'}) "
            "out(a:has_activity(ActivityTypeId.new('ACT_HEATING')))") == ["true"]
        game.wait_for("Activity: heating", timeout=5)
        screen = game.screen()
        assert screen.count("Activity: heating") == 1, \
            "the Log panel should show one line for the running activity:\n" + screen
        assert re.search(r"Activity: heating \d+%", screen), \
            "the activity line should include progress:\n" + screen
    finally:
        game.close()


TESTS = [test_activity_line_names_progress_in_the_log_panel]
