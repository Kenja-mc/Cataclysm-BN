"""The driving dashboard (issue #21) in the floating HUD's vehicle window.

The dashboard owns that window's reading only: the fixed layouts keep the compact vehicle
readout, and turning the floating HUD off must bring that readout back.  These tests drive real
vehicles, drain a real tank and take remote control, then read the window's own cells.
"""
import re

from helpers import action_menu
from remote_vehicle import enter_remote_control, remote_vehicle_game
from vehicle_box import spawn_vehicle, vehicle_game

BAR = r"[#-]{6}"


def dashboard_game(name, **options):
    profile = {"HUD_WINDOWS": "true", "HUD_ICONS": "ascii", "SHOW_WELCOME": "false",
               "ANIMATIONS": "false"}
    profile.update(options)
    return vehicle_game(name, **profile)


def title_row(screen: str):
    """The vehicle window's title row, with its collapse control."""
    rows = [(y, line) for y, line in enumerate(screen.splitlines())
            if "Vehicle" in line and ("[-]" in line or "[+]" in line)]
    assert len(rows) == 1, "expected one vehicle window title row:\n" + screen
    return rows[0]


def summary(line: str) -> str:
    start = line.index("Vehicle") + len("Vehicle")
    end = min(i for i in (line.find("[-]"), line.find("[+]")) if i >= 0)
    return line[start:end].strip()


def window_columns(screen: str):
    """Left and right border columns of the vehicle window, and its title row."""
    y, title = title_row(screen)
    name_x = title.index("Vehicle")
    left = title.rfind("│", 0, name_x)
    right = title.find("│", name_x + len("Vehicle"))
    assert left >= 0 and right > left, "the title row must sit between its borders:\n" + title
    top = screen.splitlines()[y - 1]
    assert top[left] in "╭┌" and top[right] in "╮┐", \
        "the title must sit under the window's top border:\n" + top
    return left, right, y


def row_text(screen: str, needle: str) -> str:
    """The window's interior text for the one row carrying `needle`."""
    left, right, title_y = window_columns(screen)
    lines = screen.splitlines()
    found = [y for y in range(title_y, len(lines))
             if needle.lower() in lines[y][left + 1:right].lower()]
    assert len(found) == 1, f"expected one {needle!r} row in the window:\n" + screen
    line = lines[found[0]]
    assert line[right] == "│", f"the {needle!r} row must end at the window border:\n" + line
    return line[left + 1:right]


def speed_of(screen: str) -> int:
    _, title = title_row(screen)
    found = re.search(r"Vehicle\s+(-?\d+)\s+\S+", title)
    assert found, "the title must show the speed:\n" + title
    return int(found.group(1))


def take_control(game):
    """Take control through the real menu; the dashboard words the engine state."""
    action_menu(game, "Misc", "Control Vehicle")
    for _ in range(40):
        if "Stop trying to start the vehicle?" in game.screen():
            game.keys("I", delay=0.8)
        if re.search(r"Engine\s+On", game.screen()):
            return
        game.keys("x", delay=1.0)
    raise AssertionError("the vehicle engine never started:\n" + game.screen())


