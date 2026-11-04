"""Real tiles pixel checks for persistent sound markers around a scripted activity.

The curses fixture builds a lit underground arena at z-1: clean floor, an opaque
wall, and a farmer two tiles behind it.  The avatar gets DEBUG_NIGHTVISION so
sight is pinned across save/reload, the arena is underground so wind cannot
drown the shout, and the weather is pinned clear.  The fixture asserts the NPC
is unseen, the wall is visible, the open floor is visible, there is one NPC,
the hour is 12, the avatar is underground, and the avatar is not deaf.

"Play Now! (Default Scenario)" randomizes the starting profession, and several
professions (frat, escapist, heist, ...) spawn companion NPCs within ten tiles
of the avatar.  Those companions would follow the avatar into the arena, make
their own footsteps, and break the "exactly one NPC" contract.  The fixture
therefore kills every NPC it finds while clearing the levels, runs one real
turn so companions queued on the overmap become active, purges those too, and
only then places the farmer.  A second turn lets cleanup_dead() remove the
purged NPCs before the world is saved.  A randomly rolled Deaf trait is removed
so the listener can always hear.

A Lua mod is attached only to the copied tiles launch.  It never runs in the
curses fixture.  It shouts once on the second player turn, then either starts a
real six-turn ACT_HEATING activity (the activity scene) or moves the avatar one
z-level after the marker exists (above/below scenes).  Every turn is driven by
real input, so the marker is rendered at each sampled age.

Activity rendering limit: while an activity runs, handle_wait_activity_redraw()
normally redraws on the first activity turn and then on the five-minute cadence,
under a wait_popup.  A changing marker signature forces an extra redraw, and
SOUND_MARKER_PACING=true holds that frame for about 250 ms.  The state channel
records every non-skipped turn.  The paced activity scene captures the held
frame, then requires a later turn to advance without input; the unpaced scenes
assert the aged pixels after the activity.  ACT_HEATING has no idle bubble
effect, so it is not time-skipped.

Reality-bubble coordinates shift when the bubble recenters during an activity.
The scripted marker is therefore followed by its x/y offset from the avatar,
not by a fixed tripoint.

Usage:
  python3 tests/e2e/tiles.py sound_markers [--root DIR] [--binary PATH] [--out DIR] [--timeout SEC]
"""
import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path

ACTIVITY_MOD_ID = "e2e_sound_marker_activity"
Z_ABOVE_MOD_ID = "e2e_sound_marker_above"
Z_BELOW_MOD_ID = "e2e_sound_marker_below"
LIFETIME_MOD_ID = "e2e_sound_marker_lifetime"
PACING_OPTION = "SOUND_MARKER_PACING"
SIDEBAR_CELLS = 44
FONT_WIDTH = 8
FONT_HEIGHT = 16
SCALING_FACTOR = 1
TERMINAL_X = 132
TERMINAL_Y = 50
TILE = 32 * SCALING_FACTOR
MARKER_TURNS = 10
ACTIVITY_TURNS = 6
SHOUT_TURN = 2
ACTIVITY_TURN = 4
SCENE_Z = -1
MAX_MARKER_PIXELS = 2 * TILE * TILE

OPTIONS = {
    "CONTROL_SCHEME": "modern",
    "MOUSE_MOVE": "false",
    "MOUSE_TILE_SELECTION": "false",
    "CURSOR_PANNING": "false",
    "SCALING_FACTOR": str(SCALING_FACTOR),
    "TERMINAL_X": str(TERMINAL_X),
    "TERMINAL_Y": str(TERMINAL_Y),
    "FONT_WIDTH": str(FONT_WIDTH),
    "FONT_HEIGHT": str(FONT_HEIGHT),
    "TILES": "UNDEAD_PEOPLE_BASE",
    "HUD_WINDOWS": "false",
    "HUD_CORNER_BARS": "false",
    "HUD_WEATHER_BOX": "off",
    "HUD_COMBAT_BOX": "off",
    "HUD_VEHICLE_BOX": "off",
    "SIDEBAR_POSITION": "right",
    "PIXEL_MINIMAP": "false",
    "SOUND_MARKER_TURNS": str(MARKER_TURNS),
    "SOUND_MARKER_GLYPH_AGING": "true",
    PACING_OPTION: "false",
    "SHOW_TIPS": "false",
    "SHOW_WELCOME": "false",
    "FORCE_REDRAW": "true",
    "ANIMATIONS": "false",
    "TILE_EFFECT_ANIMATIONS": "false",
    "STATICZEFFECT": "false",
    "SAFEMODE": "false",
    "INITIAL_TIME": "12",
}

