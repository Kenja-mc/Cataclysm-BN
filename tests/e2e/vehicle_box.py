"""Vehicle HUD contracts exercised through actual vehicles and driving controls."""
import re
import subprocess

from helpers import HELPERS, Game, action_menu, arena, choose_menu_entry, option_value, settle, start_new_game


def vehicle_game(name, **options):
    game = Game(name=name, options={"SAFEMODE": "false", "USE_METRIC_SPEEDS": "mph", **options})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        assert game.lua("for dx=-13,13 do for dy=-13,13 do M:set_ter_at(here(dx,dy), TerId.new('t_pavement'):int_id()) end end out('ok')") == ["ok"]
    except Exception:
        game.close()
        raise
    return game


def spawn_vehicle(game, prototype="car"):
    game.keys("F12", delay=0.6)
    game.wait_for("Debug Functions")
    game.keys("s" if option_value(game, "CONTROL_SCHEME", "modern") == "classic" else "S", delay=0.3)
    game.wait_for("Spawn a vehicle")
    game.keys("v", delay=0.3)
    game.wait_for("Choose vehicle to spawn")
    game.keys("/", delay=0.4)
    game.type(f"({prototype})")
    game.keys("Enter", "Enter", delay=0.6)
    game.wait_for("Vehicle condition")
    game.keys("Down", "Enter", delay=0.6)  # Undamaged; debug spawn fills fuel stores.
    game.wait_for("Vehicle direction")
    game.keys("Enter", delay=0.8)  # Default -90 degrees: north.
    settle(game)
    assert game.lua("out(M:has_vehicle_part_with_feature_at(here(0,0),'CONTROLS'))") == ["true"]


def take_control(game):
    """Taking control also starts the engine, which nearby monsters may interrupt."""
    action_menu(game, "Misc", "Control Vehicle")
    for _ in range(40):
        if "Stop trying to start the vehicle?" in game.screen():
            game.keys("I", delay=0.8)  # Ignore further distractions and finish.
        if "Engine: on" in game.screen():
            return
        game.keys("x", delay=1.0)
    raise AssertionError("the vehicle engine never started:\n" + game.screen())


def test_vehicle_box(_game):
    game = vehicle_game("bn-e2e-vehicle-box")
    try:
        assert "Azimuth:" not in game.screen(), game.screen()
        spawn_vehicle(game)
        screen = game.screen()
        assert re.search(r"Azimuth: 0°", screen), screen
        assert "Speed: 0 mph" in screen and "Engine: off" in screen, screen
        fuel = re.search(r"gasoline: (\d+)%", screen, re.IGNORECASE)
        assert fuel and 0 < int(fuel[1]) <= 100, screen
        assert "Battery: 100%" in screen, screen
        assert "fuel:" not in screen, "Vehicle sidebar must step aside:\n" + screen
        subprocess.run(["tmux", "resize-window", "-t", game.name, "-x", "80", "-y", "25"], check=True)
        settle(game)
        screen = game.screen()
        assert "Azimuth: 0°" in screen and "Speed: 0 mph" in screen, screen
        assert re.search(r"gasoline: \d+%", screen, re.IGNORECASE) and "Battery: 100%" in screen, screen
        subprocess.run(["tmux", "resize-window", "-t", game.name, "-x", "140", "-y", "45"], check=True)
        settle(game)
        # Fuel exhaustion remains visible rather than making its row disappear.
        assert int(game.lua("out(M:drain_vehicle_fuel_at(here(0,0),'CONTROLS',ItypeId.new('gasoline'),1000000000))")[0]) > 0
        assert int(game.lua("out(M:get_vehicle_fuel_left_at(here(0,0),'CONTROLS',ItypeId.new('gasoline')))")[0]) == 0
        settle(game)
        assert re.search(r"gasoline: 0%", game.screen(), re.IGNORECASE), game.screen()
        game.keys("a", "a", "a", delay=0.8)
        settle(game)
        assert "Azimuth:" not in game.screen(), "Box must disappear after leaving:\n" + game.screen()
    finally:
        game.close()


