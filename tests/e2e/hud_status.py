import json
import os
import re
import subprocess
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from helpers import HELPERS, arena, empty_inventory, give
from options_menu import open_options
from tmux_game import Game, start_new_game


NEEDS = ("Pain", "Thirst", "Hunger", "Rest", "Heat")
LOADOUT = ("Weapon", "Style", "Stance")
SIDEBAR_WIDTH = 44
# Keep Needs visible at minimum height.
LABEL_PANELS = ("Needs", "Movement", "Location", "Weapon", "Controls", "Log",
                "Hint", "Limbs", "Body", "Mana", "Stats", "Vehicle", "Wind",
                "Location Alt", "Wgt/Vol", "Sound", "Moon", "Armor", "comp.Armor",
                "Compass", "Comp.Compass", "Sim.Compass", "Map", "AI Needs")


@contextmanager
def hud_game(tag, moon=False, **options):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-hud-status-"))
    config = userdir / "config"
    config.mkdir()
    enabled = {"Needs", "Movement", "Location", "Weapon", "Controls", "Log"}
    if moon:
        enabled.add("Moon")
    # Wide Moon can overwrite the phase.
    layout = "labels-narrow" if moon else "labels"
    (config / "panel_options.json").write_text(json.dumps([{
        "current_layout_id": layout,
        "layouts": [{"layout_id": layout, "panels": [
            {"name": name, "toggle": name in enabled} for name in LABEL_PANELS
        ]}],
    }]))
    game = Game(name=f"bn-e2e-hud-{tag}-{os.getpid()}", cols=140, rows=45,
                userdir=userdir,
                options={"SAFEMODE": "false", "SHOW_WELCOME": "false",
                         "SHOW_TIPS": "false", "CONTROL_SCHEME": "modern",
                         "SIDEBAR_POSITION": "right", "SIDEBAR_SPACERS": "false",
                         "HUD_WEATHER_BOX": "off", "HUD_COMBAT_BOX": "off",
                         "HUD_VEHICLE_BOX": "off", "HUD_ICONS": "ascii",
                         "ANIMATIONS": "false",
                         "24_HOUR": "24h", "USE_CELSIUS": "celsius",
                         "YN_HOTKEYS": "false", "CHRONIC_PAIN": "false", **options})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        empty_inventory(game)
        arena(game)
        healthy(game)
        yield game
    finally:
        game.close()


def healthy(game):
    assert game.lua("local a=gapi.get_avatar() a:clear_effects() "
                    "a:set_all_parts_hp_to_max() a:set_painkiller(0) a:set_pain(0) "
                    "a:set_thirst(40) a:set_fatigue(0) a:set_sleep_deprivation(0) "
                    "a:set_stored_kcal(a:max_stored_kcal()) "
                    "a:set_temp_celsius(Temperature.from_celsius(37)) "
                    "out(a:get_perceived_pain(),a:get_thirst(),a:get_fatigue())") == ["0,40,0"]


def cell_width(text):
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
               for char in text)


def regions(screen, cols=140, sidebar_width=SIDEBAR_WIDTH):
    terrain, sidebar = [], []
    for line in screen.splitlines():
        column, split = 0, 0
        for index, char in enumerate(line):
            if column >= cols - sidebar_width:
                break
            column += cell_width(char)
            split = index + 1
        terrain.append(line[:split])
        sidebar.append(line[split:])
    return "\n".join(terrain), "\n".join(sidebar)


def fields(text, labels, separator):
    result = {}
    positions = []
    value_columns = []
    for label in labels:
        pattern = r"\b" + re.escape(label) + r"[ \t]*" + separator + r"[ \t]*([^│\n]*)"
        found = list(re.finditer(pattern, text))
        assert len(found) == 1, f"expected one {label} field:\n{text}"
        result[label] = found[0].group(1).strip()
        assert result[label] and re.search(r"\w", result[label]), \
            f"{label} needs an explicit readable value:\n{text}"
        positions.append(found[0].start())
        prefix = text[text.rfind("\n", 0, found[0].start(1)) + 1:found[0].start(1)]
        value_columns.append(cell_width(prefix))
    rows = [text.count("\n", 0, position) for position in positions]
    assert rows == list(range(rows[0], rows[0] + len(labels))), \
        f"fields must occupy consecutive rows in user order:\n{text}"
    assert len(set(value_columns)) == 1, f"values need a fixed aligned column:\n{text}"
    return result