FIXTURE = (
    "function sound_clear_level() "
    "local a=gapi.get_avatar() local p=a:get_pos_ms() "
    "for dx=-12,12 do for dy=-12,12 do "
    "local q=TripointBubMs.new(p.x+dx,p.y+dy,p.z) "
    "M:set_ter_at(q, TerId.new('t_floor'):int_id()) "
    "M:set_furn_at(q, FurnId.new('f_null'):int_id()) M:clear_items_at(q) "
    "for _,fid in ipairs(M:get_field_ids_at(q)) do M:remove_field_at(q,fid) end "
    "local cr=gapi.get_creature_at(q) "
    "if cr and not cr:is_avatar() then "
    "if cr:is_npc() then cr:as_npc():set_all_parts_hp_cur(0) else cr:set_hp(0) end end "
    "end end end "
    "function sound_fixture() "
    "local a=gapi.get_avatar() local home=a:get_pos_ms() "
    "a:set_pos_ms(TripointBubMs.new(home.x,home.y,home.z-1)) "
    "sound_clear_level() "
    "local p=a:get_pos_ms() "
    "for dy=-6,6 do M:set_ter_at(TripointBubMs.new(p.x-1,p.y+dy,p.z), "
    "TerId.new('t_wall'):int_id()) end "
    "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) sound_clear_level() "
    "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z+1)) sound_clear_level() "
    "a:set_pos_ms(p) "
    "a:set_mutation(MutationBranchId.new('DEBUG_NIGHTVISION')) "
    "a:unset_mutation(MutationBranchId.new('DEAF')) "
    "assert(not a:is_deaf(),'fixture listener must be able to hear') "
    "local omt=gapi.bub_to_abs(p):to_omt() gapi.set_omt_weather_override(omt,3,'clear',nil) "
    "out('fixture') end "
    "function sound_purge_npcs() "
    "for _,n in ipairs(gapi.get_all_npcs()) do n:set_all_parts_hp_cur(0) end "
    "out('purged') end "
    "function sound_place_npc() "
    "local a=gapi.get_avatar() local p=a:get_pos_ms() "
    "SOUND_NPC=M:place_npc(TripointBubMs.new(p.x-2,p.y,p.z),'farmer') "
    "SOUND_NPC:clear_bionics() SOUND_NPC:clear_mutations() "
    "SOUND_NPC:clear_morale() SOUND_NPC:drop_all_items() "
    "SOUND_NPC:set_attitude(NpcAttitude.NPCATT_WAIT) "
    "out('npc') end "
    "function sound_cleanup() "
    "for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end out('clean') end "
    "function sound_sight() "
    "local a=gapi.get_avatar() local p=a:get_pos_ms() "
    "out(a:sees(TripointBubMs.new(p.x-2,p.y,p.z)), "
    "a:sees(TripointBubMs.new(p.x-1,p.y,p.z)), "
    "a:sees(TripointBubMs.new(p.x+2,p.y,p.z)), #gapi.get_all_npcs(), "
    "gapi.current_turn():hour_of_day(), p.z, a:is_deaf()) end"
)

SIGHT_EXPECTED = ["false", "true", "true", "1", "12", str(SCENE_Z), "false"]
SIGHT_NAMES = ["NPC tile hidden", "wall tile visible", "open floor visible",
               "exactly one NPC", "game hour is INITIAL_TIME 12", "underground scene",
               "listener is not deaf"]

MODINFO = {
    "type": "MOD_INFO",
    "id": "",
    "name": "E2E sound markers",
    "description": "Schedules one unseen NPC shout, then a scripted activity or a z-level move.",
    "category": "content",
    "lua_api_version": 2,
    "dependencies": ["bn"],
}

SCRIPT_HEAD = """local mod = game.mod_runtime[game.current_mod]
mod.turns = 0
mod.armed = true

game.add_hook("on_game_load", function(params)
  mod.turns = 0
  mod.armed = true
  local avatar = gapi.get_avatar()
  local omt = gapi.bub_to_abs(avatar:get_pos_ms()):to_omt()
  gapi.set_omt_weather_override(omt, 3, "clear", nil)
  return true
end)
"""

ACTIVITY_SCRIPT = SCRIPT_HEAD + """
game.add_hook("on_npc_do_turn", function(params)
  if not mod.armed then return true end
  for _, m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end
  mod.turns = mod.turns + 1
  if mod.turns == __SHOUT_TURN__ then
    params.npc:shout("sound marker check", false)
  elseif mod.turns == __ACTIVITY_TURN__ then
    mod.armed = false
    gapi.get_avatar():assign_lua_activity({
      type = ActivityTypeId.new("ACT_HEATING"),
      duration = TimeDuration.from_turns(__ACTIVITY_TURNS__),
      name = "sound marker activity",
      interruptable = false,
    })
  end
  return true
end)
""".replace("__SHOUT_TURN__", str(SHOUT_TURN)).replace(
    "__ACTIVITY_TURN__", str(ACTIVITY_TURN)).replace("__ACTIVITY_TURNS__", str(ACTIVITY_TURNS))


def z_script(dz):
    return SCRIPT_HEAD + """
game.add_hook("on_npc_do_turn", function(params)
  if not mod.armed then return true end
  for _, m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end
  mod.turns = mod.turns + 1
  if mod.turns == __SHOUT_TURN__ then
    params.npc:shout("sound marker check", false)
  elseif mod.turns == __MOVE_TURN__ then
    mod.armed = false
    local avatar = gapi.get_avatar()
    local p = avatar:get_pos_ms()
    avatar:set_pos_ms(TripointBubMs.new(p.x, p.y, p.z + (__DZ__)))
  end
  return true
end)
""".replace("__SHOUT_TURN__", str(SHOUT_TURN)).replace("__MOVE_TURN__", str(ACTIVITY_TURN)).replace(
        "__DZ__", str(dz))


LIFETIME_SCRIPT = SCRIPT_HEAD + """
game.add_hook("on_npc_do_turn", function(params)
  if not mod.armed then return true end
  for _, m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end
  mod.turns = mod.turns + 1
  if mod.turns == __SHOUT_TURN__ then
    mod.armed = false
    params.npc:shout("sound marker check", false)
  end
  return true
end)
""".replace("__SHOUT_TURN__", str(SHOUT_TURN))


@dataclass(frozen=True)
class Blob:
    x0: int
    y0: int
    x1: int
    y1: int
    count: int
    mean: tuple

    @property
    def center(self):
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    @property
    def luma(self):
        return 0.3 * self.mean[0] + 0.6 * self.mean[1] + 0.1 * self.mean[2]

    def summary(self):
        return {"bbox": [self.x0, self.y0, self.x1, self.y1], "count": self.count,
                "center": [round(self.center[0], 1), round(self.center[1], 1)],
                "mean": [round(channel, 1) for channel in self.mean]}


@dataclass
class Sample:
    png: Path
    state: dict
    frame: tuple
    blob: Blob | None


def require(condition, message):
    import tiles

    if not condition:
        raise tiles.Failure(message)


