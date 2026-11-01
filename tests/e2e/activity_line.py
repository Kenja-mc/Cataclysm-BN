"""A running activity gets one line in the existing Log panel."""
import re

from fixtures import shared_game
from helpers import HELPERS, settle

MARK = "E2E activity row marker"

# A non-calendar activity settles while the game waits for input, unlike ACT_WAIT, which skips
# time and finishes before a redraw. The halved progress rate keeps the displayed estimate away
# from plain calendar time; the rate choice itself is locked by the Catch2 activity test.
BASE = {"SAFEMODE": "false", "SHOW_TIPS": "false", "SHOW_WELCOME": "false", "ANIMATIONS": "false",
        "ACTIVITY_PROGRESS_SCALE": "50", "LOG_FLOW": "new_top"}


def assign_activity(game, half=False):
    """Assign ACT_HEATING in the Lua console; the console must close before it can settle.

    `out` joins every argument into one comma-separated value, so return a parsed status pair.
    """
    script = ("local a=gapi.get_avatar() "
              "a:assign_lua_activity({type=ActivityTypeId.new('ACT_HEATING'), "
              "duration=TimeDuration.from_minutes(2), name='activity line check'}) "
              "local act=a:get_activity() ")
    if half:
        script += "act.moves_left = act.moves_total // 2 "
    script += "out(a:has_activity(ActivityTypeId.new('ACT_HEATING')), act.moves_left)"
    values = game.lua(script)
    assert len(values) == 1, values
    status, moves_left = values[0].split(",")
    assert status == "true", values
    return status, int(moves_left)


def log_row(screen, text):
    return next((row for row, line in enumerate(screen.splitlines()) if text in line), None)


def force_redraw(game):
    """Resizing redraws the panels without a turn or an activity-cancelling keypress."""
    game.resize(141, 45)
    game.settle_screen(minimum=0.2, timeout=2)
    game.resize(140, 45)
    game.settle_screen(minimum=0.2, timeout=2)


def test_activity_line_names_progress_and_time_left(_g):
    """The settled log shows one line whose percentage and time left follow the activity."""
    with shared_game("bn-e2e-activity-line", define=HELPERS, options=BASE,
                     layout="classic") as game:
        settle(game)
        assert "Activity:" not in game.screen(), \
            "an idle player should not reserve a line:\n" + game.screen()

        status, moves_left = assign_activity(game, half=True)
        assert status == "true" and moves_left == 6000, (status, moves_left)
        game.wait_for("Activity: heating 50%", timeout=5)
        screen = game.screen()
        assert screen.count("Activity: heating") == 1, \
            "the Log panel should show one line for the running activity:\n" + screen
        assert re.search(r"Activity: heating 50% \(\d+", screen), \
            "half the moves must read as fifty percent with a time left:\n" + screen


def test_activity_line_option_off_keeps_the_upstream_log(_g):
    """Turning the line off leaves the message rows exactly where upstream puts them."""
    with shared_game("bn-e2e-activity-line-off", define=HELPERS,
                     options={**BASE, "ACTIVITY_LINE": "false"}, layout="classic") as game:
        settle(game)
        assert game.lua(f"gapi.add_msg('{MARK}') out('ok')") == ["ok"]
        game.wait_for(MARK)
        before = log_row(game.screen(), MARK)
        assert before is not None, "the fixture needs a message in the log:\n" + game.screen()

        status, moves_left = assign_activity(game)
        assert status == "true" and moves_left > 0, "the fixture needs a running activity"
        force_redraw(game)
        screen = game.screen()
        assert "Activity:" not in screen, \
            "the activity line must stay off when the option is off:\n" + screen
        assert log_row(screen, MARK) == before, \
            "with the line off the log keeps row 0 for messages:\n" + screen


TESTS = [
    test_activity_line_names_progress_and_time_left,
    test_activity_line_option_off_keeps_the_upstream_log,
]