def test_vehicle_box_electric(_game):
    game = vehicle_game("bn-e2e-vehicle-electric", HUD_VEHICLE_BOX="top_left", HUD_ICONS="ascii")
    try:
        spawn_vehicle(game, "electric_car")
        screen = game.screen()
        assert "Azimuth: 0°" in screen and "Battery: 100%" in screen, screen
        assert len(re.findall(r"(?:battery|batteries):\s*\d+%", screen, re.IGNORECASE)) == 1, "Electric fuel and battery must not duplicate:\n" + screen
        # The same corner already holds weather/combat; all three must survive stacking.
        assert "Walking" in screen and "Azimuth:" in screen, screen
        assert "wasd move" in screen and "throttle" not in screen, screen
        take_control(game)
        game.keys("w", delay=1)
        settle(game)
        screen = game.screen()
        assert "Engine: on" in screen, screen
        speed = re.search(r"Speed: (-?\d+) mph", screen)
        assert speed and int(speed[1]) > 0, "Driving must update actual speed:\n" + screen
        cruise = re.search(r"Cruise: (\d+) mph", screen)
        assert cruise and int(cruise[1]) > 0, screen
        assert "ws throttle" in screen and "ad steer" in screen and "wasd move" not in screen, screen
        game.keys("s", delay=1)
        settle(game)
        action_menu(game, "Misc", "Control Vehicle")
        game.wait_for("Let go of controls")
        game.keys("Enter", delay=1)
        settle(game)
        screen = game.screen()
        assert "wasd move" in screen and "throttle" not in screen and "ad steer" not in screen, screen
    finally:
        game.close()


def test_vehicle_box_aircraft(_game):
    game = vehicle_game("bn-e2e-vehicle-aircraft", HUD_VEHICLE_BOX="bottom_left")
    try:
        spawn_vehicle(game, "plane_small")
        screen = game.screen()
        takeoff = re.search(r"Takeoff: (\d+) mph", screen)
        assert takeoff and int(takeoff[1]) > 0, "Takeoff speed must retain its native units:\n" + screen
    finally:
        game.close()


def test_vehicle_box_off(_game):
    game = vehicle_game("bn-e2e-vehicle-off", HUD_VEHICLE_BOX="off")
    try:
        spawn_vehicle(game)
        screen = game.screen()
        assert "Azimuth:" not in screen and "Speed:" not in screen, screen
        assert "fuel:" in screen and re.search(r"mph\s*:\s*0", screen), "Old sidebar must return:\n" + screen
    finally:
        game.close()


def test_vehicle_horn_and_handbrake_route(_game):
    """H honks while driving; Space brakes directly, and the vehicle menu still offers it."""
    game = vehicle_game("bn-e2e-vehicle-brake")
    try:
        spawn_vehicle(game)
        take_control(game)
        game.keys("space", delay=0.8)
        settle(game)
        assert "You pull a handbrake." not in game.screen(), \
            "a standstill brake must stay silent:\n" + game.screen()
        game.keys("w", delay=1.2)
        settle(game)
        moving = re.search(r"Speed: (\d+) mph", game.screen())
        assert moving and int(moving[1]) > 0, game.screen()
        game.keys("H", delay=0.8)
        game.wait_for("honk")
        game.keys("space", "x", "x", delay=1.0)
        settle(game)
        braked = re.search(r"Speed: (\d+) mph", game.screen())
        assert braked and int(braked[1]) < int(moving[1]), \
            "Space must brake while driving:\n" + game.screen()
        # The driving menu keeps its own entries; the handbrake no longer hides inside it.
        game.keys("Enter", delay=1.0)
        choose_menu_entry(game, "Control Vehicle")
        game.wait_for("Vehicle controls")
        assert "Stop driving" in game.screen(), game.screen()
        game.keys("Escape", delay=0.6)
    finally:
        game.close()


def test_vehicle_box(_game):
    game = vehicle_game("bn-e2e-vehicle-box")
    try:
        assert "Azimuth:" not in game.screen(), game.screen()
        spawn_vehicle(game)
        screen = game.screen()
        assert re.search(r"Azimuth: 0°", screen), screen
        assert "Speed: 0 mph" in screen and "Engine: off" in screen, screen
        fuel = re.search(r"gasoline: (\d+)%", screen, re.IGNORECASE)
        assert fuel and 0 < int(fuel[1]) <= 100, screen
        assert "Battery: 100%" in screen, screen
        assert "fuel:" not in screen, "Vehicle sidebar must step aside:\n" + screen
        subprocess.run(["tmux", "resize-window", "-t", game.name, "-x", "80", "-y", "25"], check=True)
        settle(game)
        screen = game.screen()
        assert "Azimuth: 0°" in screen and "Speed: 0 mph" in screen, screen
        assert re.search(r"gasoline: \d+%", screen, re.IGNORECASE) and "Battery: 100%" in screen, screen
        subprocess.run(["tmux", "resize-window", "-t", game.name, "-x", "140", "-y", "45"], check=True)
        settle(game)
        # Fuel exhaustion remains visible rather than making its row disappear.
        assert int(game.lua("out(M:drain_vehicle_fuel_at(here(0,0),'CONTROLS',ItypeId.new('gasoline'),1000000000))")[0]) > 0
        assert int(game.lua("out(M:get_vehicle_fuel_left_at(here(0,0),'CONTROLS',ItypeId.new('gasoline')))")[0]) == 0
        settle(game)
        assert re.search(r"gasoline: 0%", game.screen(), re.IGNORECASE), game.screen()
        game.keys("a", "a", "a", delay=0.8)
        settle(game)
        assert "Azimuth:" not in game.screen(), "Box must disappear after leaving:\n" + game.screen()
    finally:
        game.close()


