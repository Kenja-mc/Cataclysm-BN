"""Opt-in instruments in Fusion's vehicle card and the legacy floating vehicle window.

These are curses scenarios only. Native scaling, paired compact/dashboard captures and
real input traces belong to ``tiles.py driving_dashboard``.
"""
import json
import re
import tempfile
from pathlib import Path

from helpers import HELPERS, Game, action_menu, arena, choose_menu_entry, start_new_game
from remote_vehicle import enter_remote_control, remote_vehicle_game
from tmux_game import ROOT
from vehicle_box import spawn_vehicle, vehicle_game

BAR = r"[#-]{3,}"
OPTIONS = {"DRIVING_DASHBOARD": "true", "HUD_WINDOWS": "true", "HUD_ICONS": "ascii",
           "SHOW_WELCOME": "false", "SHOW_TIPS": "false", "ANIMATIONS": "false",
           "USE_METRIC_SPEEDS": "mph", "SIDEBAR_POSITION": "right"}

# A private high-lift aircraft reaches its real takeoff threshold in the paved arena.
# No velocity, lift state or dashboard reading is injected.
PLANE_WING = {
    "type": "vehicle_part", "id": "e2e_dashboard_wing", "copy-from": "wing_metal_external",
    "name": "dashboard test wing", "lift_coff": 5000,
}
PLANE_PROTOTYPE = {
    "type": "vehicle", "id": "e2e_dashboard_plane", "name": "Dashboard Test Plane",
    "blueprint": [[" | "], [" | "], ["-#-"], [" | "], [" | "], [" | "], [" | "]],
    "parts": [
        {"x": 0, "y": 0, "parts": ["xlframe_cross", "seat", "seatbelt", "controls",
                                   "dashboard", "e2e_dashboard_wing"]},
        {"x": 0, "y": -1, "parts": ["xlframe_vertical", "e2e_dashboard_wing",
                                    "wheel_mount_light", "wheel_small"]},
        {"x": 0, "y": 1, "parts": ["xlframe_vertical", "e2e_dashboard_wing",
                                   "wheel_mount_light", "wheel_small"]},
        {"x": 0, "y": 2, "parts": ["xlframe_horizontal", "engine_inline4",
                                   {"part": "tank_small", "fuel": "gasoline"}, "battery_car",
                                   "wheel_mount_light_steerable", "wheel_small",
                                   "propeller_metal"]},
    ],
}