def write_mods(session):
    root = session.curses_userdir / "mods"
    for mod_id, script in ((ACTIVITY_MOD_ID, ACTIVITY_SCRIPT),
                           (Z_ABOVE_MOD_ID, z_script(-1)),
                           (Z_BELOW_MOD_ID, z_script(1)),
                           (LIFETIME_MOD_ID, LIFETIME_SCRIPT)):
        folder = root / mod_id
        folder.mkdir(parents=True, exist_ok=True)
        info = dict(MODINFO)
        info["id"] = mod_id
        (folder / "modinfo.json").write_text(json.dumps([info], indent=2))
        (folder / "preload.lua").write_text(script)


def build_sound_marker_world(session):
    import tiles

    tiles.tmux_game.ROOT = session.root
    write_mods(session)
    game = tiles.Game(
        name="bn-tiles-sound-marker-fixture",
        userdir=session.curses_userdir,
        options={"SAFEMODE": "false", "INITIAL_TIME": "12", "RANDOM_NPC": "false",
                 "STATIC_NPC": "false", "STARTING_NPC": "never", "SPAWN_DENSITY": "0",
                 "SPAWN_ANIMAL_DENSITY": "0", "WANDER_SPAWNS": "false",
                 "VEHICLE_SPAWNRATE": "0", "ANIMATIONS": "false"},
    )
    def fixture_call(code):
        return game.lua(tiles.HELPERS + " " + FIXTURE + " " + code)

    try:
        tiles.start_new_game(game)
        require(fixture_call("sound_fixture()") == ["fixture"],
                "fixture scene did not build:\n" + game.screen())
        # One real turn activates every NPC the overmap has queued for this
        # bubble, including companions of a randomly rolled Play Now profession.
        # Only then can the purge see and kill all of them.
        tiles.settle(game)
        require(fixture_call("sound_purge_npcs()") == ["purged"],
                "fixture NPC purge failed:\n" + game.screen())
        require(fixture_call("sound_place_npc()") == ["npc"],
                "fixture NPC placement failed:\n" + game.screen())
        # Activate the farmer and let cleanup_dead() remove the purged NPCs
        # before the world is saved.
        tiles.settle(game)
        require(fixture_call("sound_cleanup()") == ["clean"],
                "fixture cleanup did not finish:\n" + game.screen())
        sight = fixture_call("sound_sight()")
        require(len(sight) == 1, f"fixture sight query returned {sight}")
        values = sight[0].split(",")
        mismatched = [f"{name}: got {value}, want {want}"
                      for name, value, want in zip(SIGHT_NAMES, values, SIGHT_EXPECTED) if value != want]
        require(len(values) == len(SIGHT_EXPECTED) and not mismatched,
                "fixture is not as designed: " + "; ".join(mismatched or [str(values)]))
        require(game.lua("out(gdebug.save_game())") == ["true"],
                "saving the fixture world failed:\n" + game.screen())
        (session.artifacts / "fixture-curses.txt").write_text(game.screen_colors())
        (session.artifacts / "fixture-sight.txt").write_text("\n".join(
            f"{name}: {value}" for name, value in zip(SIGHT_NAMES, values)) + "\n")
    finally:
        game.close()
    saves = [path for path in (session.curses_userdir / "save").iterdir() if path.is_dir()]
    require(len(saves) == 1, f"expected one fixture world, found {saves}")
    session.world = saves[0].name


def state_of(live):
    try:
        return json.loads(live.state_path.read_text())
    except (OSError, ValueError):
        return None


def sound_markers(state):
    if state is None:
        return None
    return [entry for entry in state.get("map_overlays", [])
            if entry.get("kind") == "sound_marker"]


def scripted_markers(state):
    player = player_pos(state)
    raw = sound_markers(state)
    if player is None or raw is None:
        return []
    origin = (player[0] - 2, player[1])
    found = [entry for entry in raw
             if abs(entry["pos"][0] - origin[0]) <= 3 and abs(entry["pos"][1] - origin[1]) <= 3]
    found.sort(key=lambda entry: (entry.get("age", 0),
                                  abs(entry["pos"][0] - origin[0]) + abs(entry["pos"][1] - origin[1])))
    return found


def marker_entry(state, pos):
    for entry in sound_markers(state) or []:
        if tuple(entry["pos"]) == tuple(pos):
            return entry
    return None


def marker_offset(state, pos):
    avatar = player_pos(state)
    require(avatar is not None and len(avatar) == 3, "the sample state has no avatar position")
    return (pos[0] - avatar[0], pos[1] - avatar[1], pos[2])


def tracked_pos(state, offset):
    avatar = player_pos(state)
    require(avatar is not None and len(avatar) == 3, "the sample state has no avatar position")
    return (avatar[0] + offset[0], avatar[1] + offset[1], offset[2])


def tracked_entry(state, offset):
    if state is None:
        return None
    return marker_entry(state, tracked_pos(state, offset))


def tracked_signature(state, offset):
    if state is None:
        return None
    entry = tracked_entry(state, offset)
    return (turn_of(state), player_pos(state), None if entry is None else entry.get("age"))


def player_pos(state):
    if state is None:
        return None
    return tuple(state.get("player", {}).get("pos", ()))


def turn_of(state):
    return None if state is None else state.get("turn")


def marker_signature(state):
    found = sound_markers(state)
    if found is None:
        return None
    return tuple(sorted((tuple(entry["pos"]), entry.get("age")) for entry in found))


def state_signature(state):
    if state is None:
        return None
    return (turn_of(state), player_pos(state), marker_signature(state))


