from contextual_hub import colored_cells
from helpers import HELPERS, Game, arena, settle, start_new_game, wait_until

PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "3", "HUD_WINDOWS": "false"}
AGING_PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "5", "HUD_WINDOWS": "false"}
NO_LEGEND_PROFILE = {**AGING_PROFILE, "SHOW_TIPS": "false"}
LAYOUT = "labels"
LEGEND = "? = a sound you heard, · = an older one."


def start_sound_scene(g):
    start_new_game(g)
    g.define_lua(HELPERS)
    arena(g)
    assert g.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() "
                 "a:clear_bionics() a:clear_mutations() a:clear_morale() a:drop_all_items() "
                 "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) arena() "
                 "for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end "
                 "for dy=-9,9 do M:set_ter_at(here(1,dy), TerId.new('t_wall'):int_id()) "
                 "for dx=2,3 do M:set_ter_at(here(dx,dy), TerId.new('t_floor'):int_id()) "
                 "M:set_furn_at(here(dx,dy), FurnId.new('f_null'):int_id()) end end "
                 "SOUND_NPC=M:place_npc(here(2,0),'farmer') "
                 "SOUND_NPC:clear_bionics() SOUND_NPC:clear_mutations() "
                 "SOUND_NPC:clear_morale() SOUND_NPC:drop_all_items() SOUND_NPC:clear_morale() "
                 "SOUND_NPC:set_attitude(NpcAttitude.NPCATT_WAIT) out('ok')") == ["ok", "ok"]
    settle(g)


def map_area(g):
    return "\n".join(line[:90] for line in g.screen().splitlines()[4:])


def glyph_cells(g, glyph):
    found = []
    for y, line in enumerate(g.screen_colors().splitlines()[4:], start=4):
        for x, (ch, state) in enumerate(colored_cells(line)):
            if x < 90 and ch == glyph:
                found.append((x, y, (state["fg"], state["bold"])))
    return found


def mouse_view(g):
    lines = g.screen().splitlines()
    top = next((y for y, line in enumerate(lines) if "Mouse View" in line), None)
    assert top is not None, "the mouse view should be open:\n" + g.screen()
    header = lines[top]
    assert "╭" in header and "╮" in header, "the mouse view needs a top border:\n" + header
    left = header.index("╭")
    right = header.index("╮")
    bottom = next((y for y in range(top + 1, len(lines))
                   if lines[y][left:left + 1] == "╰"), None)
    assert bottom is not None, "the mouse view should have a bottom border:\n" + g.screen()
    return "\n".join(row[left:right + 1] for row in lines[top:bottom + 1])


def test_sound_marker_fading(_g):
    g = Game(name="bn-e2e-sound", options=PROFILE, layout=LAYOUT)
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
    g = Game(name="bn-e2e-sound-aging", options=AGING_PROFILE, layout=LAYOUT)
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

        assert g.lua("local a=gapi.get_avatar() "
                     "a:set_mutation(MutationBranchId.new('DEAF')) out(a:is_deaf())") == ["true"]
        settle(g)
        assert "?" not in map_area(g) and "·" not in map_area(g), \
            "going deaf should clear every sound marker:\n" + g.screen()
    finally:
        g.close()


ACTIVITY = (
    "local a=gapi.get_avatar() "
    "a:assign_lua_activity({type=ActivityTypeId.new('ACT_HEATING'), "
    "duration=TimeDuration.from_hours(24), name='sound marker activity'}) "
    "out(a:has_activity(ActivityTypeId.new('ACT_HEATING')))"
)


def test_sound_marker_direction_above(_g):
    g = Game(name="bn-e2e-sound-z", options=NO_LEGEND_PROFILE, layout=LAYOUT)
    try:
        start_sound_scene(g)
        assert g.lua("SOUND_NPC:shout('tap',false) out('ok')") == ["ok"]
        fresh = []

        def heard():
            g.keys("x", delay=0.6)
            fresh[:] = glyph_cells(g, "?")
            return bool(fresh)

        assert wait_until(heard, timeout=25), \
            "a heard, unseen NPC call should create a marker:\n" + g.screen()
        fresh_xy = {(cell[0], cell[1]) for cell in fresh}

        assert g.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() "
                     "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) arena() out('ok')") == ["ok", "ok"]
        settle(g)
        assert any((cell[0], cell[1]) in fresh_xy for cell in glyph_cells(g, "^")), \
            "a marker should point up a level:\n" + g.screen()

        above = next(cell for cell in glyph_cells(g, "^") if (cell[0], cell[1]) in fresh_xy)
        g.hover(above[0], above[1])
        view = mouse_view(g)
        assert 'Heard yell "tap" from above' in view, \
            "the mouse view should name the marker's level:\n" + view
        assert "turn" in view, \
            "the mouse view should name the marker's age:\n" + view
        assert view.count('yell "tap"') == 1, \
            "the sound line must not be duplicated inside the mouse view:\n" + view
        assert "Sound from the" not in view, \
            "the old standalone sound line must be gone:\n" + view
    finally:
        g.close()


def test_sound_marker_ages_and_clears_during_activity(_g):
    g = Game(name="bn-e2e-sound-activity", options=NO_LEGEND_PROFILE, layout=LAYOUT)
    try:
        start_sound_scene(g)
        assert g.lua("SOUND_NPC:shout('activity marker check',false) out('ok')") == ["ok"]
        fresh = []

        def heard():
            g.keys("x", delay=0.6)
            fresh[:] = glyph_cells(g, "?")
            return bool(fresh)

        assert wait_until(heard, timeout=25), \
            "a heard, unseen NPC call should create a marker:\n" + g.screen()
        fresh_xy = {(cell[0], cell[1]) for cell in fresh}
        assert g.lua("park(SOUND_NPC) out('ok')") == ["ok"]
        assert g.lua(ACTIVITY) == ["true"]

        def cleared():
            return not any((cell[0], cell[1]) in fresh_xy
                           for glyph in ("?", "·") for cell in glyph_cells(g, glyph))

        assert wait_until(cleared, timeout=20), \
            "the activity should age the marker out:\n" + g.screen()
        assert "Activity: heating" in g.screen(), \
            "the marker must clear while the activity is still running:\n" + g.screen()
    finally:
        g.close()


TESTS = [
    test_sound_marker_fading,
    test_sound_marker_aging_and_legend,
    test_sound_marker_direction_above,
    test_sound_marker_ages_and_clears_during_activity,
]
