import shutil
import tempfile
from pathlib import Path

from fixtures import shared_game
from helpers import HELPERS, Game, settle, start_new_game, wait_until

PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "10", "HUD_WINDOWS": "false"}
ACTIVITY_PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "4", "HUD_WINDOWS": "false"}
LAYOUT = "labels"
MARKER_REACH = 6
ACTIVITY = (
    "local a=gapi.get_avatar() "
    "a:assign_lua_activity({type=ActivityTypeId.new('ACT_HEATING'), "
    "duration=TimeDuration.from_hours(24), name='state marker activity'}) "
    "out(a:has_activity(ActivityTypeId.new('ACT_HEATING')))"
)


def _state(game):
    try:
        return game.state()
    except (OSError, ValueError):
        return None


def _markers(state):
    return [entry for entry in (state or {}).get("map_overlays", [])
            if entry.get("kind") == "sound_marker"]


def _near_shout_markers(game):
    state = _state(game)
    player = (state or {}).get("player", {}).get("pos")
    if not player:
        return []
    px, py, pz = player
    return [marker for marker in _markers(state)
            if marker["pos"][2] == pz
            and max(abs(marker["pos"][0] - px), abs(marker["pos"][1] - py)) <= MARKER_REACH]


def _build_sound_scene(game):
    assert game.lua(
        "local a=gapi.get_avatar() local p=a:get_pos_ms() "
        "a:clear_bionics() a:clear_mutations() a:clear_morale() a:drop_all_items() "
        "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) arena() "
        "for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end "
        "for dy=-9,9 do M:set_ter_at(here(1,dy), TerId.new('t_wall'):int_id()) "
        "for dx=2,3 do M:set_ter_at(here(dx,dy), TerId.new('t_floor'):int_id()) "
        "M:set_furn_at(here(dx,dy), FurnId.new('f_null'):int_id()) end end "
        "SOUND_NPC=M:place_npc(here(2,0),'farmer') "
        "SOUND_NPC:clear_bionics() SOUND_NPC:clear_mutations() "
        "SOUND_NPC:clear_morale() SOUND_NPC:drop_all_items() "
        "SOUND_NPC:set_attitude(NpcAttitude.NPCATT_WAIT) out('ok')") == ["ok", "ok"]
    settle(game)


def test_state_file_lists_aged_sound_markers(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-map-overlays-"))
    with shared_game("bn-e2e-map-overlays", options=PROFILE, define=HELPERS,
                     userdir=userdir, layout=LAYOUT, state_path=userdir / "state.json",
                     owns_userdir=True) as game:
        _build_sound_scene(game)
        assert game.lua("SOUND_NPC:shout('map overlay check',false) out('ok')") == ["ok"]

        def listen():
            game.keys("x", delay=0.6)
            return _near_shout_markers(game)

        assert wait_until(lambda: bool(listen()), timeout=25), \
            "the state file never listed the heard sound marker\n" + game.screen()
        heard = _near_shout_markers(game)
        assert heard, "the state file stopped listing the shout marker before it could age"
        marker_pos = min(tuple(marker["pos"]) for marker in heard)
        before_age = next(marker["age"] for marker in heard
                          if tuple(marker["pos"]) == marker_pos)

        game.keys("x", delay=0.6)
        game.keys("x", delay=0.6)
        assert wait_until(
            lambda: any(tuple(marker["pos"]) == marker_pos and marker["age"] > before_age
                        for marker in _near_shout_markers(game)),
            timeout=20), \
            "the sound marker did not age across the two waits\n" + game.screen()


def test_state_file_clears_markers_during_activity(_g):
    state_dir = Path(tempfile.mkdtemp(prefix="bn-e2e-map-overlays-activity-"))
    game = Game(name="bn-e2e-map-overlays-activity", options=ACTIVITY_PROFILE,
                layout=LAYOUT, state_path=state_dir / "state.json")
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        _build_sound_scene(game)
        assert game.lua("SOUND_NPC:shout('activity overlay check',false) out('ok')") == ["ok"]

        def listen():
            game.keys("x", delay=0.6)
            return _near_shout_markers(game)

        assert wait_until(lambda: bool(listen()), timeout=25), \
            "the state file never listed the heard sound marker\n" + game.screen()
        heard_positions = {tuple(marker["pos"]) for marker in _near_shout_markers(game)}
        assert heard_positions, "the fixture needs the shout marker before starting the activity"
        start_turn = (_state(game) or {}).get("turn")
        assert start_turn is not None, "the state file needs a turn stamp"
        assert game.lua("park(SOUND_NPC) out('ok')") == ["ok"]
        assert game.lua(ACTIVITY) == ["true"]
        marker_turns = int(ACTIVITY_PROFILE["SOUND_MARKER_TURNS"])

        def cleared():
            state = _state(game)
            return (state is not None and state.get("turn", 0) >= start_turn + marker_turns
                    and not heard_positions.intersection(
                        tuple(marker["pos"]) for marker in _markers(state)))

        assert wait_until(cleared, timeout=20), \
            "the activity should age the marker out of the state file\n" + game.screen()
        assert "Activity: heating" in game.screen(), \
            "the marker must clear while the activity is still running\n" + game.screen()
    finally:
        game.close()
        shutil.rmtree(state_dir, ignore_errors=True)


def test_state_file_lists_a_marker_from_the_level_above(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-map-overlays-z-"))
    with shared_game("bn-e2e-map-overlays-z", options=PROFILE, define=HELPERS,
                     userdir=userdir, layout=LAYOUT, state_path=userdir / "state.json",
                     owns_userdir=True) as game:
        _build_sound_scene(game)
        assert game.lua("SOUND_NPC:shout('cross level overlay check',false) out('ok')") == ["ok"]

        def listen():
            game.keys("x", delay=0.6)
            return _near_shout_markers(game)

        assert wait_until(lambda: bool(listen()), timeout=25), \
            "the state file never listed the heard sound marker\n" + game.screen()
        heard_positions = {tuple(marker["pos"]) for marker in _near_shout_markers(game)}
        assert heard_positions, "the fixture needs the shout marker before changing level"
        start_state = _state(game)
        assert start_state is not None, "the state file did not stay readable"
        start_z = start_state["player"]["pos"][2]

        assert game.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() "
                        "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) arena() out('ok')") == ["ok", "ok"]
        settle(game)

        def marker_above():
            state = _state(game)
            if state is None:
                return False
            player_z = state["player"]["pos"][2]
            return player_z == start_z - 1 and any(
                tuple(marker["pos"]) in heard_positions and marker["pos"][2] == player_z + 1
                for marker in _markers(state))

        assert wait_until(marker_above, timeout=15), \
            "a marker from the level above should stay in the state file; " \
            f"heard {sorted(heard_positions)}, state {_state(game)}\n" + game.screen()


TESTS = [
    test_state_file_lists_aged_sound_markers,
    test_state_file_clears_markers_during_activity,
    test_state_file_lists_a_marker_from_the_level_above,
]
