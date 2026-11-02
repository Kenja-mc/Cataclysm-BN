"""The --state-out file reports the open inventory and advances its turn counter."""
import tempfile
from pathlib import Path

from fixtures import shared_game
from helpers import HELPERS, give, wait_until


def _state(game):
    try:
        return game.state()
    except (OSError, ValueError):
        return None


def _turn(game):
    return (_state(game) or {}).get("turn", -1)


def _inventory_top(game):
    top = (_state(game) or {}).get("ui", {}).get("top")
    if not top or "inventory" not in str(top.get("id", "")).lower():
        return None
    return top


def _inventory_with_rows(game):
    top = _inventory_top(game)
    return top if top and top.get("rows") else None


def test_state_file_reports_inventory_and_turn(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-state-"))
    with shared_game("bn-e2e-state-channel",
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"},
                     define=HELPERS, userdir=userdir,
                     state_path=userdir / "state.json") as game:
        give(game, "rock", 1)
        game.keys("i", delay=0.8)
        assert wait_until(lambda: _inventory_with_rows(game) is not None, timeout=20), \
            "the state file never reported an open inventory with rows\n" + game.screen()

        top = _inventory_with_rows(game)
        assert top["selected"] >= 0, "the open inventory must name a selected row"
        assert any(row.get("hotkey") for row in top["rows"]), \
            "inventory rows must carry their invlet hotkeys"

        game.keys("Escape", delay=0.8)
        assert wait_until(lambda: _inventory_top(game) is None, timeout=20), \
            "the inventory entry stayed in the state file after Escape\n" + game.screen()

        before = _turn(game)
        game.keys("x", delay=0.8)
        assert wait_until(lambda: _turn(game) > before, timeout=20), \
            "waiting one turn did not advance the state file's turn\n" + game.screen()


TESTS = [test_state_file_reports_inventory_and_turn]
