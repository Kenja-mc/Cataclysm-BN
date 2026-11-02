import json
import sqlite3
import subprocess
import zlib
from pathlib import Path

from driving_dashboard import clear_driving_arena
from helpers import HELPERS, arena, settle
from numbered_menu_cases import bind_keys, read_player, save_and_quit, save_file
from tmux_game import Game, start_new_game
from vehicle_box import spawn_vehicle, take_control


def saved_driver(world: Path, player: dict) -> dict:
    import tiles

    maps = {str(path.relative_to(world)): path.read_bytes() for path in world.rglob("*.map")}
    database = world / "map.sqlite3"
    if database.exists():
        with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
            for path, data, compression in connection.execute(
                    "SELECT path, data, compression FROM files WHERE path LIKE 'maps/%.map'"):
                maps[path] = zlib.decompress(data) if compression == "zlib" else bytes(data)
    found = []
    for path, data in maps.items():
        for submap in json.loads(data):
            for vehicle in submap.get("vehicles", []):
                if vehicle["type"] == "car" and any(
                        part.get("passenger_id") == player["id"] for part in vehicle["parts"]):
                    sx, sy, sz = submap["coordinates"]
                    found.append({
                        "map": path,
                        "origin": [sx * 12 + vehicle["posx"], sy * 12 + vehicle["posy"], sz],
                        "velocity": vehicle["velocity"],
                        "cruise_velocity": vehicle["cruise_velocity"],
                        "cruise_on": vehicle["cruise_on"],
                        "engine_on": vehicle["engine_on"],
                        "faceDir": vehicle["faceDir"],
                        "player_abs_pos": player["abs_pos"],
                        "controlling_vehicle": player["controlling_vehicle"],
                    })
    tiles.require(len(found) == 1, f"expected one real occupied car, found {found}")
    return found[0]


