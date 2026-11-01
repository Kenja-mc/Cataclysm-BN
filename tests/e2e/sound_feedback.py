"""A heard but unseen source fades after the configured turns in an isolated game."""
from contextual_hub import colored_cells
from helpers import HELPERS, Game, arena, settle, start_new_game, wait_until

# map_area reads the map's screen region; floating HUD windows would draw ? and · there.
PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "3", "HUD_WINDOWS": "false"}
# A longer ceiling leaves the stale dot on screen for more than one capture.
AGING_PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "5", "HUD_WINDOWS": "false"}
LEGEND = "? = a sound you heard, · = an older one."


def start_sound_scene(g):
    """Start a fresh game in a sealed underground arena with one unseen NPC."""
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


def map_area(g):
    return "\n".join(line[:90] for line in g.screen().splitlines()[4:])


def glyph_cells(g, glyph):
    """Map-area cells with `glyph`, as (x, y, (foreground SGR, bold))."""
    found = []
    for y, line in enumerate(g.screen_colors().splitlines()[4:], start=4):
        for x, (ch, state) in enumerate(colored_cells(line)):
            if x < 90 and ch == glyph:
                found.append((x, y, (state["fg"], state["bold"])))
    return found


def test_sound_marker_fading(_g):
    """A genuinely heard but unseen sound persists, then fades without a new source."""
    g = Game(name="bn-e2e-sound", options=PROFILE)
    try:
        start_sound_scene(g)
        assert g.lua("SOUND_NPC:shout('marker lifetime check',false) out('ok')") == ["ok"]

        assert wait_until(lambda: (g.keys("x", delay=0.6), "?" in map_area(g))[1], timeout=25), \
            "a heard, unseen NPC call should create a '?' marker:\n" + g.screen()
        assert g.lua("park(SOUND_NPC) out('ok')") == ["ok"]
        g.keys("x", delay=0.6)
        assert "?" in map_area(g), \
            "the configured three-turn marker must survive the next turn:\n" + g.screen()
        for _ in range(4):
            g.keys("x", delay=0.6)
        assert "?" not in map_area(g), "sound markers should have faded:\n" + g.screen()
    finally:
        g.close()


def test_sound_marker_aging_and_legend(_g):
    """A stale marker shrinks and dims, the legend shows once, and deafness clears cues."""
    g = Game(name="bn-e2e-sound-aging", options=AGING_PROFILE)
    try:
        start_sound_scene(g)
        assert g.lua("SOUND_NPC:shout('marker aging check',false) out('ok')") == ["ok"]
        assert wait_until(
            lambda: (g.keys("x", delay=0.6), "?" in map_area(g) and LEGEND in g.screen())[1],
            timeout=25), "a first marker should explain the glyphs once:\n" + g.screen()
        assert g.screen().count(LEGEND) == 1, "the legend must be one line:\n" + g.screen()
        assert g.lua("out(gapi.get_avatar():get_value('sound_marker_legend'))") == ["1"]

        fresh = glyph_cells(g, "?")
        assert fresh, "the fresh marker should be a '?':\n" + g.screen()
        x, y, fresh_color = fresh[0]

        # A second marker must not print the legend again while the first line is still visible.
        assert g.lua("SOUND_NPC:shout('marker aging check again',false) out('ok')") == ["ok"]
        settle(g)
        assert g.screen().count(LEGEND) == 1, \
            "the legend must not repeat per marker:\n" + g.screen()
        assert g.lua("park(SOUND_NPC) out('ok')") == ["ok"]

        dot = None
        for _ in range(8):
            at_spot = [cell for cell in glyph_cells(g, "·") if cell[:2] == (x, y)]
            if at_spot:
                dot = at_spot[0]
                break
            settle(g)
        assert dot is not None, \
            f"the marker at {(x, y)} should shrink to a dot as it ages:\n" + g.screen()
        assert dot[2] != fresh_color, \
            f"the stale marker should dim: fresh {fresh_color}, stale {dot[2]}\n" + g.screen()

        # Hearing loss invalidates the cues already on the map.
        assert g.lua("local a=gapi.get_avatar() "
                     "a:set_mutation(MutationBranchId.new('DEAF')) out(a:is_deaf())") == ["true"]
        settle(g)
        assert "?" not in map_area(g) and "·" not in map_area(g), \
            "going deaf should clear every sound marker:\n" + g.screen()
    finally:
        g.close()


TESTS = [
    test_sound_marker_fading,
    test_sound_marker_aging_and_legend,
]
