import tempfile
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
    "INITIAL_TIME": "12",
    "CONTAINER_HIGHLIGHT": "true",
}

OFF_PROFILE = {**PROFILE, "CONTAINER_HIGHLIGHT": "false"}


def _state(game):
    try:
        return game.state()
    except (OSError, ValueError):
        return None


def _containers(state):
    return [entry for entry in (state or {}).get("map_overlays", [])
            if entry.get("kind") == "container"]


def _target(state, dx, dy):
    x, y, z = state["player"]["pos"]
    return (x + dx, y + dy, z)


def _at_target(state, dx, dy):
    target = _target(state, dx, dy)
    return [entry for entry in _containers(state) if tuple(entry["pos"]) == target]


def _mtime(path):
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def _hover(game, dx, dy):
    found = game.find("@")
    assert found is not None, "the avatar is not on screen\n" + game.screen()
    game.hover(found[0] + dx, found[1] + dy)


def _move(game, dx, dy):
    assert game.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() "
                    f"a:set_pos_ms(TripointBubMs.new(p.x{dx:+d},p.y{dy:+d},p.z)) "
                    "out('ok')") == ["ok"]


def _turn(game):
    before = (_state(game) or {}).get("turn")
    assert before is not None, "the state file must exist before a turn pass\n" + game.screen()
    settle(game)
    assert wait_until(lambda: ((_state(game) or {}).get("turn", -1)) > before, timeout=20), \
        "the game did not finish an observation turn\n" + game.screen()


def _pin_visibility(game):
    assert game.lua(
        "local a=gapi.get_avatar() "
        "a:set_mutation(MutationBranchId.new('DEBUG_NIGHTVISION')) "
        "a:add_effect(EffectTypeId.new('debug_clairvoyance'), TimeDuration.from_turns(100000)) "
        "gapi.set_omt_weather_override(coords.project_to_omt(a:abs_pos()),3,'clear',nil) "
        "for dx=-8,8 do for dy=-8,8 do local p=here(dx,dy) "
        "M:set_ter_at(TripointBubMs.new(p.x,p.y,p.z+1), TerId.new('t_open_air'):int_id()) "
        "M:set_furn_at(TripointBubMs.new(p.x,p.y,p.z+1), FurnId.new('f_null'):int_id()) end end "
        "out('ok')") == ["ok"], "could not pin visibility\n" + game.screen()


def _assert_visible(game, *offsets):
    code = "local a=gapi.get_avatar() " + " ".join(
        f"out(a:sees(here({dx},{dy})))" for dx, dy in offsets)
    assert game.lua(code) == ["true"] * len(offsets), \
        f"the avatar must see the checked cells {offsets} for the tint checks\n" + game.screen()


def _hover_state(game, dx, dy, after=None, timeout=20):
    path = game.state_path
    assert path is not None, "hover checks need a state path"
    before = _state(game)
    assert before is not None, "no state file before the hover\n" + game.screen()
    previous = _target(before, *after) if after is not None else None
    sentinel = previous is not None and previous in [tuple(e["pos"]) for e in _containers(before)]
    before_mtime = _mtime(path)

    _hover(game, dx, dy)

    def refreshed():
        state = _state(game)
        if state is None:
            return None
        if sentinel and previous not in [tuple(e["pos"]) for e in _containers(state)]:
            return state
        now = _mtime(path)
        if now is not None and before_mtime is not None and now > before_mtime:
            return state
        return None

    assert wait_until(lambda: refreshed() is not None, timeout=timeout), \
        "the game never refreshed the state for the hovered cell\n" + game.screen()
    return refreshed()


def _describe(entries):
    return ", ".join(f"severity {entry['severity']} at {tuple(entry['pos'])}"
                     for entry in entries) or "no container overlay"