def sidebar_needs(screen, cols=140):
    return fields(regions(screen, cols)[1], NEEDS, ":")


def status_needs(screen, cols=140):
    terrain, sidebar = regions(screen, cols)
    loadout = fields(terrain, LOADOUT, r"\|")
    needs = fields(terrain, NEEDS, r"\|")
    assert not any(re.search(r"\b" + label + r"\s*:", sidebar) for label in NEEDS), \
        "Status must own Needs without a sidebar duplicate:\n" + screen
    assert loadout["Weapon"] and loadout["Style"] and loadout["Stance"]
    return needs


def counters(game):
    return game.lua("out(gapi.current_turn():to_turn(),gapi.get_avatar():get_moves())")


def resized_frame(game, cols, rows, ready, timeout=10.0):
    """Wait for a complete resize repaint, not its first visible Needs row."""
    deadline = time.time() + timeout
    previous, screen = None, ""
    while time.time() < deadline:
        screen = game.screen()
        if len(screen.splitlines()) == rows and ready(screen) and screen == previous:
            return screen
        previous = screen
        time.sleep(0.1)
    raise AssertionError(f"the {cols}x{rows} resize did not settle:\n" + screen)


def set_hud_option(game, label, value):
    """Observe the first saved frame without an extra redraw."""
    open_options(game)
    header = next(((line.index("[Interface]") + 2, y)
                   for y, line in enumerate(game.screen().splitlines())
                   if "[Interface]" in line), None)
    assert header is not None, game.screen()
    game.click(*header)
    for _ in range(180):
        screen = game.screen()
        rows = [(line.index(label), y, line)
                for y, line in enumerate(screen.splitlines())
                if re.search(r"│\s*\d+\s*│\s*(?:>>\s*)?" + re.escape(label) + r"\s*│", line)]
        if rows:
            x, y, _line = rows[0]
            game.hover(x, y)
            for _ in range(8):
                match = re.search(re.escape(label) + r"\s*│\s*([^│]*)", game.screen())
                if match and match.group(1).strip() == value:
                    break
                game.keys("Right", delay=0.3)
            else:
                raise AssertionError(f"could not set {label} to {value}:\n" + game.screen())
            break
        selected = next((line for line in screen.splitlines() if ">>" in line), "")
        if re.search(r">>\s*\+", selected):
            game.keys("Right", delay=0.1)
        game.keys("Down", delay=0.05)
    else:
        raise AssertionError(f"could not locate option {label}:\n" + game.screen())
    game.keys("Escape", delay=0.5)
    game.wait_for("Save changes?")
    game.keys("y", "Enter", delay=0.7)
    if "MAIN MENU" in game.screen():
        game.keys("Escape", delay=0.7)
    return game.screen()


