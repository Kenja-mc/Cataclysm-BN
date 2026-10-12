#!/usr/bin/env python3
"""Real native rendering E2Es. Run from the integrated tree alongside current tiles.py.

python3 tests/e2e/rendering.py --out /tmp/bn-render-proof
Captures, fixture sight answers, sprite matches and whole-frame differences remain in --out.
"""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

import tiles
import tmux_game
from helpers import HELPERS, arena, settle
from tmux_game import Game, start_new_game
from tiles import Failure, Session, X11, capture, frame_rgb, require

OFF = {name: "false" for name in (
    "ITEM_LAYERING", "CLIFF_SHADING", "DIRECTIONAL_STAIRS", "ITEM_THUMBNAILS")}
OFF["TILES"] = "UNDEAD_PEOPLE_BASE"
TABLES = {(-4, -6), (-1, -6), (-2, -4)}
CLIFF_EDGES = ({(3, y) for y in range(4, 7)} | {(6, y) for y in range(4, 7)} |
               {(x, 3) for x in (4, 5)} | {(x, 7) for x in (4, 5)})
ROTATED_STAIRS = {(-8, 6), (7, 7), (-3, 9), (9, -7)}
SPRITES = ("rock", "ruby_gold_ring", "corpse_mon_zombie")

FIXTURE_LUA = """
function render_clean()
    for dx=-12,12 do for dy=-12,12 do
        local p=here(dx,dy)
        local border=math.abs(dx)==12 or math.abs(dy)==12
        M:set_ter_at(p,TerId.new(border and 't_wall' or 't_pavement'):int_id())
        M:set_furn_at(p,FurnId.new('f_null'):int_id())
        M:clear_items_at(p)
        local above=TripointBubMs.new(p.x,p.y,p.z+1)
        M:set_furn_at(above,FurnId.new('f_null'):int_id())
        M:clear_items_at(above)
        M:set_ter_at(above,TerId.new('t_open_air'):int_id())
        local below=TripointBubMs.new(p.x,p.y,p.z-1)
        M:set_ter_at(below,TerId.new('t_pavement'):int_id())
        M:set_furn_at(below,FurnId.new('f_null'):int_id())
        M:clear_items_at(below)
    end end
    out('clean')
end
---@class RenderOffset
---@field x integer
---@field y integer
---@param center RenderOffset
---@param opening RenderOffset
function render_stair(center,opening)
    for _,d in ipairs({{0,1},{1,0},{-1,0},{0,-1}}) do
        local open=d[1]==opening.x and d[2]==opening.y
        M:set_ter_at(here(center.x+d[1],center.y+d[2]),
                    TerId.new(open and 't_pavement' or 't_wall'):int_id())
    end
    M:set_ter_at(here(center.x,center.y),TerId.new('t_stairs_down'):int_id())
end
function render_geometry()
    for dy=-4,2 do for _,dx in ipairs({-6,6}) do
        M:set_ter_at(here(dx,dy),TerId.new('t_wall'):int_id())
    end end
    for dx=4,5 do for dy=4,6 do
        M:set_ter_at(here(dx,dy),TerId.new('t_open_air'):int_id())
    end end
    M:set_ter_at(here(-7,0),TerId.new('t_open_air'):int_id())
    render_stair({x=-8,y=6},{x=1,y=0})
    render_stair({x=7,y=7},{x=-1,y=0})
    render_stair({x=-3,y=9},{x=0,y=-1})
    render_stair({x=0,y=-9},{x=0,y=1})
    render_stair({x=9,y=-7},{x=-1,y=0})
    M:set_ter_at(here(9,-6),TerId.new('t_pavement'):int_id())
    for _,d in ipairs({{-4,-6},{-1,-6},{-2,-4}}) do
        M:set_furn_at(here(d[1],d[2]),FurnId.new('f_table'):int_id())
        M:create_item_at(here(d[1],d[2]),ItypeId.new('rock'),-1)
    end
    M:create_item_at(here(2,-6),ItypeId.new('rock'),-1)
    out('geometry')
end
function render_inventory()
    local u=gapi.get_avatar()
    u:clear_bionics()
    u:clear_mutations()
    u:set_mutation(MutationBranchId.new('DEBUG_STORAGE'))
    u:create_item(ItypeId.new('rock'),-1)
    local ring=gapi.create_item(ItypeId.new('jewelry_ring'),-1)
    ring:set_var_str('variant','ruby_gold_ring')
    u:add_item(ring)
    M:create_corpse_at(here(0,0),MonsterTypeId.new('mon_zombie'))
    local corpse=M:get_items_at(here(0,0))[1]
    u:add_item(M:detach_item_at(here(0,0),corpse))
    M:create_corpse_at(here(0,0),MonsterTypeId.new('mon_zombie'))
    M:create_item_at(here(0,0),ItypeId.new('rock'),-1)
    local ground_ring=gapi.create_item(ItypeId.new('jewelry_ring'),-1)
    ground_ring:set_var_str('variant','ruby_gold_ring')
    M:add_item(here(0,0),ground_ring)
    out('inventory')
end
function render_sight()
    local a=gapi.get_avatar()
    out(a:sees(here(-6,0)),a:sees(here(-7,0)))
    out(a:sees(here(9,-7)),a:sees(here(8,-7)),a:sees(here(9,-6)))
    out(a:sees(here(-8,6)),a:sees(here(7,7)),a:sees(here(-3,9)),a:sees(here(0,-9)))
end
"""