def test_selected_container_tints_visible_and_remembered_contents(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-highlight-"))
    with shared_game("bn-e2e-container-highlight", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json",
                     owns_userdir=True) as game:
        arena(game)
        _pin_visibility(game)
        spawn(game, 1, 0, "rock", 1, "f_locker")
        _turn(game)
        _assert_visible(game, (1, 0))
        state = _hover_state(game, 1, 0)
        found = _at_target(state, 1, 0)
        assert [entry["severity"] for entry in found] == [1], \
            "a selected container with visible contents must tint as lootable; got " \
            f"{_describe(found)}\n" + game.screen()

        _move(game, 3, 0)
        _turn(game)
        _assert_visible(game, (-2, 0))
        state = _hover_state(game, -2, 0)
        found = _at_target(state, -2, 0)
        assert [entry["severity"] for entry in found] == [2], \
            "a container whose contents were seen before must tint as remembered; got " \
            f"{_describe(found)}\n" + game.screen()


def test_empty_container_gets_no_loot_tint(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-empty-"))
    with shared_game("bn-e2e-container-empty", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json",
                     owns_userdir=True) as game:
        arena(game)
        _pin_visibility(game)
        spawn(game, 1, 0, "rock", 0, "f_locker")
        spawn(game, 0, 1, "rock", 1, "f_locker")
        _turn(game)
        _assert_visible(game, (0, 1), (1, 0))

        sentinel = _at_target(_hover_state(game, 0, 1), 0, 1)
        assert [entry["severity"] for entry in sentinel] == [1], \
            "the adjacent full container must tint as lootable before the empty check; got " \
            f"{_describe(sentinel)}\n" + game.screen()

        state = _hover_state(game, 1, 0, after=(0, 1))
        found = _containers(state)
        assert found == [], \
            "an empty container must not tint while its contents are observable; the state " \
            f"reported {_describe(found)}\n" + game.screen()


def test_observed_container_tint_tracks_current_and_remembered_contents(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-observed-"))
    with shared_game("bn-e2e-container-observed", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json",
                     owns_userdir=True) as game:
        arena(game)
        _pin_visibility(game)
        spawn(game, 1, 0, "rock", 0, "f_locker")
        spawn(game, 0, 1, "rock", 1, "f_locker")
        spawn(game, -1, 0, "rock", 1, "f_locker")
        _turn(game)
        _assert_visible(game, (0, 1), (1, 0), (-1, 0))

        sentinel = _at_target(_hover_state(game, 0, 1), 0, 1)
        assert [entry["severity"] for entry in sentinel] == [1], \
            "the adjacent full container must tint as lootable before the empty check; got " \
            f"{_describe(sentinel)}\n" + game.screen()

        state = _hover_state(game, 1, 0, after=(0, 1))
        found = _containers(state)
        assert found == [], \
            "an empty container must not tint while its contents are observable; the state " \
            f"reported {_describe(found)}\n" + game.screen()

        state = _hover_state(game, 0, 1, after=(1, 0))
        found = _at_target(state, 0, 1)
        assert [entry["severity"] for entry in found] == [1], \
            "currently visible loot must tint as lootable; got " \
            f"{_describe(found)}\n" + game.screen()

        _move(game, 3, 0)
        _turn(game)
        _assert_visible(game, (-4, 0), (-2, 0))

        state = _hover_state(game, -4, 0)
        found = _at_target(state, -4, 0)
        assert [entry["severity"] for entry in found] == [2], \
            "loot seen before must stay remembered after moving away; got " \
            f"{_describe(found)}\n" + game.screen()

        state = _hover_state(game, -2, 0, after=(-4, 0))
        found = _containers(state)
        assert found == [], \
            "a container observed empty must not tint as remembered after moving away; the " \
            f"state reported {_describe(found)}\n" + game.screen()


def test_remembered_loot_is_forgotten_when_observed_empty(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-forget-"))
    with shared_game("bn-e2e-container-forget", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json",
                     owns_userdir=True) as game:
        arena(game)
        _pin_visibility(game)
        spawn(game, 2, 0, "rock", 1, "f_locker")
        spawn(game, 0, -1, "rock", 1, "f_locker")
        _turn(game)
        _assert_visible(game, (2, 0), (0, -1))

        _move(game, 1, 0)
        _turn(game)
        _move(game, -1, 0)
        _turn(game)
        found = _at_target(_hover_state(game, 2, 0), 2, 0)
        assert [entry["severity"] for entry in found] == [2], \
            "loot observed next to a container must be remembered once it is out of reach; " \
            f"got {_describe(found)}\n" + game.screen()

        _move(game, 1, 0)
        _turn(game)
        assert game.lua("M:clear_items_at(here(1,0)) out('ok')") == ["ok"]
        _turn(game)

        _move(game, -1, 0)
        _turn(game)
        _assert_visible(game, (2, 0), (0, -1))
        sentinel = _at_target(_hover_state(game, 0, -1), 0, -1)
        assert [entry["severity"] for entry in sentinel] == [1], \
            "the adjacent full container must tint as lootable before the forget check; got " \
            f"{_describe(sentinel)}\n" + game.screen()

        state = _hover_state(game, 2, 0, after=(0, -1))
        found = _containers(state)
        assert found == [], \
            "loot observed as empty must be forgotten, not tinted as remembered; the state " \
            f"reported {_describe(found)}\n" + game.screen()


def test_unseen_container_stays_untinted(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-hidden-"))
    with shared_game("bn-e2e-container-hidden", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json",
                     owns_userdir=True) as game:
        arena(game)
        _pin_visibility(game)
        spawn(game, 3, 0, "rock", 1, "f_locker")
        spawn(game, 0, -1, "rock", 1, "f_locker")
        _turn(game)
        _assert_visible(game, (0, -1), (3, 0))

        sentinel = _at_target(_hover_state(game, 0, -1), 0, -1)
        assert [entry["severity"] for entry in sentinel] == [1], \
            "the adjacent full container must tint as lootable before the unseen check; got " \
            f"{_describe(sentinel)}\n" + game.screen()

        state = _hover_state(game, 3, 0, after=(0, -1))
        found = _containers(state)
        assert found == [], \
            "a container the player has never looked inside stays untinted; the state " \
            f"reported {_describe(found)}\n" + game.screen()


def test_option_off_hides_the_tint(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-off-"))
    with shared_game("bn-e2e-container-off", options=OFF_PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json",
                     owns_userdir=True) as game:
        arena(game)
        _pin_visibility(game)
        spawn(game, 1, 0, "rock", 1, "f_locker")
        _turn(game)
        _assert_visible(game, (1, 0))
        state = _hover_state(game, 1, 0)
        found = _containers(state)
        assert found == [], \
            "the option must remove the container tint; the state reported " \
            f"{_describe(found)}\n" + game.screen()


def test_container_memory_survives_save_and_reload(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-container-reload-"))
    with shared_game("bn-e2e-container-reload", options=PROFILE, define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json",
                     owns_userdir=True) as game:
        arena(game)
        _pin_visibility(game)
        spawn(game, 1, 0, "rock", 1, "f_locker")
        _turn(game)
        _move(game, 3, 0)
        _turn(game)
        save_and_quit(game)
        assert wait_until(lambda: "load" in game.screen().lower(), timeout=60), game.screen()
        game.keys("Enter", delay=1)
        assert game.wait_for("Load character from", timeout=30), game.screen()
        game.keys("Enter", delay=1)
        assert wait_until(lambda: in_game(game.screen()), 60), "resume did not reach the game"
        game.define_lua(HELPERS)
        _pin_visibility(game)
        _turn(game)
        _assert_visible(game, (-2, 0))
        state = _hover_state(game, -2, 0)
        found = _at_target(state, -2, 0)
        assert [entry["severity"] for entry in found] == [2], \
            "the container memory must survive save and reload; got " \
            f"{_describe(found)}\n" + game.screen()


TESTS = [
    test_selected_container_tints_visible_and_remembered_contents,
    test_container_memory_survives_save_and_reload,
    test_empty_container_gets_no_loot_tint,
    test_observed_container_tint_tracks_current_and_remembered_contents,
    test_remembered_loot_is_forgotten_when_observed_empty,
    test_unseen_container_stays_untinted,
    test_option_off_hides_the_tint,
]