def test_status_fixed_needs_and_text_modes(_g):
    with hud_game("meaning") as game:
        baseline = sidebar_needs(game.screen())
        assert all(re.search(r"[A-Za-z]", baseline[label]) for label in ("Pain", "Rest")), \
            "zero pain and fatigue need explicit healthy words, not a blank or a bare zero"
        before = counters(game)
        screen = set_hud_option(game, "Status box", "Top left")
        assert status_needs(screen) == baseline, screen
        screen = set_hud_option(game, "Box icons", "Unicode")
        assert status_needs(screen) == baseline, screen
        assert counters(game) == before, "HUD options must not spend a turn or moves"

        # Use sidebar descriptors as the oracle.
        set_hud_option(game, "Status box", "Off")
        assert game.lua("local a=gapi.get_avatar() a:set_thirst(400) "
                        "a:set_fatigue(400) a:set_pain(60) "
                        "out(a:get_thirst(),a:get_fatigue(),a:get_perceived_pain())") == ["400,400,60"]
        warning = sidebar_needs(game.screen())
        for label in ("Pain", "Thirst", "Rest"):
            assert warning[label] != baseline[label], f"{label} did not reflect its warning state"
        for label in ("Hunger", "Heat"):
            assert warning[label] == baseline[label], f"warning leaked into {label}"
        before = counters(game)
        screen = set_hud_option(game, "Status box", "Top left")
        assert status_needs(screen) == warning, screen
        screen = set_hud_option(game, "Box icons", "Text only")
        assert status_needs(screen) == warning, screen
        assert counters(game) == before, "presentation changes must not alter gameplay time"
        healthy(game)
        assert status_needs(game.screen()) == baseline, "healthy Pain/Rest must recover explicit values"
        # Neutral thirst is not Hydrated.
        assert game.lua("gapi.get_avatar():set_thirst(90) "
                        "out(gapi.get_avatar():get_thirst())") == ["90"]
        neutral = status_needs(game.screen())
        assert neutral["Thirst"] != baseline["Thirst"], "neutral thirst must not claim Hydrated"
        screen = set_hud_option(game, "Status box", "Off")
        assert sidebar_needs(screen) == neutral, screen


def test_status_toggle_refresh_restores_sidebar_needs(_g):
    with hud_game("refresh") as game:
        baseline = sidebar_needs(game.screen())
        before = counters(game)
        for _ in range(2):
            screen = set_hud_option(game, "Status box", "Top left")
            assert status_needs(screen) == baseline, screen
            screen = set_hud_option(game, "Status box", "Off")
            assert sidebar_needs(screen) == baseline, screen
            assert not re.search(r"\bWeapon\s*\|", regions(screen)[0]), screen
        assert counters(game) == before, "toggling Status must not spend a turn or moves"


def test_status_short_narrow_fallback_retains_needs(_g):
    with hud_game("fit", HUD_WEATHER_BOX="top_left", HUD_COMBAT_BOX="top_left") as game:
        baseline = status_needs(game.screen())
        loadout = fields(regions(game.screen())[0], LOADOUT, r"\|")
        before = counters(game)
        for icon_mode in ("Text only", "Unicode"):
            if icon_mode == "Unicode":
                set_hud_option(game, "Box icons", icon_mode)
            for cols, rows in ((90, 25), (100, 25), (140, 45)):
                subprocess.run(["tmux", "resize-window", "-t", game.name,
                                "-x", str(cols), "-y", str(rows)], check=True)
                sidebar_owns = rows == 25

                def ready(screen, cols=cols, sidebar_owns=sidebar_owns):
                    pattern = r"\bPain\s*:" if sidebar_owns else r"\bPain\s*\|"
                    return re.search(pattern, regions(screen, cols)[1 if sidebar_owns else 0])

                screen = resized_frame(game, cols, rows, ready)
                if rows == 25:
                    terrain, sidebar = regions(screen, cols)
                    assert sidebar_needs(screen, cols) == baseline, screen
                    assert not re.search(r"\bPain\s*\|", terrain), screen
                    if re.search(r"\bWeapon\s*\|", terrain):
                        fields(terrain, LOADOUT, r"\|")
                    else:
                        fallback = fields(sidebar, ("Wield", "Style"), ":")
                        assert fallback["Wield"] == loadout["Weapon"], screen
                        assert fallback["Style"] == loadout["Style"], screen
                    weather_rows(screen, cols)
                else:
                    assert status_needs(screen, cols) == baseline, screen
        assert counters(game) == before, "resize must not consume turns or moves"