def test_dashboard_driving_facts_fit_80x25(_game):
    game = dashboard_game("bn-e2e-dashboard")
    try:
        spawn_vehicle(game)
        screen = game.screen()
        _, title = title_row(screen)
        assert re.search(r"0 mph N$", summary(title)), \
            "the title must keep speed and heading:\n" + title
        speed_row = row_text(screen, "Speed")
        assert re.search(BAR, speed_row), speed_row
        assert not re.search(r"\d", speed_row), \
            "the speed number belongs to the title, not a duplicate body row:\n" + speed_row
        assert re.search(r"Cruise\s+Off", row_text(screen, "Cruise")), screen
        assert re.search(r"Heading\s+0°", row_text(screen, "Heading")), screen
        assert not re.search(r"\bN\b", row_text(screen, "Heading")), \
            "the cardinal belongs to the title, not a duplicate body row:\n" + screen
        assert re.search(r"Engine\s+Off", row_text(screen, "Engine")), screen
        assert re.search(r"gasoline\s+" + BAR + r"\s+\d+%",
                         row_text(screen, "gasoline"), re.IGNORECASE), screen
        assert re.search(r"battery\s+" + BAR + r"\s+\d+%",
                         row_text(screen, "battery"), re.IGNORECASE), screen
        # The floating window replaces the sidebar readout; nothing shows it twice.
        assert "fuel:" not in screen and "mph :" not in screen, screen

        take_control(game)
        game.keys("w", delay=1.2)
        game.keys("x", delay=0.8)
        screen = game.screen()
        assert re.search(r"Engine\s+On", row_text(screen, "Engine")), screen
        moving = speed_of(screen)
        assert moving > 0, "driving must update the dashboard speed:\n" + screen
        cruise = re.search(r"Cruise\s+On\s+(\d+) mph", row_text(screen, "Cruise"))
        assert cruise and int(cruise.group(1)) > 0, "the cruise target must read as ON:\n" + screen
        assert not re.search(r"\d", row_text(screen, "Speed")), \
            "the body speed row carries the bar only:\n" + screen

        # The minimum supported terminal: the window fits beside the 44-cell sidebar, every row
        # inside its borders, and nothing spills into the sidebar.
        game.resize(80, 25)
        game.settle_screen(minimum=0.6, timeout=3)
        screen = game.screen()
        left, right, title_y = window_columns(screen)
        assert 0 <= left < right < 36, f"the dashboard must stay on the map: {left}..{right}"
        _, title = title_row(screen)
        assert re.search(r"\d+ mph N$", summary(title)), title
        for needle in ("Speed", "Cruise", "Heading", "Engine", "gasoline", "battery"):
            row_text(screen, needle)
        assert re.search(BAR, row_text(screen, "Speed")), screen
        assert screen.splitlines()[title_y][right] == "│", screen
    finally:
        game.close()