class RenderSession(Session):
    def build_world(self):
        tmux_game.ROOT = self.root
        game = Game(name="bn-render-fixture", options={"SAFEMODE": "false", "INITIAL_TIME": "12"},
                    userdir=self.curses_userdir)
        try:
            start_new_game(game)
            console_source = " ".join(line for line in FIXTURE_LUA.splitlines()
                                      if not line.lstrip().startswith("---@"))
            game.define_lua(HELPERS + console_source)
            arena(game)
            require(game.lua("render_clean()") == ["clean"], game.screen())
            settle(game)
            require(game.lua("render_clean()") == ["clean"], game.screen())
            require(game.lua("render_geometry()") == ["geometry"], game.screen())
            require(game.lua("render_inventory()") == ["inventory"], game.screen())
            settle(game)
            sight = game.lua("render_sight()")
            (self.artifacts / "fixture-sight.json").write_text(json.dumps(sight))
            require(sight == ["true,false", "true,true,false", "true,true,true,true"],
                    f"fixture must expose ledges/visible openings but hide occluded openings: {sight}")
            require(game.lua("out(gdebug.save_game())") == ["true"], game.screen())
            (self.artifacts / "fixture-curses.ansi").write_text(game.screen_colors())
        finally:
            subprocess.run(["tmux", "kill-session", "-t", game.name], check=False,
                           stderr=subprocess.DEVNULL)
        saves = [p for p in (self.curses_userdir / "save").iterdir() if p.is_dir()]
        require(len(saves) == 1, f"one saved fixture required: {saves}")
        self.world = saves[0].name

    def launch_keyed(self, label, options, keys):
        with self.running_game(label, options) as live:
            baseline = frame_rgb(live.frame)
            x11 = X11(self.display)
            try:
                window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
                require(window is not None, "running game window disappeared")
                x11.focus(window, 0, 0)
                for key in keys:
                    x11.key(key)
                previous = None
                deadline = time.monotonic() + self.timeout
                while time.monotonic() < deadline:
                    require(live.proc.poll() is None, "game exited during real menu input")
                    shot = capture(self.display, window, live.run / "menu.png")
                    current = frame_rgb(shot)
                    if current == previous and current != baseline:
                        kept = self.artifacts / f"{label}.png"
                        shutil.copy(shot, kept)
                        return kept
                    previous = current
                    time.sleep(0.5)
                raise Failure(f"{label}: menu did not reach a stable drawn frame")
            finally:
                x11.close()


def changed_pixels(off, on):
    require(off[:2] == on[:2], "option changed the capture dimensions")
    return [i for i in range(off[0] * off[1])
            if off[2][3*i:3*i+3] != on[2][3*i:3*i+3]]