def weather_rows(screen, cols=140, sidebar_width=SIDEBAR_WIDTH):
    terrain = regions(screen, cols, sidebar_width)[0].splitlines()
    light = [y for y, line in enumerate(terrain) if re.search(r"\bLight\s*:", line)]
    assert len(light) == 1, screen
    y = light[0]
    line = terrain[y]
    left, right = line.index("│"), line.rindex("│")
    assert right > left, screen
    rows = [row[left + 1:right].strip() for row in terrain[y - 2:y + 2]]
    assert all(char in "─┌┐└┘╭╮╰╯" for char in terrain[y - 3][left:right + 1]), screen
    assert all(char in "─┌┐└┘╭╮╰╯" for char in terrain[y + 2][left:right + 1]), screen
    assert all(rows), screen
    assert re.search(r"\bLight\s*:\s*\S", rows[2]), screen
    assert re.search(r"\bWind\s*:\s*\S", rows[3]), screen
    return rows


def moon_phase(screen, cols=140):
    """Use the narrow Moon panel as the phase oracle."""
    sidebar = regions(screen, cols, 32)[1]
    found = re.search(r"\bMoon\s*:\s*([^\n]+)", sidebar)
    assert found and found.group(1).strip(), screen
    return found.group(1).strip()


def date_reading(game):
    season, date, clock = game.lua("local t=gapi.current_turn() out(t:season()) "
                                   "out(tostring(t)) out(t:to_string_time_of_day())")
    # Read the day without assuming season length.
    day = re.search(re.escape(season) + r"\D+(\d+)", date)
    assert day, date
    return season, day.group(1), clock


def assert_weather_date(row, season, day, phase):
    assert re.search(re.escape(season) + r"\D*" + day + r"\b", row), row
    assert phase in row, f"the full sidebar moon phase must survive the combined row: {row!r}"


def test_weather_four_rows_and_instrument_gates(_g):
    with hud_game("weather", moon=True, HUD_WEATHER_BOX="top_left") as game:
        assert game.lua("out(gapi.get_avatar():has_watch())") == ["false"]
        season, day, clock = date_reading(game)
        phase = moon_phase(game.screen())
        clock_pattern = r"\b\d{1,2}:\d{2}(?::\d{2})?\b"
        temperature_pattern = r"[-+]?\d+(?:\.\d+)?\s*°\s*[CFK]"
        initial = weather_rows(game.screen(), sidebar_width=32)
        assert_weather_date(initial[1], season, day, phase)
        assert not re.search(clock_pattern, initial[1]), "no watch must mean approximate time"
        assert not re.search(temperature_pattern, initial[0]), "temperature leaked without an instrument"

        give(game, "thermometer")
        measured = weather_rows(game.screen(), sidebar_width=32)
        assert re.search(temperature_pattern, measured[0]), measured
        assert_weather_date(measured[1], season, day, phase)
        assert not re.search(clock_pattern, measured[1]), "a thermometer must not reveal exact time"
        give(game, "pocketwatch")
        assert game.lua("out(gapi.get_avatar():has_watch())") == ["true"]
        equipped = weather_rows(game.screen(), sidebar_width=32)
        assert_weather_date(equipped[1], season, day, phase)
        assert clock in equipped[1], "the combined date/time row must preserve the existing clock including seconds"
        before = counters(game)
        for mode in ("Unicode", "Text only"):
            screen = set_hud_option(game, "Box icons", mode)
            icon_rows = weather_rows(screen, sidebar_width=32)
            assert_weather_date(icon_rows[1], season, day, moon_phase(screen))
            assert clock in icon_rows[1], icon_rows
            assert re.search(temperature_pattern, icon_rows[0]).group() == \
                re.search(temperature_pattern, equipped[0]).group(), icon_rows
            assert equipped[0].removeprefix("Weather: ") in icon_rows[0], icon_rows
            assert re.sub(r"^.*?Light:", "Light:", icon_rows[2]) == equipped[2], icon_rows
            assert icon_rows[3].rsplit(" ", 1)[0] == equipped[3].rsplit(" ", 1)[0], icon_rows
            assert counters(game) == before, "changing weather icons must not advance time"
        for cols, rows in ((90, 25), (140, 45)):
            subprocess.run(["tmux", "resize-window", "-t", game.name,
                            "-x", str(cols), "-y", str(rows)], check=True)

            def ready(screen, cols=cols):
                terrain, sidebar = regions(screen, cols, 32)
                return re.search(r"\bLight\s*:", terrain) and \
                    re.search(r"\bMoon\s*:\s*\S", sidebar)

            screen = resized_frame(game, cols, rows, ready)
            resized = weather_rows(screen, cols, 32)
            assert_weather_date(resized[1], season, day, moon_phase(screen, cols))
            assert clock in resized[1], resized
        assert counters(game) == before, "resize must not advance time"
        empty_inventory(game)
        assert game.lua("out(gapi.get_avatar():has_watch())") == ["false"]
        unequipped = weather_rows(game.screen(), sidebar_width=32)
        assert_weather_date(unequipped[1], season, day, moon_phase(game.screen()))
        assert not re.search(clock_pattern, unequipped[1]), unequipped
        assert not re.search(temperature_pattern, unequipped[0]), unequipped