def aircraft_game(name: str) -> Game:
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-dashboard-plane-"))
    mod_dir = userdir / "mods" / "e2e_dashboard_plane"
    mod_dir.mkdir(parents=True)
    (mod_dir / "modinfo.json").write_text(json.dumps([{
        "type": "MOD_INFO", "id": "e2e_dashboard_plane", "name": "E2E dashboard plane",
        "description": "High-lift aircraft for the driving dashboard lift check.",
        "category": "content", "dependencies": ["bn"],
    }]))
    (mod_dir / "vehicles.json").write_text(json.dumps([PLANE_WING, PLANE_PROTOTYPE]))
    defaults = json.loads((ROOT / "data/mods/default.json").read_text())
    (userdir / "config").mkdir()
    (userdir / "config/default_mods.json").write_text(
        json.dumps([*defaults, "e2e_dashboard_plane"]))
    game = Game(name=name, userdir=userdir, layout="fusion", cols=160, rows=45,
                options={**OPTIONS, "SAFEMODE": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        clear_driving_arena(game)
        return game
    except Exception:
        game.close()
        raise


def clear_driving_arena(game: Game) -> None:
    assert game.lua(
        "for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end "
        "for dx=-13,13 do for dy=-13,13 do local p=here(dx,dy) "
        "M:set_ter_at(p,TerId.new('t_pavement'):int_id()) "
        "M:set_furn_at(p,FurnId.new('f_null'):int_id()) "
        "local above=TripointBubMs.new(p.x,p.y,p.z+1) "
        "M:set_ter_at(above,TerId.new('t_open_air'):int_id()) "
        "M:set_furn_at(above,FurnId.new('f_null'):int_id()) "
        "end end out('ok')") == ["ok"]


def dashboard_game(name: str, *, layout: str = "fusion", cols: int = 160,
                   rows: int = 45, **options: str) -> Game:
    game = vehicle_game(name, layout=layout, cols=cols, rows=rows, **{**OPTIONS, **options})
    try:
        clear_driving_arena(game)
        return game
    except Exception:
        game.close()
        raise


def capture_proof(game: Game, directory: Path, phase: str) -> None:
    """Retain actual curses cells (and their colours), including successful runs."""
    game.settle_screen()
    (directory / f"{phase}.txt").write_text(game.screen())
    (directory / f"{phase}.ansi").write_text(game.screen_colors())


def vehicle_panel(screen: str) -> tuple[int, int, int, int]:
    """Locate the actual bordered card/window, not a fixed number of instrument rows."""
    lines = screen.splitlines()
    titles = [(y, line, re.search(r"\b(?:VEHICLE|Vehicle)\b", line))
              for y, line in enumerate(lines)
              if re.search(r"\b(?:VEHICLE|Vehicle)\b", line)
              and any(border in line for border in "╭┌│")]
    assert len(titles) == 1, "expected one vehicle card/window:\n" + screen
    title_y, title, match = titles[0]
    left = max(title.rfind(border, 0, match.start()) for border in "╭┌│")
    rights = [title.find(border, match.end()) for border in "╮┐│"]
    right = min(x for x in rights if x >= 0)
    top = title_y if title[left] in "╭┌" else title_y - 1
    bottoms = [y for y in range(title_y + 1, len(lines))
               if len(lines[y]) > right and lines[y][left] in "╰└"
               and lines[y][right] in "╯┘"]
    assert bottoms and left >= 0 and right > left, "unbounded vehicle panel:\n" + screen
    bottom = bottoms[0]
    assert all(len(lines[y]) > right and lines[y][left] == lines[y][right] == "│"
               for y in range(top + 1, bottom)), "clipped vehicle panel:\n" + screen
    return left, top, right, bottom


def panel_text(screen: str) -> str:
    left, top, right, bottom = vehicle_panel(screen)
    return "\n".join(line[left + 1:right] for line in screen.splitlines()[top:bottom + 1])


def row_text(screen: str, needle: str) -> str:
    found = [line for line in panel_text(screen).splitlines()
             if needle.lower() in line.lower()]
    assert len(found) == 1, f"expected one {needle!r} instrument:\n" + screen
    return found[0]


def speed_of(screen: str, units: str = "mph") -> int:
    # Speed is a summary fact; neither title case nor border decoration is contractual.
    header = panel_text(screen).splitlines()[:2]
    found = re.search(r"(-?\d+)\s+" + re.escape(units) + r"\s+[NSEW]{1,2}\b", " ".join(header))
    assert found, "vehicle summary must show speed, units and cardinal heading:\n" + screen
    return int(found.group(1))


def assert_instruments(screen: str, units: str = "mph") -> None:
    speed_of(screen, units)
    assert re.search(BAR, row_text(screen, "Speed")), screen
    assert re.search(r"Cruise\s+(?:On\s+\d+\s+" + re.escape(units) + r"|Off)\b",
                     row_text(screen, "Cruise")), screen
    assert re.search(r"Heading\s+\d+°", row_text(screen, "Heading")), screen
    assert re.search(r"Engine\s+(?:On|Off)\b", row_text(screen, "Engine")), screen


def take_control(game: Game) -> None:
    action_menu(game, "Misc", "Control Vehicle")
    for _ in range(40):
        screen = game.screen()
        if "Stop trying to start the vehicle?" in screen:
            game.keys("I", delay=0.8)
        if re.search(r"Engine\s+On\b", screen):
            return
        game.keys("x", delay=1.0)
    raise AssertionError("the vehicle engine never started:\n" + game.screen())


def test_dashboard_fusion_driving_facts(_game):
    game = dashboard_game("bn-e2e-dashboard-fusion")
    try:
        spawn_vehicle(game)
        screen = game.screen()
        assert "VEHICLE" in screen, screen
        left, _, right, _ = vehicle_panel(screen)
        assert right - left + 1 <= 32, "instruments must fit Fusion's existing vehicle card:\n" + screen
        assert_instruments(screen)
        assert speed_of(screen) == 0, screen
        for fuel in ("gasoline", "battery"):
            assert re.search(BAR + r"\s+\d+%", row_text(screen, fuel)), screen
        take_control(game)
        game.keys("w", delay=0.5)
        game.keys("x", delay=0.8)
        screen = game.screen()
        assert speed_of(screen) > 0, "real throttle must update speed:\n" + screen
        cruise = re.search(r"Cruise\s+On\s+(\d+) mph", row_text(screen, "Cruise"))
        assert cruise and int(cruise.group(1)) > 0, screen
        game.keys("Enter", delay=0.8)
        choose_menu_entry(game, "Control Vehicle")
        game.wait_for("Vehicle controls")
        choose_menu_entry(game, "Disable cruise control")
        game.settle_screen()
        assert re.search(r"Cruise\s+Off\b", row_text(game.screen(), "Cruise")), game.screen()
    finally:
        game.close()


def test_dashboard_driving_facts_fit_80x25(_game):
    # Fusion's real small-screen path is the grouped fallback, not a second tiny Fusion design.
    for layout in ("fusion", "labels"):
        game = dashboard_game("bn-e2e-dashboard-small-" + layout, layout=layout)
        try:
            spawn_vehicle(game)
            game.resize(80, 25)
            game.settle_screen()
            screen = game.screen()
            assert_instruments(screen)
            left, top, right, bottom = vehicle_panel(screen)
            assert 0 <= left < right < 36 and 0 <= top < bottom < 25, screen
            # The actual avatar glyph remains visible outside the instrument window.
            avatars = [(x, y) for y, line in enumerate(screen.splitlines())
                       for x, ch in enumerate(line[:36]) if ch == "@"]
            assert avatars, "dashboard must not cover the avatar:\n" + screen
            assert all(not (left <= x <= right and top <= y <= bottom) for x, y in avatars), screen
        finally:
            game.close()


def fuel_left(game: Game, fuel: str) -> int:
    return int(game.lua("out(M:get_vehicle_fuel_left_at(here(0,0),'CONTROLS',"
                        f"ItypeId.new('{fuel}')))")[0])


def drain(game: Game, fuel: str, amount: int) -> None:
    assert int(game.lua("out(M:drain_vehicle_fuel_at(here(0,0),'CONTROLS',"
                        f"ItypeId.new('{fuel}'),{amount}))")[0]) > 0


def test_dashboard_fuel_and_battery_warnings_are_worded(_game):
    for prototype, fuel in (("car", "gasoline"), ("electric_car", "battery")):
        game = dashboard_game("bn-e2e-dashboard-warning-" + fuel)
        proof = Path(tempfile.mkdtemp(prefix=f"bn-dashboard-{fuel}-warnings-"))
        try:
            spawn_vehicle(game, prototype)
            start = fuel_left(game, fuel)
            assert start > 0, "warning fixture must start fuelled"
            drain(game, fuel, start * 85 // 100)
            capture_proof(game, proof, "low")
            low = re.search(BAR + r"\s+(\d+)%\s+low\b", row_text(game.screen(), fuel), re.I)
            assert low and 6 <= int(low.group(1)) <= 20, game.screen()
            # Critical is a word plus punctuation, not just a red gauge.
            drain(game, fuel, fuel_left(game, fuel) * 4 // 5)
            capture_proof(game, proof, "critical")
            critical = re.search(r"(\d+)%\s+low!", row_text(game.screen(), fuel), re.I)
            assert critical and 0 < int(critical.group(1)) <= 5, game.screen()
            drain(game, fuel, fuel_left(game, fuel))
            assert fuel_left(game, fuel) == 0
            capture_proof(game, proof, "empty")
            assert re.search(r"-{3,}\s+0%\s+empty\b", row_text(game.screen(), fuel), re.I), game.screen()
            if fuel == "gasoline":
                assert re.search(BAR + r"\s+\d+%", row_text(game.screen(), "battery")), game.screen()
            else:
                assert len(re.findall(r"\bbatter(?:y|ies)\b", panel_text(game.screen()), re.I)) == 1, game.screen()
        finally:
            print(f"Dashboard {fuel} warning captures: {proof}")
            game.close()


def test_dashboard_aircraft_takeoff_state(_game):
    game = aircraft_game("bn-e2e-dashboard-aircraft")
    proof = Path(tempfile.mkdtemp(prefix="bn-dashboard-aircraft-proof-"))
    trace = []
    try:
        spawn_vehicle(game, "e2e_dashboard_plane")
        capture_proof(game, proof, "below-takeoff")
        takeoff = re.search(r"Takeoff\s+(\d+) mph\s+no lift", row_text(game.screen(), "Takeoff"))
        assert takeoff and int(takeoff.group(1)) > 0, game.screen()
        needed = int(takeoff.group(1))
        take_control(game)
        for _ in range(12):
            if re.search(r"Takeoff\s+\d+ mph\s+lift\b", panel_text(game.screen())):
                break
            for key, delay in (("w", 0.2), ("x", 0.8)):
                trace.append({"key": key, "delay": delay})
                game.keys(key, delay=delay)
        capture_proof(game, proof, "after-real-throttle")
        screen = game.screen()
        assert re.search(r"Takeoff\s+" + str(needed) + r" mph\s+lift\b",
                         row_text(screen, "Takeoff")), screen
        assert speed_of(screen) >= needed, screen
    finally:
        (proof / "throttle-input-trace.json").write_text(json.dumps(trace, indent=2))
        print(f"Aircraft dashboard captures and throttle trace: {proof}")
        game.close()


def test_dashboard_remote_control(_game):
    for layout in ("fusion", "labels"):
        game = remote_vehicle_game("bn-e2e-dashboard-remote-" + layout, layout=layout,
                                   cols=160, rows=45, **OPTIONS)
        proof = Path(tempfile.mkdtemp(prefix=f"bn-dashboard-remote-{layout}-proof-"))
        trace = []
        try:
            clear_driving_arena(game)
            enter_remote_control(game)
            capture_proof(game, proof, "remote-control")
            screen = game.screen()
            assert_instruments(screen)
            assert "Remote control" in row_text(screen, "Remote control"), screen
            assert re.search(r"(?:gasoline|battery)\s+" + BAR, panel_text(screen), re.I), screen
            action_menu(game, "Misc", "Control Vehicle")
            game.wait_for("Vehicle controls")
            assert "Stop controlling" in game.screen() or "Stop driving" in game.screen(), game.screen()
            game.keys("Escape", delay=0.5)
            game.settle_screen()
            # Absolute positions remain valid when driving recentres the reality bubble.
            positions = (
                "local a=gapi.get_avatar():abs_pos() out(a.x,a.y,a.z) "
                "for _,v in ipairs(M:get_vehicles()) do if v:type()=='bubble_car' then "
                "local p=M:bub_to_abs(v:pos()) out(p.x,p.y,p.z) end end")
            before = game.lua(positions)
            assert len(before) == 2, before
            for _ in range(6):
                for key in ("w", "x"):
                    trace.append({"key": key, "delay": 0.8})
                    game.keys(key, delay=0.8)
                if speed_of(game.screen()) > 0 and game.lua(positions)[1] != before[1]:
                    break
            capture_proof(game, proof, "remote-driving")
            assert speed_of(game.screen()) > 0, game.screen()
            after = game.lua(positions)
            assert after[0] == before[0] and after[1] != before[1], (before, after)
            assert "Remote control" in panel_text(game.screen()), game.screen()
            (proof / "absolute-positions.json").write_text(json.dumps({"before": before, "after": after}))
        finally:
            (proof / "throttle-input-trace.json").write_text(json.dumps(trace, indent=2))
            print(f"Remote dashboard captures and throttle trace: {proof}")
            game.close()


def test_dashboard_unicode_icons_and_kmh(_game):
    game = dashboard_game("bn-e2e-dashboard-unicode", HUD_ICONS="unicode", USE_METRIC_SPEEDS="km/h")
    try:
        spawn_vehicle(game)
        assert_instruments(game.screen(), "km/h")
        start = fuel_left(game, "gasoline")
        assert start > 0
        drain(game, "gasoline", start * 85 // 100)
        game.settle_screen()
        assert re.search(r"\d+%\s+low\b", row_text(game.screen(), "gasoline"), re.I), game.screen()
    finally:
        game.close()


def test_dashboard_off_preserves_compact_readout(_game):
    for layout, windows in (("fusion", "true"), ("labels", "true"), ("labels", "false")):
        game = dashboard_game("bn-e2e-dashboard-off-" + layout + windows, layout=layout,
                              DRIVING_DASHBOARD="false", HUD_WINDOWS=windows)
        try:
            spawn_vehicle(game)
            screen = game.screen()
            assert "Azimuth: 0°" in screen and "Speed: 0 mph" in screen, screen
            assert re.search(r"gasoline:\s*\d+%", screen, re.I), screen
            assert not re.search(r"Cruise\s+(?:On|Off)\b|Heading\s+\d+°", screen), screen
        finally:
            game.close()


def test_dashboard_does_not_replace_classic_or_compact_panels(_game):
    for layout in ("classic", "compact"):
        game = dashboard_game("bn-e2e-dashboard-" + layout, layout=layout, HUD_VEHICLE_BOX="off")
        try:
            spawn_vehicle(game)
            screen = game.screen()
            assert "fuel:" in screen and re.search(r"mph\s*:\s*0", screen), screen
            assert not re.search(r"Cruise\s+(?:On|Off)\b|Heading\s+\d+°", screen), screen
        finally:
            game.close()


TESTS = [
    test_dashboard_fusion_driving_facts,
    test_dashboard_driving_facts_fit_80x25,
    test_dashboard_fuel_and_battery_warnings_are_worded,
    test_dashboard_aircraft_takeoff_state,
    test_dashboard_remote_control,
    test_dashboard_unicode_icons_and_kmh,
    test_dashboard_off_preserves_compact_readout,
    test_dashboard_does_not_replace_classic_or_compact_panels,
]