def world_grid(frame, root):
    info = json.loads((root / "gfx/MSX++UnDeadPeopleEdition/tile_config.json").read_text())["tile_info"][0]
    tx, ty = info["width"], info["height"]
    width, height = frame[:2]
    # The saved classic sidebar uses 44 terminal cells. Native view counts round up partial tiles.
    map_width = width - 44 * (width // 132)
    return {"ox": math.ceil(map_width / tx) // 2 * tx,
            "oy": math.ceil(height / ty) // 2 * ty, "tx": tx, "ty": ty}


def check_world_feature(session, baseline, feature, expected, grid):
    image = session.launch(feature.lower(), {**OFF, feature: "true"})
    on = frame_rgb(image)
    changed = changed_pixels(baseline, on)
    cells = {((i % on[0] - grid["ox"]) // grid["tx"],
              (i // on[0] - grid["oy"]) // grid["ty"]) for i in changed}
    (session.artifacts / f"{feature.lower()}-cells.json").write_text(json.dumps(sorted(cells)))
    require(cells == expected, f"{feature}: changed cells {sorted(cells)}, expected {sorted(expected)}")
    if feature == "CLIFF_SHADING":
        require(all(all(on[2][3*i+c] <= baseline[2][3*i+c] for c in range(3)) for i in changed),
                "cliff shading must only darken the ten visible perimeter cells")
        require(all(max(on[2][3*i:3*i+3]) > 0 for i in changed
                    if max(baseline[2][3*i:3*i+3]) >= 16),
                "cliff shading must leave the lit ground texture visible")
    return {"feature": feature, "changed_pixels": len(changed), "cells": sorted(cells)}


def sprite_template(root, name, size):
    folder = root / "gfx/MSX++UnDeadPeopleEdition"
    config = json.loads((folder / "tile_config.json").read_text())
    info = config["tile_info"][0]
    offset = 0
    for sheet in config["tiles-new"]:
        sw = sheet.get("sprite_width", info["width"])
        sh = sheet.get("sprite_height", info["height"])
        atlas = folder / sheet["file"]
        dimensions = subprocess.run(["magick", "identify", "-format", "%w %h", str(atlas)],
                                    check=True, capture_output=True, text=True).stdout.split()
        columns, rows = int(dimensions[0]) // sw, int(dimensions[1]) // sh
        for tile in sheet.get("tiles", []):
            ids = tile["id"] if isinstance(tile["id"], list) else [tile["id"]]
            if name not in ids:
                continue
            local = tile["fg"] - offset
            require(0 <= local < columns * rows, f"{name}: sprite lies outside its atlas")
            x, y = local % columns * sw, local // columns * sh
            pixels = subprocess.run([
                "magick", str(atlas), "-crop", f"{sw}x{sh}+{x}+{y}", "+repage", "-filter", "point",
                "-resize", f"{size[0]}x{size[1]}!", "-depth", "8", "rgba:-"],
                check=True, capture_output=True).stdout
            return size[0], size[1], pixels
        offset += columns * rows
    raise Failure(f"fixture artwork {name} is missing from the selected tileset")


def template_positions(frame, template):
    width, height, data = frame
    tw, th, pixels = template
    colors = [pixels[i:i+4] for i in range(0, len(pixels), 4)]
    opaque = [i for i, color in enumerate(colors) if color[3] == 255]
    anchor = next(i for i in opaque if colors[i][:3] != b"\0\0\0")
    ax, ay = anchor % tw, anchor // tw
    found = []
    for match in re.finditer(b"(?=" + re.escape(colors[anchor][:3]) + b")", data):
        if match.start() % 3:
            continue
        p = match.start() // 3
        x, y = p % width - ax, p // width - ay
        if not (0 <= x <= width-tw and 0 <= y <= height-th):
            continue
        if all(data[3*((y+i//tw)*width+x+i%tw):3*((y+i//tw)*width+x+i%tw)+3] == colors[i][:3]
               for i in opaque):
            found.append((x, y))
    return found


def check_thumbnails(session):
    evidence = []
    for menu, keys in (("inventory", ["i"]), ("pickup", ["i", "Escape", "g"])):
        off = frame_rgb(session.launch_keyed(menu + "-off", OFF, keys))
        on = frame_rgb(session.launch_keyed(menu + "-on", {**OFF, "ITEM_THUMBNAILS": "true"}, keys))
        size = (2 * on[0] // 132, on[1] // 60)
        positions = {}
        for name in SPRITES:
            template = sprite_template(session.root, name, size)
            matches = template_positions(on, template)
            require(matches and not template_positions(off, template),
                    f"{menu}: native {name} artwork must appear only with thumbnails enabled")
            positions[name] = matches
        columns = set.intersection(*(set(x for x, _ in positions[name]) for name in SPRITES))
        require(columns, f"{menu}: ordinary, variant and corpse sprites must occupy the same row gutter")
        evidence.append({"menu": menu, "sprite_positions": positions})
    filtered = frame_rgb(session.launch_keyed("inventory-filtered", {**OFF, "ITEM_THUMBNAILS": "true"},
                                            ["i", "slash", "r", "o", "c", "k", "Return"]))
    size = (2 * filtered[0] // 132, filtered[1] // 60)
    require(template_positions(filtered, sprite_template(session.root, "rock", size)),
            "filtered inventory must keep the actual rock sprite")
    for name in SPRITES[1:]:
        require(not template_positions(filtered, sprite_template(session.root, name, size)),
                f"filtered inventory retained a stale {name} overlay")
    return {"feature": "ITEM_THUMBNAILS", "menus": evidence, "filtered_stale_sprites": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(tiles.ROOT))
    parser.add_argument("--binary")
    parser.add_argument("--vk-icd")
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--out", default="/tmp/bn-render-proof")
    args = parser.parse_args()
    artifacts = Path(args.out)
    artifacts.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="bn-render-work-"))
    session = RenderSession(args, work, artifacts)
    checks, failures = [], []
    try:
        session.start()
        session.build_world()
        baseline = frame_rgb(session.launch("baseline", OFF))
        grid = world_grid(baseline, session.root)
        (artifacts / "grid.json").write_text(json.dumps(grid))
        for feature, expected in (("ITEM_LAYERING", TABLES), ("CLIFF_SHADING", CLIFF_EDGES),
                                  ("DIRECTIONAL_STAIRS", ROTATED_STAIRS)):
            checks.append(check_world_feature(session, baseline, feature, expected, grid))
        checks.append(check_thumbnails(session))
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
        (artifacts / "exception.txt").write_text(traceback.format_exc())
    finally:
        session.close()
    if failures:
        shutil.move(str(work), str(artifacts / "work"))
    else:
        shutil.rmtree(work)
    (artifacts / "result.json").write_text(json.dumps({"passed": not failures, "checks": checks,
                                                     "failures": failures}, indent=2))
    for failure in failures:
        print("FAIL", failure)
    print("FAILED" if failures else "PASS", "native rendering:", artifacts)
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
