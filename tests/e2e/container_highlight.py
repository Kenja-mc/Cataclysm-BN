import tempfile
import time
from pathlib import Path

from fixtures import shared_game
from helpers import HELPERS, arena, save_and_quit, settle, spawn, wait_until
from tmux_game import in_game

PROFILE = {
    "CONTROL_SCHEME": "modern",
    "MOUSE_MOVE": "true",
    "MOUSE_TILE_SELECTION": "true",
    "SAFE_CLICK_WALK": "true",
    "SAFEMODE": "false",
    "HUD_WINDOWS": "false",
    "CONTAINER_HIGHLIGHT": "true",
}

OFF_PROFILE = {**PROFILE, "CONTAINER_HIGHLIGHT": "false"}


def _state(game):
    try:
        return game.state()
    except (OSError, ValueError):
        return None


def _containers(game):
    return [entry for entry in (_state(game) or {}).get("map_overlays", [])
            if entry.get("kind") == "container"]


def _hover(game, dx, dy):
    found = game.find("@")
    assert found is not None, "the avatar is not on screen\n" + game.screen()
    game.hover(found[0] + dx, found[1] + dy)


def test_selected_container_tints_visible_and_remembered_contents(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-highlight-"))
    with shared_game("bn-e2e-container-highlight", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        arena(game)
        spawn(game, 1, 0, "rock", 1, "f_locker")
        settle(game)
        _hover(game, 1, 0)
        assert wait_until(lambda: [e["severity"] for e in _containers(game)] == [1], timeout=20), \
            "a selected container with visible contents must tint as lootable\n" + game.screen()

        assert game.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() "
                        "a:set_pos_ms(TripointBubMs.new(p.x+3,p.y,p.z)) out('ok')") == ["ok"]
        settle(game)
        _hover(game, -2, 0)
        assert wait_until(lambda: [e["severity"] for e in _containers(game)] == [2], timeout=20), \
            "a container whose contents were seen before must tint as remembered\n" + game.screen()


def test_empty_container_gets_no_loot_tint(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-empty-"))
    with shared_game("bn-e2e-container-empty", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        arena(game)
        spawn(game, 1, 0, "rock", 0, "f_locker")
        settle(game)
        _hover(game, 1, 0)
        assert wait_until(lambda: [e["severity"] for e in _containers(game)] == [2], timeout=20), \
            "an empty container must be remembered, not tinted as lootable\n" + game.screen()


def test_unseen_container_stays_untinted(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-hidden-"))
    with shared_game("bn-e2e-container-hidden", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        arena(game)
        spawn(game, -3, 0, "rock", 1, "f_locker")
        settle(game)
        assert _containers(game) == []
        _hover(game, -3, 0)
        time.sleep(1.5)
        assert _containers(game) == [], \
            "a container the player has never looked inside stays untinted\n" + game.screen()


def test_option_off_hides_the_tint(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-off-"))
    with shared_game("bn-e2e-container-off", options=OFF_PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        arena(game)
        spawn(game, 1, 0, "rock", 1, "f_locker")
        settle(game)
        _hover(game, 1, 0)
        time.sleep(1.5)
        assert _containers(game) == [], \
            "the option must remove the container tint\n" + game.screen()


def test_container_memory_survives_save_and_reload(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-reload-"))
    with shared_game("bn-e2e-container-reload", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        arena(game)
        spawn(game, 1, 0, "rock", 1, "f_locker")
        settle(game)
        assert game.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() "
                        "a:set_pos_ms(TripointBubMs.new(p.x+3,p.y,p.z)) out('ok')") == ["ok"]
        settle(game)
        save_and_quit(game)
        assert wait_until(lambda: "load" in game.screen().lower(), timeout=60), game.screen()
        game.keys("Enter", delay=1)
        assert game.wait_for("Load character from", timeout=30), game.screen()
        game.keys("Enter", delay=1)
        assert wait_until(lambda: in_game(game.screen()), 60), "resume did not reach the game"
        game.define_lua(HELPERS)
        _hover(game, -2, 0)
        assert wait_until(lambda: [e["severity"] for e in _containers(game)] == [2], timeout=20), \
            "the container memory must survive save and reload\n" + game.screen()


TESTS = [
    test_selected_container_tints_visible_and_remembered_contents,
    test_container_memory_survives_save_and_reload,
    test_empty_container_gets_no_loot_tint,
    test_unseen_container_stays_untinted,
    test_option_off_hides_the_tint,
]
