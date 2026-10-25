"""A heard but unseen source fades after the configured turns in an isolated game."""
from helpers import HELPERS, Game, arena, settle, start_new_game, wait_until

PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "3"}


def test_sound_marker_fading(_g):
    """A genuinely heard but unseen sound persists, then fades without a new source."""
    g = Game(name="bn-e2e-sound", options=PROFILE)
    try:
        start_new_game(g)
        g.define_lua(HELPERS)
        arena(g)
        # Underground ambient noise is fixed; surface wind can mask the shout.
        assert g.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() "
                     "a:clear_bionics() a:clear_mutations() a:clear_morale() a:drop_all_items() "
                     "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) arena() "
                     "for dy=-9,9 do M:set_ter_at(here(1,dy), TerId.new('t_wall'):int_id()) "
                     "for dx=2,3 do M:set_ter_at(here(dx,dy), TerId.new('t_floor'):int_id()) "
                     "M:set_furn_at(here(dx,dy), FurnId.new('f_null'):int_id()) end end "
                     "SOUND_NPC=M:place_npc(here(2,0),'farmer') "
                     "SOUND_NPC:clear_bionics() SOUND_NPC:clear_mutations() "
                     "SOUND_NPC:clear_morale() SOUND_NPC:drop_all_items() SOUND_NPC:clear_morale() "
                     "SOUND_NPC:set_attitude(NpcAttitude.NPCATT_WAIT) out('ok')") == ["ok", "ok"]
        # Apply terrain and equipment changes before generating the sound.
        settle(g)
        assert g.lua("SOUND_NPC:shout('marker lifetime check',false) out('ok')") == ["ok"]

        def map_area():
            return "\n".join(line[:90] for line in g.screen().splitlines()[4:])

        assert wait_until(lambda: (g.keys("x", delay=0.6), "?" in map_area())[1], timeout=25), \
            "a heard, unseen NPC call should create a '?' marker:\n" + g.screen()
        assert g.lua("park(SOUND_NPC) out('ok')") == ["ok"]
        g.keys("x", delay=0.6)
        assert "?" in map_area(), "the configured three-turn marker must survive the next turn:\n" + g.screen()
        for _ in range(4):
            g.keys("x", delay=0.6)
        assert "?" not in map_area(), "sound markers should have faded:\n" + g.screen()
    finally:
        g.close()


TESTS = [
    test_sound_marker_fading,
]