def wait_state(live, check, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = state_of(live)
        if state is not None and check(state):
            return state
        time.sleep(0.1)
    return None


def wait_no_marker(live, timeout=20):
    return wait_state(live, lambda state: sound_markers(state) == [], timeout=timeout)


def map_limit(frame):
    width = frame[0]
    limit = min(width, (TERMINAL_X - SIDEBAR_CELLS) * FONT_WIDTH * SCALING_FACTOR)
    require(limit > 0, f"window {width}px leaves no map area before the sidebar")
    return limit


def changed_blob(baseline, frame, limit):
    width, height, left = baseline
    other_width, other_height, right = frame
    require((width, height) == (other_width, other_height),
            f"frames differ in size: {width}x{height} vs {other_width}x{other_height}")
    limit = min(limit, width)
    x0, y0, x1, y1 = width, height, -1, -1
    count = 0
    totals = [0, 0, 0]
    for y in range(height):
        start = y * width * 3
        end = start + limit * 3
        row_left = left[start:end]
        row_right = right[start:end]
        if row_left == row_right:
            continue
        delta = (int.from_bytes(row_left, "big") ^ int.from_bytes(row_right, "big")).to_bytes(
            len(row_left), "big")
        for x in range(limit):
            offset = x * 3
            if not (delta[offset] or delta[offset + 1] or delta[offset + 2]):
                continue
            count += 1
            x0 = min(x0, x)
            x1 = max(x1, x)
            y0 = min(y0, y)
            y1 = max(y1, y)
            totals[0] += row_right[offset]
            totals[1] += row_right[offset + 1]
            totals[2] += row_right[offset + 2]
    if count == 0:
        return None
    return Blob(x0, y0, x1, y1, count,
                (totals[0] / count, totals[1] / count, totals[2] / count))


def changed_blob_region(baseline, frame, x0, y0, x1, y1):
    width, height, left = baseline
    other_width, other_height, right = frame
    require((width, height) == (other_width, other_height), "frames differ in size")
    x0 = max(0, min(x0, width - 1))
    x1 = max(x0 + 1, min(x1, width))
    y0 = max(0, min(y0, height - 1))
    y1 = max(y0 + 1, min(y1, height))
    count = 0
    totals = [0, 0, 0]
    bx0, by0, bx1, by1 = x1, y1, -1, -1
    for y in range(y0, y1):
        start = (y * width + x0) * 3
        end = (y * width + x1) * 3
        row_left = left[start:end]
        row_right = right[start:end]
        if row_left == row_right:
            continue
        delta = (int.from_bytes(row_left, "big") ^ int.from_bytes(row_right, "big")).to_bytes(
            len(row_left), "big")
        for x in range(x1 - x0):
            offset = x * 3
            if not (delta[offset] or delta[offset + 1] or delta[offset + 2]):
                continue
            count += 1
            px = x0 + x
            bx0 = min(bx0, px)
            bx1 = max(bx1, px)
            by0 = min(by0, y)
            by1 = max(by1, y)
            totals[0] += row_right[offset]
            totals[1] += row_right[offset + 1]
            totals[2] += row_right[offset + 2]
    if count == 0:
        return None
    return Blob(bx0, by0, bx1, by1, count,
                (totals[0] / count, totals[1] / count, totals[2] / count))


def marker_tile_rect(frame, state, pos=None):
    if pos is None:
        found = sound_markers(state)
        require(found, "the sample state carries no marker")
        pos = found[0]["pos"]
    center = expected_tile_center(frame, player_pos(state), pos)
    half = TILE // 2
    return (int(center[0]) - half, int(center[1]) - half,
            int(center[0]) + half, int(center[1]) + half)


def capture_frame(session, window, png):
    import tiles

    return tiles.frame_rgb(tiles.capture(session.display, window, png))


def expected_tile_center(frame, avatar, marker):
    width, height = frame[0], frame[1]
    require(width == TERMINAL_X * FONT_WIDTH * SCALING_FACTOR,
            f"capture width {width}px does not match TERMINAL_X={TERMINAL_X} and "
            f"FONT_WIDTH={FONT_WIDTH} at scale {SCALING_FACTOR}")
    require(height == TERMINAL_Y * FONT_HEIGHT * SCALING_FACTOR,
            f"capture height {height}px does not match TERMINAL_Y={TERMINAL_Y} and "
            f"FONT_HEIGHT={FONT_HEIGHT} at scale {SCALING_FACTOR}")
    columns = ((TERMINAL_X - SIDEBAR_CELLS) * FONT_WIDTH * SCALING_FACTOR) // TILE
    rows = height // TILE
    posx, posy = columns // 2, rows // 2
    return ((marker[0] - avatar[0] + posx) * TILE + TILE // 2,
            (marker[1] - avatar[1] + posy) * TILE + TILE // 2)


def check_at_tile(blob, frame, state, label, pos=None):
    markers = sound_markers(state)
    require(markers, f"{label}: no marker in the sample state")
    avatar = player_pos(state)
    require(avatar is not None, f"{label}: sample state has no player position")
    if pos is None:
        pos = markers[0]["pos"]
    expected = expected_tile_center(frame, avatar, pos)
    distance = math.hypot(blob.center[0] - expected[0], blob.center[1] - expected[1])
    require(distance <= TILE,
            f"{label}: changed pixels are {distance:.1f}px from the marker tile at {expected}, "
            f"blob {blob.summary()}")
    return distance


def stable_input_sample(session, window, live, png):
    import tiles

    last = "no attempt"
    for _ in range(4):
        before = state_of(live)
        first = capture_frame(session, window, png)
        after = state_of(live)
        if before is None or after is None:
            last = "the state file was unreadable during the capture"
            time.sleep(0.2)
            continue
        if state_signature(before) != state_signature(after):
            last = "state changed while the frame was captured"
            time.sleep(0.2)
            continue
        time.sleep(0.3)
        second = capture_frame(session, window, png)
        if changed_blob(first, second, map_limit(first)) is not None:
            last = "the map kept changing after the capture"
            time.sleep(0.2)
            continue
        return Sample(png=png, state=after, frame=first, blob=None)
    raise tiles.Failure(f"{png.name}: {last}")


def clean_frame(session, window, png, live=None, timeout=10, offset=None):
    import tiles

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = state_of(live) if live is not None else None
        if live is not None and (state is None or
                                 (tracked_entry(state, offset) is not None if offset
                                  else sound_markers(state) != [])):
            time.sleep(0.2)
            continue
        first = capture_frame(session, window, png)
        time.sleep(0.3)
        second = capture_frame(session, window, png)
        if changed_blob(first, second, map_limit(first)) is None:
            return first, state
    raise tiles.Failure(f"{png.name}: the marker-free map never settled")


def press_turn(x11, live, label, timeout=10):
    import tiles

    before = state_of(live)
    previous = turn_of(before)
    x11.key("x", delay=0.8)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = state_of(live)
        if state is not None and (previous is None or (turn_of(state) or -1) > previous):
            return state
        time.sleep(0.1)
    raise tiles.Failure(f"{label}: the wait key did not advance a recorded turn")


def analyse_marker(session, slots, clean, label, glyph_aging, rect, offset):
    fresh, aged = slots["fresh"], slots["aged"]
    fresh_blob = changed_blob_region(clean, fresh.frame, *rect)
    aged_blob = changed_blob_region(clean, aged.frame, *rect)
    require(fresh_blob is not None, f"{label}: the fresh marker frame is identical to the clean map")
    require(aged_blob is not None, f"{label}: the aged marker frame is identical to the clean map")
    require(fresh_blob.count <= MAX_MARKER_PIXELS,
            f"{label}: the fresh change covered {fresh_blob.count}px, more than one sprite")
    require(aged_blob.count <= MAX_MARKER_PIXELS,
            f"{label}: the aged change covered {aged_blob.count}px, more than one sprite")
    check_at_tile(fresh_blob, fresh.frame, fresh.state, f"{label} fresh",
                  tracked_pos(fresh.state, offset))
    check_at_tile(aged_blob, aged.frame, aged.state, f"{label} aged",
                  tracked_pos(aged.state, offset))
    fresh_entry = tracked_entry(fresh.state, offset)
    aged_entry = tracked_entry(aged.state, offset)
    fresh_age = fresh_entry.get("age") if fresh_entry else None
    aged_age = aged_entry.get("age") if aged_entry else None
    require(fresh_age is not None and fresh_age <= 1,
            f"{label}: the pre-activity marker was age {fresh_age}, not fresh")
    require(aged_age is not None and aged_age >= 2,
            f"{label}: the post-activity marker was age {aged_age}, not aged")
    if glyph_aging:
        require(aged_blob.count * 4 < fresh_blob.count,
                f"{label}: an aged marker must shrink to the dot, fresh {fresh_blob.count}px, "
                f"aged {aged_blob.count}px")
    else:
        require(aged_blob.count * 2 >= fresh_blob.count,
                f"{label}: with shrinking disabled the aged marker must keep its sprite, "
                f"fresh {fresh_blob.count}px, aged {aged_blob.count}px")
    if glyph_aging or fresh_age == 0:
        require(abs(aged_blob.luma - fresh_blob.luma) > 2.0,
                f"{label}: the aged marker did not change colour, fresh {fresh_blob.luma:.1f}, "
                f"aged {aged_blob.luma:.1f}")
    return {"fresh": fresh_blob.summary(), "aged": aged_blob.summary(),
            "fresh_age": fresh_age, "aged_age": aged_age}


def capture_paced_activity(session, window, live, baseline, label, before_assign, offset):
    import tiles

    attempt = 0
    started_at = time.monotonic()
    trace = [{"offset": list(offset)}]
    last_turn = turn_of(before_assign)
    dot_frames = []
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        before = state_of(live)
        png = session.artifacts / f"{label}-during-{attempt:03d}.png"
        attempt += 1
        frame = capture_frame(session, window, png)
        after = state_of(live)
        tracked_before = tracked_entry(before, offset) if before is not None else None
        tracked_after = tracked_entry(after, offset) if after is not None else None
        region_before = [(list(entry["pos"]), entry.get("age"))
                         for entry in (scripted_markers(before) if before is not None else [])]
        region_after = [(list(entry["pos"]), entry.get("age"))
                        for entry in (scripted_markers(after) if after is not None else [])]
        trace.append({
            "t": round(time.monotonic() - started_at, 3),
            "before_turn": turn_of(before),
            "after_turn": turn_of(after),
            "before_player": list(player_pos(before) or ()),
            "after_player": list(player_pos(after) or ()),
            "before_age": (sound_markers(before) or [{}])[0].get("age"),
            "after_age": (sound_markers(after) or [{}])[0].get("age"),
            "tracked_before_age": tracked_before.get("age") if tracked_before else None,
            "tracked_after_age": tracked_after.get("age") if tracked_after else None,
            "region_before": region_before,
            "region_after": region_after,
            "png": png.name,
        })
        if after is not None and last_turn is not None and turn_of(after) > last_turn:
            for pending_frame, pending_state, pending_blob, pending_png in dot_frames:
                if pending_state is not None and turn_of(after) > turn_of(pending_state):
                    (session.artifacts / f"{label}-during-trace.json").write_text(json.dumps(trace, indent=2))
                    return (pending_frame, pending_state, pending_blob, pending_png, after,
                            tracked_pos(pending_state, offset))
            last_turn = turn_of(after)
        if before is None or after is None:
            continue
        if turn_of(before) != turn_of(after) or \
                tracked_signature(before, offset) != tracked_signature(after, offset):
            continue
        entry = tracked_entry(before, offset)
        if entry is None or entry["age"] < 2:
            continue
        blob = changed_blob_region(baseline, frame,
                                   *marker_tile_rect(frame, before, tracked_pos(before, offset)))
        if blob is not None:
            dot_frames.append((frame, after, blob, png))
    (session.artifacts / f"{label}-during-trace.json").write_text(json.dumps(trace, indent=2))
    raise tiles.Failure(
        f"{label}: real-time pacing did not expose a held activity frame with the aged marker. "
        f"{attempt} frames were captured; no aged-marker frame was followed by a turn advancing "
        f"without input, so no frame proves the activity was still running. Expected "
        f"{PACING_OPTION}=true to hold each age transition ~250 ms inside the activity.")


def wait_activity_end(live, quiet=2.5, timeout=30):
    last_turn = turn_of(state_of(live))
    last_change = time.monotonic()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = state_of(live)
        if state is not None:
            turn = turn_of(state)
            if turn != last_turn:
                last_turn = turn
                last_change = time.monotonic()
        if last_turn is not None and time.monotonic() - last_change >= quiet:
            return last_turn
        time.sleep(0.1)
    return last_turn


def run_activity_scene(session, label, glyph_aging, pacing):
    import tiles

    options = dict(OPTIONS)
    options["SOUND_MARKER_GLYPH_AGING"] = "true" if glyph_aging else "false"
    options[PACING_OPTION] = "true" if pacing else "false"
    with session.running_game(label, options, state_out=True, world_mods=[ACTIVITY_MOD_ID]) as live:
        x11 = tiles.X11(session.display)
        try:
            window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
            require(window is not None, f"{label}: game window disappeared")
            x11.focus_local(window, (TERMINAL_X - SIDEBAR_CELLS) * FONT_WIDTH + 20, 20)
            baseline, _ = clean_frame(session, window, session.artifacts / f"{label}-before.png")
            state = press_turn(x11, live, label)
            start_turn = turn_of(state)
            state = press_turn(x11, live, label)
            before_positions = {tuple(entry["pos"]) for entry in (sound_markers(state) or [])}
            state = press_turn(x11, live, label)
            require(state is not None, f"{label}: unreadable state after the shout")
            scripted = [entry for entry in scripted_markers(state)
                        if tuple(entry["pos"]) not in before_positions]
            require(len(scripted) == 1,
                    f"{label}: the shout turn must create exactly one new marker in the scripted "
                    f"region; got {scripted}. All markers: {sound_markers(state)}")
            scripted_pos = tuple(scripted[0]["pos"])
            scripted_offset = marker_offset(state, scripted_pos)
            scripted_region = [dict(entry) for entry in scripted]
            require(scripted[0].get("age") == 0,
                    f"{label}: the scripted marker was not new: {scripted}")
            fresh = stable_input_sample(session, window, live,
                                        session.artifacts / f"{label}-fresh.png")
            fresh_entry = tracked_entry(fresh.state, scripted_offset)
            require(fresh_entry and fresh_entry["age"] <= 1,
                    f"{label}: the scripted marker was not fresh before the activity: "
                    f"{fresh.state.get('map_overlays')}")
            marker_rect = marker_tile_rect(fresh.frame, fresh.state,
                                           tracked_pos(fresh.state, scripted_offset))

            before_assign = state_of(live)
            require(before_assign is not None, f"{label}: unreadable state before the activity")
            before_entry = tracked_entry(before_assign, scripted_offset)
            require(before_entry and before_entry["age"] <= 1,
                    f"{label}: the scripted marker was not fresh before the activity: "
                    f"{before_assign.get('map_overlays')}")
            fresh_blob = changed_blob_region(baseline, fresh.frame, *marker_rect)
            require(fresh_blob is not None, f"{label}: the fresh marker frame did not differ from the clean map")

            later_turn = None
            during_png = None
            if pacing:
                for warm in range(2):
                    capture_frame(session, window,
                                  session.artifacts / f"{label}-prewarm-{warm}.png")
            x11.key("x", delay=0 if pacing else 0.8)
            if pacing:
                (during_frame, during_state, during_blob, during_png, later_turn,
                 during_pos) = capture_paced_activity(
                    session, window, live, baseline, label, before_assign, scripted_offset)
                finished_turn = wait_activity_end(live)
                advanced = finished_turn - turn_of(before_assign)
                require(advanced >= ACTIVITY_TURNS,
                        f"{label}: the activity advanced only {advanced} turns")
                during_entry = marker_entry(during_state, during_pos)
                require(during_entry is not None,
                        f"{label}: the scripted marker vanished during the activity")
                during_age = during_entry["age"]
                check_at_tile(during_blob, during_frame, during_state, f"{label} mid-activity", during_pos)
                if glyph_aging:
                    require(during_blob.count * 4 < fresh_blob.count,
                            f"{label}: state age {during_age} but the frame rendered {during_blob.count}px; "
                            f"expected the aged dot (fresh {fresh_blob.count}px). Frame/state mismatch.")
                else:
                    require(during_blob.count * 2 >= fresh_blob.count,
                            f"{label}: state age {during_age} but the frame rendered {during_blob.count}px; "
                            f"expected the aged sprite (fresh {fresh_blob.count}px). Frame/state mismatch.")
                require(abs(during_blob.luma - fresh_blob.luma) > 2.0,
                        f"{label}: the mid-activity marker did not change colour, "
                        f"fresh {fresh_blob.luma:.1f}, during {during_blob.luma:.1f}")
            else:
                started = wait_state(
                    live, lambda current: turn_of(current) is not None
                    and turn_of(current) > turn_of(before_assign), timeout=15)
                require(started is not None,
                        f"{label}: assigning the activity never advanced the state")
                finished_turn = wait_activity_end(live)
                advanced = finished_turn - turn_of(before_assign)
                require(advanced >= ACTIVITY_TURNS,
                        f"{label}: the activity advanced only {advanced} turns")
                during_state = state_of(live)
                during_entry = tracked_entry(during_state, scripted_offset)
                require(during_entry and during_entry["age"] >= 2,
                        f"{label}: the activity ran without aging the scripted marker: "
                        f"{(during_state or {}).get('map_overlays')}")
                during_png = None
                during_age = during_entry["age"]

            require(during_age < MARKER_TURNS,
                    f"{label}: a marker outlived SOUND_MARKER_TURNS={MARKER_TURNS}: {during_age}")

            state = press_turn(x11, live, label)
            aged = stable_input_sample(session, window, live,
                                       session.artifacts / f"{label}-after-activity.png")
            aged.blob = changed_blob(baseline, aged.frame, map_limit(aged.frame))
            aged_entry = tracked_entry(aged.state, scripted_offset)
            require(aged_entry and aged_entry["age"] >= 2,
                    f"{label}: the post-activity capture was not an aged scripted marker: "
                    f"{aged.state.get('map_overlays')}")

            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                state = state_of(live)
                if state is not None and tracked_entry(state, scripted_offset) is None:
                    break
                x11.key("x", delay=0.8)
                time.sleep(0.2)
            else:
                raise tiles.Failure(f"{label}: the marker never disappeared after the activity")
            gone_clean, gone_state = clean_frame(session, window,
                                                 session.artifacts / f"{label}-clean.png",
                                                 live=live, offset=scripted_offset)
            require(gone_state is not None and tracked_entry(gone_state, scripted_offset) is None,
                    f"{label}: the clean frame was taken with the scripted marker still present")
            require(changed_blob_region(baseline, gone_clean, *marker_rect) is None,
                    f"{label}: the marker tile did not return to its before frame after the activity")
            external = changed_blob(baseline, gone_clean, map_limit(gone_clean))
            observations = analyse_marker(session, {"fresh": fresh, "aged": aged},
                                          gone_clean, label, glyph_aging, marker_rect, scripted_offset)
            observations.update({
                "glyph_aging": glyph_aging,
                "pacing": pacing,
                "start_turn": start_turn,
                "activity_before_turn": turn_of(before_assign),
                "finished_turn": finished_turn,
                "activity_turn_delta": advanced,
                "during_age": during_age,
                "during_png": during_png.name if during_png else None,
                "during_later_turn": turn_of(later_turn) if later_turn else None,
                "fresh_png": fresh.png.name,
                "aged_png": aged.png.name,
                "scripted_region_markers": scripted_region,
                "external_delta_after_clear": external.summary() if external else None,
            })
            if pacing:
                observations["during"] = during_blob.summary()
            observations["weather"] = ((state_of(live) or {}).get("hud") or {}).get("weather")
        finally:
            x11.close()
    return observations


def run_lifetime_scene(session, label):
    import tiles

    options = dict(OPTIONS)
    options["SOUND_MARKER_TURNS"] = "3"
    options[PACING_OPTION] = "false"
    with session.running_game(label, options, state_out=True, world_mods=[LIFETIME_MOD_ID]) as live:
        x11 = tiles.X11(session.display)
        try:
            window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
            require(window is not None, f"{label}: game window disappeared")
            x11.focus_local(window, (TERMINAL_X - SIDEBAR_CELLS) * FONT_WIDTH + 20, 20)
            baseline, _ = clean_frame(session, window, session.artifacts / f"{label}-before.png")
            press_turn(x11, live, label)
            state = press_turn(x11, live, label)
            before_positions = {tuple(entry["pos"]) for entry in (sound_markers(state) or [])}
            state = press_turn(x11, live, label)
            scripted = [entry for entry in scripted_markers(state)
                        if tuple(entry["pos"]) not in before_positions]
            require(len(scripted) == 1 and scripted[0]["age"] == 0,
                    f"{label}: the shout turn must create exactly one new lifetime marker; "
                    f"got {scripted}. All markers: {(state or {}).get('map_overlays')}")
            lifetime_pos = tuple(scripted[0]["pos"])
            lifetime_offset = marker_offset(state, lifetime_pos)
            fresh = stable_input_sample(session, window, live,
                                        session.artifacts / f"{label}-age0.png")
            lifetime_rect = marker_tile_rect(fresh.frame, fresh.state,
                                             tracked_pos(fresh.state, lifetime_offset))
            fresh_blob = changed_blob_region(baseline, fresh.frame, *lifetime_rect)
            require(fresh_blob is not None, f"{label}: age-0 marker did not draw over its level")
            dot = None
            for expected in (1, 2):
                state = press_turn(x11, live, label)
                entry = tracked_entry(state, lifetime_offset)
                require(entry and entry["age"] == expected,
                        f"{label}: SOUND_MARKER_TURNS=3 must keep the scripted marker at age {expected}, "
                        f"got {(state or {}).get('map_overlays')}")
                sample = stable_input_sample(
                    session, window, live,
                    session.artifacts / f"{label}-age{expected}.png")
                if expected == 2:
                    dot = changed_blob_region(baseline, sample.frame, *lifetime_rect)
            state = press_turn(x11, live, label)
            require(tracked_entry(state, lifetime_offset) is None,
                    f"{label}: SOUND_MARKER_TURNS=3 must clear the scripted marker when it reaches age 3, "
                    f"got {(state or {}).get('map_overlays')}")
            clean, clean_state = clean_frame(session, window,
                                             session.artifacts / f"{label}-clean.png",
                                             live=live, offset=lifetime_offset)
            require(changed_blob_region(baseline, clean, *lifetime_rect) is None,
                    f"{label}: the marker tile did not return to its before frame after the exact lifetime")
            lifetime_external = changed_blob(baseline, clean, map_limit(clean))
            require(dot is not None, f"{label}: no age-2 dot frame")
            check_at_tile(dot, sample.frame, sample.state, f"{label} age 2",
                          tracked_pos(sample.state, lifetime_offset))
            require(dot.count * 4 < fresh_blob.count,
                    f"{label}: the default-lifetime age-2 marker must be the dot, "
                    f"age0 {fresh_blob.count}px, age2 {dot.count}px")
            observations = {
                "default_turns": 3,
                "visible_ages": [0, 1, 2],
                "cleared_at_age": 3,
                "age0": fresh_blob.summary(),
                "age2": dot.summary(),
                "age0_png": fresh.png.name,
                "age2_png": sample.png.name,
                "clean_png": f"{label}-clean.png",
                "external_delta_after_clear": lifetime_external.summary() if lifetime_external else None,
            }
            (session.artifacts / f"{label}-observations.json").write_text(json.dumps(observations, indent=2))
        finally:
            x11.close()
    return observations


def run_z_scene(session, label, mod_id, dz):
    import tiles

    with session.running_game(label, dict(OPTIONS), state_out=True, world_mods=[mod_id]) as live:
        x11 = tiles.X11(session.display)
        try:
            window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
            require(window is not None, f"{label}: game window disappeared")
            x11.focus_local(window, (TERMINAL_X - SIDEBAR_CELLS) * FONT_WIDTH + 20, 20)
            baseline, _ = clean_frame(session, window, session.artifacts / f"{label}-before.png")
            press_turn(x11, live, label)
            state = press_turn(x11, live, label)
            before_positions = {tuple(entry["pos"]) for entry in (sound_markers(state) or [])}
            state = press_turn(x11, live, label)
            require(state is not None, f"{label}: unreadable state after the shout")
            scripted = [entry for entry in scripted_markers(state)
                        if tuple(entry["pos"]) not in before_positions]
            require(len(scripted) == 1,
                    f"{label}: the shout turn must create exactly one new marker in the scripted "
                    f"region; got {scripted}. All markers: {sound_markers(state)}")
            scripted_pos = tuple(scripted[0]["pos"])
            scripted_offset = marker_offset(state, scripted_pos)
            fresh = stable_input_sample(session, window, live,
                                        session.artifacts / f"{label}-fresh.png")
            fresh.blob = changed_blob_region(
                baseline, fresh.frame,
                *marker_tile_rect(fresh.frame, fresh.state,
                                  tracked_pos(fresh.state, scripted_offset)))
            require(fresh.blob is not None, f"{label}: the fresh marker did not draw over its level")
            require(player_pos(fresh.state)[2] == SCENE_Z,
                    f"{label}: the fresh marker was not captured at the scene level")
            fresh_entry = tracked_entry(fresh.state, scripted_offset)
            require(fresh_entry is not None,
                    f"{label}: the scripted marker was not on the scene level")

            state = press_turn(x11, live, label)
            require(player_pos(state)[2] == SCENE_Z + dz,
                    f"{label}: the script did not move the avatar by {dz} z-levels: "
                    f"{player_pos(state)}")
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                entry = tracked_entry(state, scripted_offset)
                if entry and entry.get("age", 0) >= 2:
                    break
                state = press_turn(x11, live, label, timeout=15)
            else:
                raise tiles.Failure(f"{label}: the z marker never aged to two turns")
            aged = stable_input_sample(session, window, live,
                                       session.artifacts / f"{label}-aged.png")
            aged_entry = tracked_entry(aged.state, scripted_offset)
            require(aged_entry and aged_entry["age"] >= 2,
                    f"{label}: the z capture was not an aged scripted marker: "
                    f"{aged.state.get('map_overlays')}")
            require(aged_entry["pos"][2] == SCENE_Z,
                    f"{label}: the marker moved off the scene level: {aged.state.get('map_overlays')}")
            marker_z = aged_entry["pos"][2]
            player_z = player_pos(aged.state)[2]
            if dz < 0:
                require(marker_z > player_z, f"{label}: the marker must be above the avatar")
            else:
                require(marker_z < player_z, f"{label}: the marker must be below the avatar")

            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                state = state_of(live)
                if state is not None and tracked_entry(state, scripted_offset) is None:
                    break
                x11.key("x", delay=0.8)
                time.sleep(0.2)
            else:
                raise tiles.Failure(f"{label}: the z marker never disappeared")
            clean, clean_state = clean_frame(session, window,
                                             session.artifacts / f"{label}-clean.png",
                                             live=live, offset=scripted_offset)
            require(clean_state is not None and tracked_entry(clean_state, scripted_offset) is None,
                    f"{label}: the clean z frame was taken with the scripted marker still present")
            aged_blob = changed_blob_region(
                clean, aged.frame,
                *marker_tile_rect(aged.frame, aged.state,
                                  tracked_pos(aged.state, scripted_offset)))
            require(aged_blob is not None, f"{label}: the aged z marker did not draw over the moved level")
            require(aged_blob.count <= MAX_MARKER_PIXELS,
                    f"{label}: the aged z change covered {aged_blob.count}px, more than one sprite")
            require(aged_blob.count * 2 >= fresh.blob.count,
                    f"{label}: a marker on another z-level must keep its arrow sprite, "
                    f"fresh {fresh.blob.count}px, aged {aged_blob.count}px")
            check_at_tile(aged_blob, aged.frame, aged.state, f"{label} aged above/below",
                          tracked_pos(aged.state, scripted_offset))
            ages = [entry.get("age") for entry in sound_markers(aged.state) or []]
            require(ages and max(ages) < MARKER_TURNS,
                    f"{label}: a marker outlived SOUND_MARKER_TURNS={MARKER_TURNS}: {ages}")
            observations = {
                "dz": dz,
                "scene_z": SCENE_Z,
                "player_z": player_z,
                "marker_z": marker_z,
                "fresh": fresh.blob.summary(),
                "aged": aged_blob.summary(),
                "age": ages[0] if ages else None,
                "fresh_png": fresh.png.name,
                "aged_png": aged.png.name,
                "arrow_asset_identity": "not asserted: ^/v sprites are only distinguished by z relation",
            }
        finally:
            x11.close()
    return observations


def case_sound_markers(session):
    require(session.world is not None, "the sound marker fixture world was not built")
    observations = {}
    observations["aging"] = run_activity_scene(session, "sound-marker-aging", glyph_aging=True, pacing=True)
    observations["aging_off"] = run_activity_scene(session, "sound-marker-aging-off", glyph_aging=False, pacing=False)
    observations["default"] = run_activity_scene(session, "sound-marker-default", glyph_aging=True, pacing=False)
    observations["lifetime"] = run_lifetime_scene(session, "sound-marker-lifetime")
    observations["z_above"] = run_z_scene(session, "sound-marker-above", Z_ABOVE_MOD_ID, -1)
    observations["z_below"] = run_z_scene(session, "sound-marker-below", Z_BELOW_MOD_ID, 1)
    (session.artifacts / "observations.json").write_text(json.dumps(observations, indent=2))
    return [], observations
