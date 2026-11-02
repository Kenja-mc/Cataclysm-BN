import json
import shutil
import sqlite3
import subprocess
import zlib

from helpers import HELPERS, arena, settle


CHAIRS = {"diagonal": (-4, -4, 45), "cardinal": (4, -4, 0)}
TILESET = "MSX++UnDeadPeopleEdition"


def _spawn_chair(game, heading):
    import tiles

    tiles.require(game.lua("rotation_spawn=gapi.get_avatar():abs_pos() out('ok')") == ["ok"],
                  "could not remember chair origin")
    game.keys("F12", delay=0.6)
    game.wait_for("Debug Functions")
    game.keys("s", delay=0.3)
    game.wait_for("Spawn a vehicle")
    game.keys("v", delay=0.3)
    game.wait_for("Choose vehicle to spawn")
    game.keys("/", delay=0.4)
    game.type("(swivel_chair)")
    game.keys("Enter", "Enter", delay=0.6)
    game.wait_for("Vehicle condition")
    game.keys("Down", "Enter", delay=0.6)
    game.wait_for("Vehicle direction")
    game.keys("Enter", delay=0.8)
    game.keys("h", delay=0.6)
    tiles.require(game.lua(
        "local p=gapi.get_avatar():abs_pos() "
        "out(p.x==rotation_spawn.x-1 and p.y==rotation_spawn.y and p.z==rotation_spawn.z)")
        == ["true"], "avatar did not leave the spawned chair to the west:\n" + game.screen())
    tiles.require(game.lua(
        f"out(M:replace_vehicle(M:abs_to_bub(rotation_spawn),'swivel_chair',"
        f"{{orientation={heading},status=0,locks=false}}))") == ["true"],
        "real vehicle replacement failed:\n" + game.screen())


def _saved_chairs(world, avatar, artifacts):
    import tiles

    maps = {str(path.relative_to(world)): path.read_bytes() for path in world.rglob("*.map")}
    db = world / "map.sqlite3"
    if db.exists():
        with sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True) as connection:
            for path, data, compression in connection.execute(
                    "SELECT path, data, compression FROM files WHERE path LIKE 'maps/%.map'"):
                maps[path] = zlib.decompress(data) if compression == "zlib" else bytes(data)
    found, sources = {}, {}
    for path, data in maps.items():
        for submap in json.loads(data):
            sx, sy, sz = submap["coordinates"]
            for vehicle in submap.get("vehicles", []):
                if vehicle["type"] != "swivel_chair":
                    continue
                offset = (sx * 12 + vehicle["posx"] - avatar[0],
                          sy * 12 + vehicle["posy"] - avatar[1], sz - avatar[2])
                for name, (dx, dy, heading) in CHAIRS.items():
                    if offset != (dx, dy, 0):
                        continue
                    tiles.require(name not in found, f"duplicate {name} chair in saved map")
                    tiles.require(vehicle["faceDir"] == heading,
                                  f"{name}: saved facing {vehicle['faceDir']} != {heading}")
                    tiles.require(vehicle["velocity"] == 0 and not vehicle["engine_on"],
                                  f"{name}: chair is not stationary with engine off")
                    tiles.require({part["id"] for part in vehicle["parts"]}
                                  == {"xlframe_vertical_2", "wheel_caster", "seat"},
                                  f"{name}: unexpected saved vehicle parts")
                    found[name] = {"offset": offset, "heading": heading, "vehicle": vehicle}
                    sources[path] = json.loads(data)
    (artifacts / "vehicle-rotation-saved-submaps.json").write_text(json.dumps(sources, indent=2))
    (artifacts / "vehicle-rotation-fixture.json").write_text(json.dumps(found, indent=2))
    tiles.require(set(found) == set(CHAIRS), f"saved fixture chairs missing: {set(CHAIRS) - set(found)}")
    return found