def test_weather_underground_time_knowledge(_g):
    with hud_game("underground", HUD_WEATHER_BOX="top_left") as game:
        assert game.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() p.z=-1 "
                        "gapi.place_player_local_at(p) out(a:get_pos_ms().z,a:has_watch())") == ["-1,false"]
        arena(game)
        season, day, clock = date_reading(game)
        unknown = weather_rows(game.screen())
        assert "???" in unknown[1], unknown
        assert clock not in unknown[1], unknown
        give(game, "pocketwatch")
        known = weather_rows(game.screen())
        assert clock in known[1] and "???" not in known[1], known
        before = counters(game)
        icon_rows = weather_rows(set_hud_option(game, "Box icons", "Unicode"))
        assert clock in icon_rows[1] and "???" not in icon_rows[1], icon_rows
        empty_inventory(game)
        unknown = weather_rows(game.screen())
        assert "???" in unknown[1] and clock not in unknown[1], unknown
        assert re.search(re.escape(season) + r"\D*" + day + r"\b", unknown[1]), unknown
        assert counters(game) == before, "time knowledge changes must not spend a turn"


def test_weather_text_wind_origin_matches_instrument(_g):
    with hud_game("wind-origin", HUD_WEATHER_BOX="top_left") as game:
        origins = game.lua(
            "local a=gapi.get_avatar() local it=a:create_item(ItypeId.new('weather_reader'),-1) "
            "it:ammo_set(ItypeId.new('battery'),100) it:invoke_at(a:get_pos_ms()) "
            "for _,message in ipairs(gapi.get_messages(20)) do "
            "local origin=message.text:match('from the ([%a%-]+)%.') "
            "if origin then out(origin) end end")
        assert len(origins) == 1, origins
        # Keep the oracle independent of the arrow table.
        expected = "".join(word[0].upper() for word in origins[0].split("-"))
        wind = weather_rows(game.screen())[3]
        assert wind.rsplit(" ", 1)[-1] == expected, (wind, origins)
        before = counters(game)
        unicode_rows = weather_rows(set_hud_option(game, "Box icons", "Unicode"))
        assert unicode_rows[3].rsplit(" ", 1)[0] == wind.rsplit(" ", 1)[0], unicode_rows
        text_rows = weather_rows(set_hud_option(game, "Box icons", "Text only"))
        assert text_rows[3].rsplit(" ", 1)[-1] == expected, (text_rows, origins)
        assert counters(game) == before, "changing the wind display must not advance time"


TESTS = [test_status_fixed_needs_and_text_modes,
         test_status_toggle_refresh_restores_sidebar_needs,
         test_status_short_narrow_fallback_retains_needs,
         test_weather_four_rows_and_instrument_gates,
         test_weather_underground_time_knowledge,
         test_weather_text_wind_origin_matches_instrument]