def build_driving_dashboard_world(session) -> None:
    import tiles

    tiles.tmux_game.ROOT = session.root
    game = Game(name="bn-tiles-dashboard-fixture", userdir=session.curses_userdir,
                layout="fusion", cols=160, rows=45,
                options={"SAFEMODE": "false", "INITIAL_TIME": "12", "CONTROL_SCHEME": "modern",
                         "HUD_WINDOWS": "true", "DRIVING_DASHBOARD": "false", "HUD_ICONS": "ascii",
                         "USE_METRIC_SPEEDS": "mph", "SHOW_WELCOME": "false", "SHOW_TIPS": "false",
                         "ANIMATIONS": "false", "SIDEBAR_POSITION": "right"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        clear_driving_arena(game)
        spawn_vehicle(game)
        take_control(game)
        settle(game)
        tiles.require(game.lua(
            "gapi.get_avatar():set_mutation(MutationBranchId.new('DEBUG_NIGHTVISION')) "
            "gapi.set_omt_weather_override(coords.project_to_omt(gapi.get_avatar():abs_pos()),"
            "3,'clear',nil) out('ok')") == ["ok"], "could not pin fixture light/weather")
        tiles.require(game.lua("out(gdebug.save_game())") == ["true"], "dashboard fixture save failed")
        (session.artifacts / "dashboard-fixture-curses.txt").write_text(game.screen_colors())
        bind_keys(session, {"DEFAULTMODE": {"save": "F6"}})
    finally:
        subprocess.run(["tmux", "kill-session", "-t", game.name],
                       stderr=subprocess.DEVNULL, check=False)
    saves = [path for path in (session.curses_userdir / "save").iterdir() if path.is_dir()]
    tiles.require(len(saves) == 1, f"expected one dashboard world, found {saves}")
    session.world = saves[0].name
    characters = list(saves[0].glob("*.sav"))
    tiles.require(len(characters) == 1, f"expected one fixture character, found {characters}")
    state = saved_driver(saves[0], read_player(characters[0]))
    tiles.require(state["velocity"] == 0 and state["engine_on"] and state["controlling_vehicle"],
                  f"fixture must be stationary with actual engine/control active: {state}")
    (session.artifacts / "dashboard-fixture-state.json").write_text(json.dumps(state, indent=2))


def _region_bytes(frame: tuple, rect: tuple[int, int, int, int]) -> bytes:
    width, height, rgb = frame
    left, top, right, bottom = rect
    assert 0 <= left < right <= width and 0 <= top < bottom <= height, (rect, width, height)
    return b"".join(rgb[3 * (y * width + left):3 * (y * width + right)]
                    for y in range(top, bottom))


def _changed_bounds(first: tuple, second: tuple) -> tuple[int, int, int, int]:
    import tiles

    tiles.require(first[:2] == second[:2], "dashboard must not resize the native window")
    width, height, off = first
    on = second[2]
    left, top, right, bottom = width, height, -1, -1
    for y in range(height):
        for x in range(width):
            offset = 3 * (y * width + x)
            if off[offset:offset + 3] != on[offset:offset + 3]:
                left, top, right, bottom = min(left, x), min(top, y), max(right, x), max(bottom, y)
    tiles.require(right >= left, "dashboard on must visibly expand the compact instruments")
    return left, top, right + 1, bottom + 1


def case_driving_dashboard(session) -> tuple[list[str], dict]:
    import tiles

    base = {"CONTROL_SCHEME": "modern", "HUD_WINDOWS": "true", "HUD_ICONS": "ascii",
            "FONT_WIDTH": "8", "FONT_HEIGHT": "16", "FONT_SIZE": "16",
            "USE_METRIC_SPEEDS": "mph", "SIDEBAR_POSITION": "right",
            "MOUSE_MOVE": "false", "MOUSE_TILE_SELECTION": "false", "CURSOR_PANNING": "false",
            "PIXEL_MINIMAP": "false", "ANIMATIONS": "false", "SHOW_TIPS": "false",
            "HUD_VEHICLE_BOX": "bottom_right", "TILES": "UNDEAD_PEOPLE_BASE"}
    observations = {}
    checks = []
    for layout, columns, rows in (("fusion", 160, 45), ("labels", 80, 25), ("fusion", 80, 25)):
        panels = session.curses_userdir / "config" / "panel_options.json"
        panels.write_text(json.dumps([{"current_layout_id": layout, "layouts": []}]))
        for scale in ((1,) if columns >= 140 else (1, 2)):
            group = f"dashboard-{layout}-{columns}x{rows}-{scale}x"
            captures, states, traces, frames = {}, {}, {}, {}
            for enabled in (False, True):
                mode = "on" if enabled else "off"
                label = f"{group}-{mode}"
                options = {**base, "SCALING_FACTOR": str(scale),
                           "TERMINAL_X": str(columns * scale), "TERMINAL_Y": str(rows * scale),
                           "DRIVING_DASHBOARD": str(enabled).lower()}
                trace = []
                with session.running_game(label, options) as live:
                    x11 = tiles.X11(session.display)
                    try:
                        window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
                        tiles.require(window is not None, f"{label}: window disappeared")
                        width, height, _ = tiles.frame_rgb(live.frame)
                        tiles.require((width, height) == (columns * 8 * scale, rows * 16 * scale),
                                      f"{label}: requested logical dimensions/scaling were not applied")
                        x11.focus_local(window, width - 8, height - 8)
                        shots = {}
                        phase_frames = {}
                        for phase in ("parked", "driving"):
                            if phase == "driving":
                                for key in ("w", "x", "w", "x"):
                                    trace.append({"key": key, "delay": 0.6})
                                    x11.key(key, delay=0.6)
                            path = session.artifacts / f"{label}-{phase}.png"
                            phase_frames[phase] = tiles.settle_capture(session, x11, window, path)
                            shots[phase] = str(path)
                        save = save_file(live, session.world)
                        trace += [{"key": "F6", "delay": 0.7}, {"key": "Left", "delay": 0.3},
                                  {"key": "Return", "delay": 0.8}]
                        save_and_quit(x11, save)
                        state = saved_driver(save.parent, read_player(save))
                        (session.artifacts / f"{label}-saved-state.json").write_text(json.dumps(state, indent=2))
                        captures[mode], states[mode], frames[mode] = shots, state, phase_frames
                        traces[mode] = trace
                    finally:
                        (session.artifacts / f"{label}-input-trace.json").write_text(json.dumps(trace, indent=2))
                        x11.close()
            cell_width, cell_height = 8 * scale, 16 * scale
            width, height = columns * cell_width, rows * cell_height
            terrain_width = (columns - 44) * cell_width
            pitch = 32 * scale
            avatar_x = terrain_width // pitch // 2 * pitch
            avatar_y = height // pitch // 2 * pitch
            avatar = (avatar_x, avatar_y, avatar_x + pitch, avatar_y + pitch)
            sidebar = (terrain_width, 0, width, height)
            protected = {"avatar": avatar, "vitals/right sidebar": sidebar}
            changes = {}
            for phase in ("parked", "driving"):
                off, on = frames["off"][phase], frames["on"][phase]
                bounds = _changed_bounds(off, on)
                changes[phase] = bounds
                if phase == "parked":
                    checks.append(tiles.Check(f"{group} {phase}: instruments fit beside right sidebar",
                                              bounds[2] <= terrain_width,
                                              f"changed bounds={bounds}, terrain right={terrain_width}"))
                for name, rect in protected.items():
                    checks.append(tiles.Check(f"{group} {phase}: {name} remains unobscured",
                                              _region_bytes(off, rect) == _region_bytes(on, rect),
                                              f"protected native rectangle={rect}"))
                if phase == "parked" and layout == "fusion" and columns >= 140:
                    checks.append(tiles.Check(f"{group} {phase}: reuse Fusion vehicle card",
                                              bounds[0] < 32 * cell_width and bounds[2] <= 32 * cell_width,
                                              f"changed bounds={bounds}"))
            for mode, state in states.items():
                checks.append(tiles.Check(f"{group} {mode}: real throttle drives the vehicle",
                                          state["velocity"] > 0 and state["cruise_velocity"] > 0
                                          and state["engine_on"] and state["controlling_vehicle"],
                                          str(state)))
            checks.append(tiles.Check(f"{group}: identical input and game state with option off/on",
                                      traces["off"] == traces["on"] and states["off"] == states["on"],
                                      f"off={states['off']}, on={states['on']}"))
            observations[group] = {"layout": layout, "visible_cells": [columns, rows], "scale": scale,
                                   "captures": captures, "states": states, "changed_bounds": changes,
                                   "protected_regions": protected, "input_traces": traces}
    observations["checks"] = [check.__dict__ for check in checks]
    return [f"{check.name}: {check.detail}" for check in checks if not check.ok], observations