def test_dashboard_fuel_warning_is_worded(_game):
    game = dashboard_game("bn-e2e-dashboard-fuel")
    try:
        spawn_vehicle(game)

        def fuel_left():
            return int(game.lua(
                "out(M:get_vehicle_fuel_left_at(here(0,0),'CONTROLS',"
                "ItypeId.new('gasoline')))")[0])

        def drain(amount):
            assert int(game.lua(
                f"out(M:drain_vehicle_fuel_at(here(0,0),'CONTROLS',"
                f"ItypeId.new('gasoline'),{amount}))")[0]) > 0

        start = fuel_left()
        assert start > 0, "the spawned car must be fuelled"
        drain(start * 85 // 100)
        game.keys("x", delay=0.8)
        screen = game.screen()
        low = re.search(r"gasoline\s+" + BAR + r"\s+(\d+)%\s+low",
                        row_text(screen, "gasoline"), re.IGNORECASE)
        assert low and 6 <= int(low.group(1)) <= 20, \
            "a 6-20% tank must say low without colour:\n" + screen

        drain(fuel_left())
        game.keys("x", delay=0.8)
        screen = game.screen()
        empty = row_text(screen, "gasoline")
        assert re.search(r"gasoline\s+-{6}\s+0%\s+empty", empty, re.IGNORECASE), empty
        assert re.search(r"battery\s+" + BAR + r"\s+\d+%",
                         row_text(screen, "battery"), re.IGNORECASE), \
            "the battery reading must not disappear with the empty tank:\n" + screen
    finally:
        game.close()


def test_dashboard_aircraft_takeoff_state(_game):
    game = dashboard_game("bn-e2e-dashboard-aircraft")
    try:
        spawn_vehicle(game, "plane_small")
        screen = game.screen()
        takeoff = re.search(r"Takeoff\s+(\d+) mph\s+no lift", row_text(screen, "Takeoff"))
        assert takeoff and int(takeoff.group(1)) > 0, \
            "the dashboard must keep the takeoff speed and its inactive state:\n" + screen
        needed = int(takeoff.group(1))

        take_control(game)
        for _ in range(30):
            if re.search(r"Takeoff\s+\d+ mph\s+lift", game.screen()):
                break
            game.keys("w", delay=0.8)
        screen = game.screen()
        assert re.search(r"Takeoff\s+\d+ mph\s+lift", row_text(screen, "Takeoff")), \
            "reaching takeoff speed must read lift without relying on colour:\n" + screen
        assert speed_of(screen) >= needed, screen
    finally:
        game.close()


def test_dashboard_remote_control(_game):
    game = remote_vehicle_game("bn-e2e-dashboard-remote", HUD_WINDOWS="true",
                               HUD_ICONS="ascii", SHOW_WELCOME="false")
    try:
        enter_remote_control(game)
        screen = game.screen()
        title_row(screen)
        assert row_text(screen, "Remote control").strip() == "Remote control", screen
        assert re.search(BAR, row_text(screen, "Speed")), screen
        assert re.search(r"Cruise\s+\S", row_text(screen, "Cruise")), screen
        assert re.search(r"Heading\s+\d+°", row_text(screen, "Heading")), screen
        assert re.search(r"Engine\s+\S", row_text(screen, "Engine")), screen
        assert re.search(r"(?:gasoline|battery)\s+" + BAR, screen, re.IGNORECASE), screen
    finally:
        game.close()


def test_dashboard_unicode_icons_kmh_and_low_fuel(_game):
    """Unicode icons, km/h units and a 6-20% warning share one live cluster."""
    game = dashboard_game("bn-e2e-dashboard-unicode", HUD_ICONS="unicode",
                          USE_METRIC_SPEEDS="km/h")
    try:
        spawn_vehicle(game)
        screen = game.screen()
        _, title = title_row(screen)
        assert re.search(r"0 km/h N$", summary(title)), title
        assert re.search(r"⊕\s+Heading\s+0°", row_text(screen, "Heading")), screen
        assert "▤" in row_text(screen, "gasoline"), screen
        assert "↯" in row_text(screen, "battery"), screen
        assert not re.search(r"\d", row_text(screen, "Speed")), \
            "the icon column must not change the bar-only body row:\n" + screen

        left = int(game.lua(
            "out(M:get_vehicle_fuel_left_at(here(0,0),'CONTROLS',"
            "ItypeId.new('gasoline')))")[0])
        assert left > 0
        assert int(game.lua(
            f"out(M:drain_vehicle_fuel_at(here(0,0),'CONTROLS',"
            f"ItypeId.new('gasoline'),{left * 85 // 100}))")[0]) > 0
        game.keys("x", delay=0.8)
        screen = game.screen()
        low = re.search(r"▤\s+gasoline\s+" + BAR + r"\s+(\d+)%\s+low",
                        row_text(screen, "gasoline"), re.IGNORECASE)
        assert low and 6 <= int(low.group(1)) <= 20, \
            "the fuel glyph and the low word must both show:\n" + screen
    finally:
        game.close()


def test_dashboard_leaves_compact_readout_alone(_game):
    # HUD_VEHICLE_BOX=off keeps the map box out of the way, so the sidebar readout is what shows.
    game = dashboard_game("bn-e2e-dashboard-compact", HUD_WINDOWS="false", HUD_VEHICLE_BOX="off")
    try:
        spawn_vehicle(game)
        screen = game.screen()
        assert not any("Vehicle" in line and ("[-]" in line or "[+]" in line)
                       for line in screen.splitlines()), \
            "the floating window must not exist with HUD_WINDOWS off:\n" + screen
        assert "fuel:" in screen and re.search(r"mph\s*:\s*0", screen), \
            "the compact sidebar readout must return:\n" + screen
        assert not re.search(r"(?:Heading|Cruise)\s+\S", screen), screen
    finally:
        game.close()


TESTS = [
    test_dashboard_driving_facts_fit_80x25,
    test_dashboard_fuel_warning_is_worded,
    test_dashboard_aircraft_takeoff_state,
    test_dashboard_remote_control,
    test_dashboard_unicode_icons_kmh_and_low_fuel,
    test_dashboard_leaves_compact_readout_alone,
]
