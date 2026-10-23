import json
import re
import subprocess
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from helpers import HELPERS, action_menu, arena, choose_menu_entry, empty_inventory, give
from options_menu import open_options
from hud_boxes import SKY_TRACK, sky_track
from fixtures import retire, shared_game


NEEDS = ("Pain", "Thirst", "Hunger", "Rest", "Body temp")
SIDEBAR_WIDTH = 44
# Keep Needs visible at minimum height.
LABEL_PANELS = ("Needs", "Movement", "Location", "Weapon", "Controls", "Log",
                "Hint", "Limbs", "Body", "Mana", "Stats", "Vehicle", "Wind",
                "Location Alt", "Wgt/Vol", "Sound", "Moon", "Armor", "comp.Armor",
                "Compass", "Comp.Compass", "Sim.Compass", "Map", "AI Needs")


_layouts = {}


def layout_userdir(moon, options):
    """Seed each option profile independently, including after retirement deletes its directory."""
    key = (moon, tuple(sorted(options.items())))
    if key not in _layouts or not (_layouts[key] / "config" / "panel_options.json").exists():
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
        _layouts[key] = userdir
    return _layouts[key]


def hud_setup(game):
    # A test may leave the pane or the avatar changed; both are part of the profile's start.
    game.resize(140, 45)
    empty_inventory(game)
    arena(game)
    healthy(game)
    action_menu(game, "Combat", "Select Martial Arts Style")
    game.wait_for("Select a style.")
    choose_menu_entry(game, "No style")
    game.wait_gone("Select a style.")


@contextmanager
def hud_game(tag, moon=False, **options):
    with shared_game(f"bn-e2e-hud-{tag}", cols=140, rows=45, userdir=layout_userdir(moon, options),
                     define=HELPERS, setup=hud_setup,
                     options={"SAFEMODE": "false", "SHOW_WELCOME": "false",
                              "SHOW_TIPS": "false", "CONTROL_SCHEME": "modern",
                              "SIDEBAR_POSITION": "right", "SIDEBAR_SPACERS": "false",
                              "HUD_WEATHER_BOX": "off", "HUD_COMBAT_BOX": "off",
                              "HUD_VEHICLE_BOX": "off", "HUD_ICONS": "ascii",
                              "ANIMATIONS": "false",
                              "24_HOUR": "24h", "USE_CELSIUS": "celsius",
                              "YN_HOTKEYS": "false", "CHRONIC_PAIN": "false", **options}) as game:
        game.options_changed = False
        yield game
        # The profile's options are the key the game is shared under; once a test changed one
        # in-game, the game no longer matches its profile.
        if game.options_changed:
            retire(game)