def build_vehicle_rotation_world(session):
    import tiles

    tiles.tmux_game.ROOT = session.root
    game = tiles.Game(name="bn-tiles-e2e-vehicle-rotation", userdir=session.curses_userdir,
                      options={"SAFEMODE": "false", "INITIAL_TIME": "12",
                               "CONTROL_SCHEME": "classic", "ANIMATIONS": "false"})
    try:
        tiles.start_new_game(game)
        game.define_lua(HELPERS + " "
            "function rotation_clear() for dx=-13,13 do for dy=-13,13 do local p=here(dx,dy) "
            "M:set_ter_at(p,TerId.new('t_floor'):int_id()) "
            "M:set_furn_at(p,FurnId.new('f_null'):int_id()) M:clear_items_at(p) M:remove_trap_at(p) "
            "for _,f in ipairs(M:get_field_ids_at(p)) do M:remove_field_at(p,f) end "
            "local above=TripointBubMs.new(p.x,p.y,p.z+1) "
            "M:set_ter_at(above,TerId.new('t_open_air'):int_id()) "
            "M:set_furn_at(above,FurnId.new('f_null'):int_id()) "
            "local cr=gapi.get_creature_at(p) if cr and not cr:is_avatar() then park(cr) end "
            "end end out('clear') end")
        arena(game)
        tiles.require(game.lua(
            "gapi.get_avatar():set_mutation(MutationBranchId.new('DEBUG_NIGHTVISION')) "
            "out(gapi.get_avatar():has_trait(MutationBranchId.new('DEBUG_NIGHTVISION')))")
            == ["true"], "could not pin fixture sight across save/reload")
        tiles.require(game.lua("rotation_clear()") == ["clear"], "courtyard setup failed")
        settle(game)
        tiles.require(game.lua("rotation_clear() rotation_origin=gapi.get_avatar():abs_pos() "
                               "gapi.set_omt_weather_override("
                               "coords.project_to_omt(gapi.get_avatar():abs_pos()),3,'clear',nil)")
                      == ["clear"], "final courtyard/weather setup failed")
        _spawn_chair(game, 45)
        tiles.require(game.lua("gapi.get_avatar():set_pos(TripointAbsMs.new("
                               "rotation_origin.x+8,rotation_origin.y,rotation_origin.z)) out('ok')")
                      == ["ok"], "could not reach cardinal spawn origin")
        _spawn_chair(game, 0)
        tiles.require(game.lua("gapi.get_avatar():set_pos(TripointAbsMs.new("
                               "rotation_origin.x+4,rotation_origin.y+4,rotation_origin.z)) out('ok')")
                      == ["ok"], "could not reach the observation tile")
        settle(game)
        positions = game.lua(
            "local a=gapi.get_avatar():abs_pos() out('avatar',a.x,a.y,a.z) "
            "for _,v in ipairs(M:get_vehicles()) do if v:type()=='swivel_chair' then "
            "local p=M:bub_to_abs(v:pos()) out('chair',p.x,p.y,p.z) end end")
        (session.artifacts / "vehicle-rotation-positions.json").write_text(json.dumps(positions, indent=2))
        proof = game.lua(
            "local a=gapi.get_avatar() "
            "out(a:sees(here(-4,-4)),a:sees(here(4,-4)),"
            "M:has_vehicle_part_with_feature_at(here(-4,-4),'BOARDABLE'),"
            "M:has_vehicle_part_with_feature_at(here(4,-4),'BOARDABLE')) "
            "out(gapi.current_turn():hour_of_day(),gapi.get_omt_weather_override("
            "coords.project_to_omt(a:abs_pos())))")
        (session.artifacts / "vehicle-rotation-sight-weather.json").write_text(json.dumps(proof, indent=2))
        avatar = tuple(int(value) for value in game.lua("pos()")[0].split(","))
        tiles.require(game.lua("out(gdebug.save_game())") == ["true"], "saving rotation fixture failed")
        (session.artifacts / "vehicle-rotation-curses.txt").write_text(game.screen_colors())
        tiles.require(proof == ["true,true,true,true", "12,clear"],
                      f"chairs must be visible/boardable at noon in clear weather: {proof}")
    finally:
        subprocess.run(["tmux", "kill-session", "-t", game.name],
                       stderr=subprocess.DEVNULL, check=False)
    saves = [path for path in (session.curses_userdir / "save").iterdir() if path.is_dir()]
    tiles.require(len(saves) == 1, f"expected one saved world, found {saves}")
    session.world = saves[0].name
    _saved_chairs(saves[0], avatar, session.artifacts)


