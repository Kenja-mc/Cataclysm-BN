"""Map memory keeps the ground a moving vehicle hides (upstream #10452)."""
import json
import tempfile
from pathlib import Path

from helpers import HELPERS, Game, bub_pos, settle, start_new_game
from tmux_game import ROOT
from vehicle_box import spawn_vehicle, take_control


def vehicle_game(name, **options):
    # Clearing exhaust after driving invalidates the sight caches under test.
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-vehicle-memory-"))
    mod_dir = userdir / "mods" / "e2e_vehicle_memory"
    mod_dir.mkdir(parents=True)
    prototype = next(vehicle for vehicle in json.loads(
        (ROOT / "data/json/vehicles/vans_busses.json").read_text()) if vehicle["id"] == "armored_car")
    prototype["id"] = "e2e_memory_electric_car"
    prototype["name"] = "Memory fixture armored car"
    for part in prototype["parts"]:
        part["parts"] = ["engine_electric_super" if item == "diesel_engine_v8" else item
                         for item in part["parts"] if item != "alternator_truck"]
    (mod_dir / "modinfo.json").write_text(json.dumps([{
        "type": "MOD_INFO", "id": "e2e_vehicle_memory", "name": "E2E vehicle memory",
        "description": "Electric, camera-free armored car for the map-memory fixture.",
        "category": "content", "dependencies": ["bn"],
    }]))
    (mod_dir / "vehicles.json").write_text(json.dumps([prototype]))
    defaults = json.loads((ROOT / "data/mods/default.json").read_text())
    (userdir / "config").mkdir()
    (userdir / "config/default_mods.json").write_text(json.dumps([*defaults, "e2e_vehicle_memory"]))
    game = Game(name=name, userdir=userdir,
                options={"SAFEMODE": "false", "ANIMATIONS": "false", **options})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        settle(game)  # Activate queued NPCs before parking them.
        # Yellow pavement marks the memorable ground; its ':' symbol is unique on screen.
        # Engine sounds place random '?' overlays in the occluded trail; isolate map memory.
        assert game.lua("local a=gapi.get_avatar() a:set_mutation(MutationBranchId.new('DEAF')) "
                        "out(a:is_deaf())") == ["true"]
        assert game.lua("for dx=-18,18 do for dy=-40,15 do local p=here(dx,dy) "
                        "M:set_ter_at(p, TerId.new('t_pavement_y'):int_id()) "
                        "M:set_furn_at(p, FurnId.new('f_null'):int_id()) M:clear_items_at(p) "
                        "M:remove_trap_at(p) "
                        "for _,fid in ipairs(M:get_field_ids_at(p)) do M:remove_field_at(p,fid) end "
                        "local cr=gapi.get_creature_at(p) if cr and not cr:is_avatar() then park(cr) end "
                        "end end out('ok')") == ["ok"]
        settle(game)
    except Exception:
        game.close()
        raise
    return game


def drive_north(game, tiles=3, presses=70):
    start = bub_pos(game)
    for _ in range(presses):
        game.keys("w", delay=0.7)
        settle(game)
        current = bub_pos(game)
        assert current[0] == start[0] and current[2] == start[2], (
            "the vehicle left the straight, level fixture:\n" + game.screen())
        distance = start[1] - current[1]
        if distance >= tiles:
            assert distance <= 10, "the vehicle overshot the remembered fixture:\n" + game.screen()
            return
    raise AssertionError(f"the vehicle did not drive {tiles} tiles north:\n" + game.screen())


def ground_region(screen, rows):
    lines = screen.splitlines()
    avatars = [(line.index('@'), row) for row, line in enumerate(lines) if '@' in line[:95]]
    assert len(avatars) == 1, "expected one avatar in the map:\n" + screen
    col, row = avatars[0]
    assert all(0 <= row + dy < len(lines) and col + 4 < len(lines[row + dy]) for dy in rows), (
        "the ground assertion region is outside the screen:\n" + screen)
    return [lines[row + dy][col + dx] for dy in rows for dx in range(5) if dy != 0 or dx != 0]


def test_memory_behind_moved_vehicle(_game):
    """A vehicle that blocks the view must not blank the remembered ground behind it."""
    game = vehicle_game("bn-e2e-vehicle-memory")
    try:
        # These uncovered tiles include the whole future trailing region, even if the
        # drive advances ten tiles.  Their memory must exist before the vehicle spawns.
        before = game.screen()
        assert set(ground_region(before, range(-6, 9))) == {':'}, (
            "the fixture ground was not visible before spawning the vehicle:\n" + before)
        spawn_vehicle(game, "e2e_memory_electric_car")
        take_control(game)
        drive_north(game)
        screen = game.screen()
        assert game.lua("local a=gapi.get_avatar() local visible=false "
                        "for dx=0,4 do for dy=6,11 do visible=a:sees(here(dx,dy)) or visible end end "
                        "out(visible)") == ["false"], (
            "the vehicle must hide all ground being measured:\n" + screen)
        # The opaque armored hull is unchanged; the private fixture mod uses an electric
        # drivetrain so exhaust cannot cover the remembered pavement.
        hidden = ground_region(screen, range(6, 12))
        assert set(hidden) == {':'}, (
            "tiles hidden by the vehicle lost their remembered ground: "
            f"{sorted(set(hidden))}\n" + screen)
    finally:
        game.close()


TESTS = [test_memory_behind_moved_vehicle]