def test_vehicle_box_electric(_game):
    game = vehicle_game("bn-e2e-vehicle-electric", HUD_VEHICLE_BOX="top_left", HUD_ICONS="ascii")
    try:
        spawn_vehicle(game, "electric_car")
        screen = game.screen()
        assert "Azimuth: 0°" in screen and "Battery: 100%" in screen, screen
        assert len(re.findall(r"(?:battery|batteries):\s*\d+%", screen, re.IGNORECASE)) == 1, "Electric fuel and battery must not duplicate:\n" + screen
        # The same corner already holds weather/combat; all three must survive stacking.
        assert "Walking" in screen and "Azimuth:" in screen, screen
        assert "wasd move" in screen and "throttle" not in screen, screen
        take_control(game)
        game.keys("w", delay=1)
        settle(game)
        screen = game.screen()
        assert "Engine: on" in screen, screen
        speed = re.search(r"Speed: (-?\d+) mph", screen)
        assert speed and int(speed[1]) > 0, "Driving must update actual speed:\n" + screen
        cruise = re.search(r"Cruise: (\d+) mph", screen)
        assert cruise and int(cruise[1]) > 0, screen
        assert "ws throttle" in screen and "ad steer" in screen and "wasd move" not in screen, screen
        game.keys("s", delay=1)
        settle(game)
        action_menu(game, "Misc", "Control Vehicle")
        game.wait_for("Let go of controls")
        game.keys("Enter", delay=1)
        settle(game)
        screen = game.screen()
        assert "wasd move" in screen and "throttle" not in screen and "ad steer" not in screen, screen
    finally:
        game.close()


def test_vehicle_box_aircraft(_game):
    game = vehicle_game("bn-e2e-vehicle-aircraft", HUD_VEHICLE_BOX="bottom_left")
    try:
        spawn_vehicle(game, "plane_small")
        screen = game.screen()
        takeoff = re.search(r"Takeoff: (\d+) mph", screen)
        assert takeoff and int(takeoff[1]) > 0, "Takeoff speed must retain its native units:\n" + screen
    finally:
        game.close()


def test_vehicle_box_off(_game):
    game = vehicle_game("bn-e2e-vehicle-off", HUD_VEHICLE_BOX="off")
    try:
        spawn_vehicle(game)
        screen = game.screen()
        assert "Azimuth:" not in screen and "Speed:" not in screen, screen
        assert "fuel:" in screen and re.search(r"mph\s*:\s*0", screen), "Old sidebar must return:\n" + screen
    finally:
        game.close()


def test_vehicle_handbrake_and_horn(_game):
    """While driving, Space pulls the handbrake and H honks, without a vehicle menu."""
    game = vehicle_game("bn-e2e-vehicle-brake")
    try:
        spawn_vehicle(game)
        take_control(game)
        game.keys("w", delay=1.2)
        settle(game)
        moving = re.search(r"Speed: (\d+) mph", game.screen())
        assert moving and int(moving[1]) > 0, game.screen()
        game.keys("space", "x", "x", delay=1.0)
        settle(game)
        stopped = re.search(r"Speed: (\d+) mph", game.screen())
        assert stopped and int(stopped[1]) < int(moving[1]), \
            "Space must brake while driving:\n" + game.screen()
        game.keys("H", delay=0.8)
        game.wait_for("honk")
    finally:
        game.close()


TESTS = [test_vehicle_horn_and_handbrake_route, test_vehicle_handbrake_and_horn, test_vehicle_box,
         test_vehicle_box_electric, test_vehicle_box_aircraft, test_vehicle_box_off]