def _keep_sprite_source(session):
    import tiles

    directory = session.root / "gfx" / TILESET
    config = json.loads((directory / "tile_config.json").read_text())
    tiles.require(config["tile_info"][0]["width"] == 32
                  and config["tile_info"][0]["height"] == 32
                  and not config["tile_info"][0].get("iso", False),
                  "rotation case requires the pinned 32px non-isometric tileset")
    matches = [(atlas, tile) for atlas in config["tiles-new"] for tile in atlas.get("tiles", [])
               if tile["id"] == "vp_seat"]
    tiles.require(len(matches) == 1, "pinned tileset must define vp_seat exactly once")
    atlas, seat = matches[0]
    tiles.require(seat.get("rotates") is True and type(seat.get("fg")) is int
                  and type(seat.get("bg")) is int,
                  f"vp_seat must have single-sprite rotating foreground/background, got {seat}")
    shutil.copy(directory / atlas["file"], session.artifacts / ("source-" + atlas["file"]))
    shutil.copy(directory / "tile_config.json", session.artifacts / "source-tile_config.json")
    metadata = {"tileset": "UNDEAD_PEOPLE_BASE", "atlas": atlas["file"], "seat": seat,
                "tile_info": config["tile_info"]}
    (session.artifacts / "vehicle-rotation-sprite-source.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def case_vehicle_rotation(session):
    import tiles

    source = _keep_sprite_source(session)
    options = {
        "CONTROL_SCHEME": "classic", "SCALING_FACTOR": "1", "FONT_WIDTH": "8",
        "FONT_HEIGHT": "16", "FONT_SIZE": "16", "TERMINAL_X": "160", "TERMINAL_Y": "60",
        "TILES": "UNDEAD_PEOPLE_BASE", "SIDEBAR_POSITION": "right", "HUD_WINDOWS": "false",
        "PIXEL_MINIMAP": "false", "MOUSE_MOVE": "false", "MOUSE_TILE_SELECTION": "false",
        "CURSOR_PANNING": "false",
    }
    frames, pngs = {}, {}
    for enabled in (False, True):
        label = "vehicle-rotation-" + ("on" if enabled else "off")
        with session.running_game(label, {**options, "VEHICLE_SMOOTH_ROTATION": str(enabled).lower()}) as live:
            x11 = tiles.X11(session.display)
            try:
                window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
                tiles.require(window is not None, "rotation case: native window disappeared")
                x11.focus_local(window, 1272, 952)
                pngs[enabled] = session.artifacts / f"{label}.png"
                frames[enabled] = tiles.settle_capture(session, x11, window, pngs[enabled])
            finally:
                x11.close()
    tiles.require(frames[False][:2] == frames[True][:2] == (1280, 960),
                  "rotation case requires the pinned 1280x960 native window")
    pitch = 32
    terrain_width = 1280 - tiles.ZOOM_SIDEBAR_CELLS * tiles.ZOOM_FONT_WIDTH
    ox = terrain_width // pitch // 2 * pitch
    oy = 960 // pitch // 2 * pitch

    def region(dx, dy):
        return {"x0": ox + (dx - 1) * pitch, "y0": oy + (dy - 1) * pitch,
                "w": 3 * pitch, "h": 3 * pitch}

    regions = {name: region(dx, dy) for name, (dx, dy, _) in CHAIRS.items()}
    regions["empty_floor"] = region(0, -4)
    changed, off_regions = {}, {}
    off, on = frames[False][2], frames[True][2]
    for name, rect in regions.items():
        x0, y0, width, height = (rect[key] for key in ("x0", "y0", "w", "h"))
        tiles.require(0 <= x0 < x0 + width <= terrain_width and 0 <= y0 < y0 + height <= 960,
                      f"{name}: verification region is outside the terrain")
        off_regions[name] = b"".join(
            off[3 * (y * 1280 + x0):3 * (y * 1280 + x0 + width)]
            for y in range(y0, y0 + height))
        changed[name] = sum(off[p:p + 3] != on[p:p + 3]
                            for y in range(y0, y0 + height) for x in range(x0, x0 + width)
                            for p in [3 * (y * 1280 + x)])
        for enabled in (False, True):
            tiles.crop_to(pngs[enabled], rect,
                          session.artifacts / f"vehicle-rotation-{name}-{'on' if enabled else 'off'}.png",
                          margin=0)
    diagonal = regions["diagonal"]
    outside = sum(off[p:p + 3] != on[p:p + 3]
                  for y in range(960) for x in range(terrain_width)
                  if not (diagonal["x0"] <= x < diagonal["x0"] + diagonal["w"]
                          and diagonal["y0"] <= y < diagonal["y0"] + diagonal["h"])
                  for p in [3 * (y * 1280 + x)])
    checks = [
        tiles.Check("both measured regions contain visible vehicle sprites",
                    all(off_regions[name] != off_regions["empty_floor"] for name in CHAIRS),
                    "both off-option chair crops must differ from the identical empty floor"),
        tiles.Check("45-degree real vehicle sprite changes", changed["diagonal"] > 0,
                    f"{changed['diagonal']} changed pixels in the diagonal chair region"),
        tiles.Check("0-degree real vehicle sprite stays identical", changed["cardinal"] == 0,
                    f"{changed['cardinal']} changed pixels in the cardinal chair region"),
        tiles.Check("empty floor stays identical", changed["empty_floor"] == 0,
                    f"{changed['empty_floor']} changed pixels in the empty floor control"),
        tiles.Check("terrain changes are confined to the diagonal vehicle", outside == 0,
                    f"{outside} changed terrain pixels outside the diagonal chair region"),
    ]
    return ([f"{check.name}: {check.detail}" for check in checks if not check.ok],
            {"regions": regions, "tile_pitch": pitch, "avatar_tile_top_left": [ox, oy],
             "changed_pixels": changed, "outside_diagonal_changed_pixels": outside,
             "source": source, "options": options,
             "checks": [check.__dict__ for check in checks]})