def healthy(game):
    assert game.lua("local a=gapi.get_avatar() a:vomit() a:clear_effects() "
                    "a:set_all_parts_hp_to_max() a:set_painkiller(0) a:set_pain(0) "
                    "a:set_thirst(40) a:set_fatigue(0) a:set_sleep_deprivation(0) "
                    "a:set_stored_kcal(a:max_stored_kcal()-100) "
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


def status_box(screen, cols=140):
    terrain = regions(screen, cols)[0].splitlines()
    stance = next((y for y, line in enumerate(terrain) if "Walking" in line), None)
    assert stance is not None, "the status box must show the stance:\n" + screen
    top = max(y for y in range(stance) if terrain[y].startswith("╭"))
    bottom = next(y for y in range(stance + 1, len(terrain)) if terrain[y].startswith("╰"))
    return "\n".join(line[:line.index("│", 1) + 1] if line.startswith("│") else line
                     for line in terrain[top:bottom + 1])


def status_needs(screen, cols=140, expected=None):
    """Only pressing needs belong in Status; the sidebar remains the descriptor oracle."""
    expected = expected or {}
    box = status_box(screen, cols)
    sidebar = regions(screen, cols)[1]
    assert "No style" not in box, box
    assert not re.search(r"\bStyle\s*\|", box), "an unset style must not occupy a row:\n" + box
    for label in NEEDS:
        assert not re.search(r"\b" + label + r"\s*:", sidebar), \
            "Status must own Needs without a sidebar duplicate:\n" + screen
        if label in expected:
            assert expected[label] in box, f"{label} warning disappeared:\n{box}"
        else:
            assert not re.search(r"\b" + label + r"\s*\|", box), \
                f"healthy {label} must not occupy a row:\n{box}"
    assert ("Needs met" in box) == (not expected), box
    return expected


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
    game.options_changed = True
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
        before = counters(game)
        status_needs(set_hud_option(game, "Status box", "Top left"))
        status_needs(set_hud_option(game, "Box icons", "Unicode"))
        assert counters(game) == before, "HUD options must not spend a turn or moves"

        set_hud_option(game, "Status box", "Off")
        assert game.lua("local a=gapi.get_avatar() a:set_thirst(400) "
                        "a:set_fatigue(400) a:set_pain(60) "
                        "out(a:get_thirst(),a:get_fatigue(),a:get_perceived_pain())") == ["400,400,60"]
        warning = sidebar_needs(game.screen())
        pressing = {label: warning[label] for label in ("Pain", "Thirst", "Rest")}
        for label, value in pressing.items():
            assert value != baseline[label], f"{label} did not reflect its warning state"
        for label in ("Hunger", "Body temp"):
            assert warning[label] == baseline[label], f"warning leaked into {label}"
        before = counters(game)
        status_needs(set_hud_option(game, "Status box", "Top left"), expected=pressing)
        status_needs(set_hud_option(game, "Box icons", "Text only"), expected=pressing)
        assert counters(game) == before, "presentation changes must not alter gameplay time"
        healthy(game)
        status_needs(game.screen())
        # Neither neutral thirst nor hydration asks the player to do anything.
        assert game.lua("gapi.get_avatar():set_thirst(90) out('ok')") == ["ok"]
        status_needs(game.screen())
        screen = set_hud_option(game, "Status box", "Off")
        assert sidebar_needs(screen)["Thirst"] != baseline["Thirst"], screen


def test_status_toggle_refresh_restores_sidebar_needs(_g):
    with hud_game("refresh") as game:
        baseline = sidebar_needs(game.screen())
        before = counters(game)
        for _ in range(2):
            status_needs(set_hud_option(game, "Status box", "Top left"))
            screen = set_hud_option(game, "Status box", "Off")
            assert sidebar_needs(screen) == baseline, screen
            assert not re.search(r"\bWeapon\s*\|", regions(screen)[0]), screen
        assert counters(game) == before, "toggling Status must not spend a turn or moves"


def test_status_short_narrow_fallback_retains_needs(_g):
    with hud_game("fit", HUD_WEATHER_BOX="top_left", HUD_COMBAT_BOX="top_left") as game:
        baseline = sidebar_needs(set_hud_option(game, "Status box", "Off"))
        status_needs(set_hud_option(game, "Status box", "Top left"))
        before = counters(game)
        for icon_mode in ("Text only", "Unicode"):
            if icon_mode == "Unicode":
                set_hud_option(game, "Box icons", icon_mode)
            for cols, rows in ((90, 25), (100, 25), (140, 45)):
                game.resize(cols, rows)

                def ready(screen, cols=cols):
                    terrain, sidebar = regions(screen, cols)
                    return ("Walking" in terrain and "Needs met" in terrain) or all(
                        re.search(r"\b" + label + r"\s*:", sidebar) for label in NEEDS)

                screen = resized_frame(game, cols, rows, ready)
                terrain, sidebar = regions(screen, cols)
                if re.search(r"\bPain\s*:", sidebar):
                    assert sidebar_needs(screen, cols) == baseline, screen
                    assert "Needs met" not in terrain, screen
                else:
                    status_needs(screen, cols)
                # Fit policy may keep a lean loadout box or return it to the sidebar.
                assert "Walking" in terrain or re.search(r"\bWield\s*:\s*\S", sidebar), screen
                weather_rows(screen, cols)
        assert counters(game) == before, "resize must not consume turns or moves"


def body_temp(game, celsius):
    """The moodle is the readback: Lua sets the body temperature, the HUD shows it."""
    assert game.lua("local a=gapi.get_avatar() "
                    f"a:set_temp_celsius(Temperature.from_celsius({celsius})) "
                    "out('set')") == ["set"]
    return game.screen()


def test_temperature_row_names_comfort_and_mild_chill_is_fine(_g):
    """Mild chill keeps Needs met; only the extremes press the row, in the cold direction."""
    with hud_game("bodytemp") as game:
        set_hud_option(game, "Status box", "Top left")
        screen = set_hud_option(game, "Box icons", "Unicode")
        assert "Needs met" in status_box(screen), screen
        screen = body_temp(game, 33)
        box = status_box(screen)
        assert "Needs met" in box, "a mildly chilly body asks for nothing:\n" + box
        assert "Body temp" not in box and "Chilly" not in box, box
        screen = body_temp(game, 29)
        box = status_box(screen)
        assert "Needs met" not in box, "a very cold body must press the row:\n" + box
        assert re.search(r"│\s*❄\s+Very cold", box), "the cold row needs its snowflake:\n" + box
        assert not re.search(r"\bHeat\b", box), "no row may call a cold body heat:\n" + box
        assert game.lua("local a=gapi.get_avatar() a:set_fatigue(400) out('ok')") == ["ok"]
        box = status_box(game.screen())
        assert re.search(r"│\s*z\s+Dead Tired", box), "Rest needs one glyph:\n" + box
        assert "zz" not in box, "the two-letter sleep glyph must be gone:\n" + box
        # The detailed panel keeps the full value under a neutral, direction-free label.
        assert sidebar_needs(set_hud_option(game, "Status box", "Off"))["Body temp"] == "Very cold!", \
            game.screen()
        assert not re.search(r"\bHeat\b", game.screen()), game.screen()


def weather_rows(screen, cols=140, sidebar_width=SIDEBAR_WIDTH):
    terrain = regions(screen, cols, sidebar_width)[0].splitlines()
    light = [y for y, line in enumerate(terrain) if re.search(r"\bLight\s*:", line)]
    assert len(light) == 1, screen
    y = light[0]
    line = terrain[y]
    left = line.index("│")
    # The nearest closing border, not the last one on the row: a bordered sidebar to the right
    # would otherwise become the box's right edge and pull map terrain into the rows.
    right = line.index("│", left + 1)
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


def assert_weather_date(row, season, day):
    assert re.search(re.escape(season) + r"\D*" + day + r"\b", row), row
    sky_track(row)


def test_weather_four_rows_and_instrument_gates(_g):
    with hud_game("weather", moon=True, HUD_WEATHER_BOX="top_left") as game:
        assert game.lua("out(gapi.get_avatar():has_watch())") == ["false"]
        season, day, clock = date_reading(game)
        clock_pattern = r"\b\d{1,2}:\d{2}(?::\d{2})?\b"
        temperature_pattern = r"[-+]?\d+(?:\.\d+)?\s*°\s*[CFK]"
        initial = weather_rows(game.screen(), sidebar_width=32)
        assert initial[1].startswith("t ") and initial[2].startswith("l Light:") and \
            initial[3].startswith("w Wind:"), initial
        assert_weather_date(initial[1], season, day)
        assert not re.search(clock_pattern, initial[1]), "no watch must mean approximate time"
        assert not re.search(temperature_pattern, initial[0]), "temperature leaked without an instrument"

        give(game, "thermometer")
        measured = weather_rows(game.screen(), sidebar_width=32)
        assert re.search(temperature_pattern, measured[0]), measured
        assert_weather_date(measured[1], season, day)
        assert not re.search(clock_pattern, measured[1]), "a thermometer must not reveal exact time"
        give(game, "pocketwatch")
        assert game.lua("out(gapi.get_avatar():has_watch())") == ["true"]
        equipped = weather_rows(game.screen(), sidebar_width=32)
        assert_weather_date(equipped[1], season, day)
        assert clock in equipped[1], "the combined date/time row must preserve the existing clock including seconds"
        before = counters(game)
        for mode, light_icon in (("Unicode", "⊙"), ("Text only", "l")):
            screen = set_hud_option(game, "Box icons", mode)
            icon_rows = weather_rows(screen, sidebar_width=32)
            assert_weather_date(icon_rows[1], season, day)
            assert clock in icon_rows[1], icon_rows
            assert re.search(temperature_pattern, icon_rows[0]).group() == \
                re.search(temperature_pattern, equipped[0]).group(), icon_rows
            assert equipped[0].split("Weather:", 1)[1].strip() in icon_rows[0], icon_rows
            assert icon_rows[2] == light_icon + " Light:" + equipped[2].split("Light:", 1)[1], icon_rows
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
            assert_weather_date(resized[1], season, day)
            assert clock in resized[1], resized
        assert counters(game) == before, "resize must not advance time"
        empty_inventory(game)
        assert game.lua("out(gapi.get_avatar():has_watch())") == ["false"]
        unequipped = weather_rows(game.screen(), sidebar_width=32)
        assert_weather_date(unequipped[1], season, day)
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
        assert not SKY_TRACK.search(unknown[1]), "the sky is hidden underground"
        give(game, "pocketwatch")
        known = weather_rows(game.screen())
        assert clock in known[1] and "???" not in known[1], known
        assert not SKY_TRACK.search(known[1]), "a watch must not reveal the underground sky"
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
        weather_rows(set_hud_option(game, "Box icons", "Unicode"))
        text_rows = weather_rows(set_hud_option(game, "Box icons", "Text only"))
        assert text_rows[3].rsplit(" ", 1)[-1] == expected, (text_rows, origins)
        assert counters(game) == before, "changing the wind display must not advance time"


def set_debug_turn(game, turn):
    """Use the real debug time editor; calendar mutation is not exposed to Lua."""
    game.keys("F12", delay=0.2)
    game.wait_for("Debug Functions")
    choose_menu_entry(game, "Map…")
    game.wait_for("Change time")
    choose_menu_entry(game, "Change time")
    game.keys("t", delay=0.2)
    game.wait_for("Set turn to?")
    game.keys("C-u", delay=0.1)
    game.type(str(turn))
    game.keys("Enter", delay=0.2)
    game.wait_for("hour:")
    game.keys("Escape", delay=0.2)
    game.wait_gone("hour:")


def test_sky_track_ascii_sun_and_new_moon_are_distinct(_g):
    with hud_game("sky-cycle", moon=True, HUD_WEATHER_BOX="top_left") as game:
        original = int(game.lua("out(gapi.current_turn():to_turn())")[0])
        try:
            set_debug_turn(game, 0)
            assert "New" in moon_phase(game.screen()), game.screen()
            night = sky_track(weather_rows(game.screen(), sidebar_width=32)[1])
            assert "o" in night and "*" not in night, "new moon must be the ASCII o:\n" + night
            positions = []
            for hour in (8, 12, 16):
                set_debug_turn(game, hour * 60 * 60)
                track = sky_track(weather_rows(game.screen(), sidebar_width=32)[1])
                assert "*" in track and "o" not in track, "the ASCII sun must be distinct from new moon:\n" + track
                positions.append(track.index("*"))
            assert positions[0] < positions[1] < positions[2], \
                "the sun must progress across the nine-cell track through the day"
            screen = set_hud_option(game, "Box icons", "Unicode")
            assert "☼" in sky_track(weather_rows(screen, sidebar_width=32)[1]), screen
        finally:
            set_debug_turn(game, original)


TESTS = [test_status_fixed_needs_and_text_modes,
         test_status_toggle_refresh_restores_sidebar_needs,
         test_status_short_narrow_fallback_retains_needs,
         test_temperature_row_names_comfort_and_mild_chill_is_fine,
         test_weather_four_rows_and_instrument_gates,
         test_weather_underground_time_knowledge,
         test_weather_text_wind_origin_matches_instrument,
         test_sky_track_ascii_sun_and_new_moon_are_distinct]
