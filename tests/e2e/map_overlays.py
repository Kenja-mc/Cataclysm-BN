"""The state file lists the map overlays both renderers draw, at their real ages."""
import tempfile
from pathlib import Path

from fixtures import shared_game
from helpers import HELPERS, settle, wait_until

# Markers last long enough to observe several turns without fading.
PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "10"}


def _state(game):
    try:
        return game.state()
    except (OSError, ValueError):
        return None


def _sound_markers(game):
    return [entry for entry in (_state(game) or {}).get("map_overlays", [])
            if entry.get("kind") == "sound_marker"]


def _build_sound_scene(game):
    """Seal the player in an underground arena with one NPC behind a wall."""
    assert game.lua(
        "local a=gapi.get_avatar() local p=a:get_pos_ms() "
        "a:clear_bionics() a:clear_mutations() a:clear_morale() a:drop_all_items() "
        "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) arena() "
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
                     userdir=userdir, state_path=userdir / "state.json") as game:
        _build_sound_scene(game)
        assert game.lua("SOUND_NPC:shout('map overlay check',false) out('ok')") == ["ok"]

        def listen():
            game.keys("x", delay=0.6)
            return _sound_markers(game)

        assert wait_until(lambda: bool(listen()), timeout=25), \
            "the state file never listed the heard sound marker\n" + game.screen()
        before = _sound_markers(game)[0]

        game.keys("x", delay=0.6)
        game.keys("x", delay=0.6)
        assert wait_until(
            lambda: any(marker["age"] > before["age"] for marker in _sound_markers(game)),
            timeout=20), \
            "the sound marker did not age across the two waits\n" + game.screen()


TESTS = [test_state_file_lists_aged_sound_markers]
