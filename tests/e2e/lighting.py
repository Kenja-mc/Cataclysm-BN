#!/usr/bin/env python3
"""Check real lamp hues and the colored-lighting toggle on CPU and software GPU.

python3 tests/e2e/lighting.py --out /tmp/bn-lighting-proof
Each lamp has its own saved darkroom, so other lamps and sidebar colors cannot satisfy a check.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import tiles
import tmux_game
from helpers import HELPERS, arena, settle
from rendering import world_grid
from tmux_game import Game, start_new_game
from tiles import Session, frame_rgb, require

EMITTERS = {
    "atomic_lamp": "green",
    "glowstick_lit": "blue",
    "candle_lit": "warm",
    "electric_lantern_on": "neutral",
    "oil_lamp_on": "warm",
    "gasoline_lantern_on": "warm",
}
OPTIONS = {"TILES": "UNDEAD_PEOPLE_BASE", "PIXEL_MINIMAP": "false"}
FIXTURE_LUA = """
function lighting_room()
    local a=gapi.get_avatar()
    local pos=a:get_pos_ms()
    a:set_pos_ms(TripointBubMs.new(pos.x,pos.y,-1))
    for dx=-20,20 do for dy=-20,20 do
        local p=here(dx,dy)
        M:set_ter_at(p,TerId.new('t_pavement'):int_id())
        M:set_furn_at(p,FurnId.new('f_null'):int_id())
        M:clear_items_at(p)
        local above=TripointBubMs.new(p.x,p.y,0)
        M:set_ter_at(above,TerId.new('t_rock'):int_id())
        M:set_furn_at(above,FurnId.new('f_null'):int_id())
        M:clear_items_at(above)
    end end
    for dx=-21,21 do for dy=-21,21 do
        if math.abs(dx)==21 or math.abs(dy)==21 then
            M:set_ter_at(here(dx,dy),TerId.new('t_rock'):int_id())
        end
    end end
    out('room')
end
---@param id string
function lighting_emitter(id)
    M:clear_items_at(here(3,0))
    M:create_item_at(here(3,0),ItypeId.new(id),-1)
    local it=M:get_items_at(here(3,0))[1]
    if id=='electric_lantern_on' then it:ammo_set(ItypeId.new('battery'),100) end
    if id~='atomic_lamp' then it:activate() end
    out('placed')
end
function lighting_live()
    local it=M:get_items_at(here(3,0))[1]
    out(it:get_type():str(),it:is_active(),it:ammo_remaining())
    out(gapi.get_avatar():sees(here(4,0)))
end
"""


class LightingSession(Session):
    def build_world(self):
        tmux_game.ROOT = self.root
        game = Game(name="bn-lighting-fixture", options={"SAFEMODE": "false"},
                    userdir=self.curses_userdir)
        self.fixtures = {}
        try:
            start_new_game(game)
            source = " ".join(line for line in FIXTURE_LUA.splitlines()
                              if not line.lstrip().startswith("---@"))
            game.define_lua(HELPERS + source)
            require(game.lua(
                "local a=gapi.get_avatar() a:drop_all_items() a:clear_bionics() "
                "a:clear_mutations() out('empty')"
            ) == ["empty"], game.screen())
            arena(game)
            require(game.lua("lighting_room()") == ["room"], game.screen())
            settle(game)
            require(game.lua("lighting_room()") == ["room"], game.screen())
            for emitter in EMITTERS:
                require(game.lua(f"lighting_emitter('{emitter}')") == ["placed"], game.screen())
                settle(game)
                state = game.lua("lighting_live()")
                (self.artifacts / f"{emitter}-fixture.json").write_text(json.dumps(state))
                require(len(state) == 2 and state[1] == "true", f"unseen floor probe: {state}")
                name, active, fuel = state[0].split(",")
                require(name == emitter, f"lamp reverted or disappeared: {state}")
                if emitter != "atomic_lamp":
                    require(active == "true" and int(fuel) > 0, f"unlit or empty lamp: {state}")
                require(game.lua("out(gdebug.save_game())") == ["true"], game.screen())
                snapshot = self.work / "fixtures" / emitter
                shutil.copytree(self.curses_userdir, snapshot)
                self.fixtures[emitter] = snapshot
        finally:
            subprocess.run(["tmux", "kill-session", "-t", game.name], check=False,
                           stderr=subprocess.DEVNULL)
        worlds = [p for p in (self.curses_userdir / "save").iterdir() if p.is_dir()]
        require(len(worlds) == 1, f"expected one fixture world: {worlds}")
        self.world = worlds[0].name


def floor_mean(frame, grid):
    width, height, data = frame
    x = grid["ox"] + 4 * grid["tx"] + grid["tx"] // 4
    y = grid["oy"] + grid["ty"] // 4
    pw, ph = grid["tx"] // 2, grid["ty"] // 2
    require(0 <= x and x + pw <= width and 0 <= y and y + ph <= height, "floor probe clipped")
    return [sum(data[3 * (row * width + col) + channel]
                for row in range(y, y + ph) for col in range(x, x + pw)) / (pw * ph)
            for channel in range(3)]


def check_hue(gains, hue):
    red, green, blue = gains
    if hue == "green":
        return green > red + 0.02 and green > blue + 0.02
    if hue == "blue":
        return blue > green + 0.02 and green > red + 0.02
    if hue == "warm":
        return red > green + 0.02 and green > blue + 0.02
    return max(gains) / min(gains) < 1.15


def verify(session):
    results = []
    for emitter, hue in EMITTERS.items():
        session.curses_userdir = session.fixtures[emitter]
        gains_by_backend = {}
        for backend in ("cpu", "gpu_software"):
            means = {}
            for colored in (False, True):
                label = f"{emitter}-{backend}-{'on' if colored else 'off'}"
                image = session.launch(label, {**OPTIONS, "COMPUTE_ACCELERATION": backend,
                                               "COLORED_LIGHTING": str(colored).lower()})
                frame = frame_rgb(image)
                means[colored] = floor_mean(frame, world_grid(frame, session.root))
            off, on = means[False], means[True]
            require(min(off) > 5, f"{emitter}/{backend}: floor never received visible light: {off}")
            require(max(off) - min(off) < 4, f"{emitter}/{backend}: toggle-off floor is colored: {off}")
            gains = [on[c] / off[c] for c in range(3)]
            require(check_hue(gains, hue), f"{emitter}/{backend}: expected {hue}, RGB gains {gains}")
            gains_by_backend[backend] = gains
            results.append({"emitter": emitter, "backend": backend, "hue": hue,
                            "off_rgb": off, "on_rgb": on, "rgb_gains": gains})
            print(f"PASS {emitter}/{backend}: {hue}, gains {gains}", flush=True)
        cpu, gpu = gains_by_backend["cpu"], gains_by_backend["gpu_software"]
        require(all(abs(cpu[c] - gpu[c]) < 0.1 for c in range(3)),
                f"{emitter}: CPU and software-GPU hues diverged: {cpu}, {gpu}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(tiles.ROOT))
    parser.add_argument("--binary")
    parser.add_argument("--vk-icd")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--out", default=f"/tmp/bn-lighting-proof-{int(time.time())}")
    args = parser.parse_args()
    artifacts = Path(args.out).resolve()
    artifacts.mkdir(parents=True, exist_ok=False)
    session = LightingSession(args, artifacts / "work", artifacts)
    report = {}
    try:
        session.start()
        session.build_world()
        report["checks"] = verify(session)
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["exception"] = traceback.format_exc()
        print(report["exception"], file=sys.stderr)
    finally:
        session.close()
        (artifacts / "result.json").write_text(json.dumps(report, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
