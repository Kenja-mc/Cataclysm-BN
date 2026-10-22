"""The corner boxes, body panel and map glyphs that replace sidebar rows.

Tests that take `g` run on the runner's main game; box layouts start their own.
"""
import re

from helpers import action_menu, arena, bub_pos, settle
from tmux_game import Game, start_new_game

# src/panels_utility.cpp: four of the nine names carry no "moon" word at all.
MOON_PHASES = ("new moon", "waxing crescent", "half moon", "waxing gibbous", "full moon",
               "waning gibbous", "waning crescent", "dark moon")


def test_hud_box_options(g):
    """Each box moves to any corner or turns off; the ASCII choice renders labels, not icons."""
    other = Game(name="bn-e2e-hud", options={"SAFEMODE": "false", "HUD_WEATHER_BOX": "off",
                                             "HUD_COMBAT_BOX": "bottom_left", "HUD_ICONS": "ascii"})
    try:
        start_new_game(other)
        other.keys("x", delay=0.6)
        lines = other.screen().splitlines()
        assert not lines[0].startswith("╭"), "the weather box is off"
        bottom = [i for i, l in enumerate(lines) if l.startswith("╰")]
        assert bottom, "\n".join(lines)
        top_edge = max(i for i, l in enumerate(lines[:bottom[-1]]) if l.startswith("╭"))
        box = "\n".join(l[:40] for l in lines[top_edge:bottom[-1] + 1])
        assert "│ Weapon |" in box, "the bottom-left box must name the weapon:\n" + box
        assert "│ Stance |" in box, "the bottom-left box must name the stance:\n" + box
        assert not any(icon in box for icon in ("✶", "⚔", "☯", "•", "☹", "☕", "♨", "°", "✦")), \
            "ASCII icons must stay text:\n" + box
    finally:
        other.close()


def test_boxes_replace_sidebar_rows(g):
    """What the weather and weapon boxes show leaves the sidebar; turning the boxes off brings it back."""
    spend_mana = "local a=gapi.get_avatar() a:get_magic():set_mana(1) out('ok')"
    assert g.lua(spend_mana) == ["ok"]
    settle(g)
    s = g.screen()
    lines = s.splitlines()
    assert lines[0].startswith("╭"), "the box frame starts on the top line:\n" + s
    boxes = "\n".join(l[:40] for l in lines[:18])
    assert any(icon in boxes for icon in ("☼", "☾", "☁", "☂", "↯", "❄", "◎", "▼")), "weather icon: " + boxes
    for fact in ("Light:", "Wind:", "Weapon", "Mana"):
        assert fact in boxes, f"{fact} belongs in a box:\n" + boxes
    assert any(phase in boxes.lower() for phase in MOON_PHASES), \
        "box should show the moon phase: " + boxes
    assert re.search(r"(Spring|Summer|Autumn|Winter) \d+", boxes), \
        "box should show the season and day: " + boxes
    # tmux drops trailing blanks, so a short line is all map; the sidebar starts at column 96.
    sidebar = "\n".join(l[96:] for l in lines)
    assert re.search(r"Place\s*:", sidebar) and re.search(r"X,Y,Z\s*:", sidebar), s
    for label in ("Sky", "Light", "Date", "Time", "Wield", "Style", "Mana"):
        assert not re.search(label + r"\s*:", sidebar), f"{label} is in a box already:\n" + s
    off = Game(name="bn-e2e-env-off", options={"SAFEMODE": "false", "HUD_WEATHER_BOX": "off", "HUD_COMBAT_BOX": "off"})
    try:
        start_new_game(off)
        off.define_lua("")
        assert off.lua(spend_mana) == ["ok"]
        off.keys("x", delay=0.6)
        s2 = off.screen()
        assert not s2.splitlines()[0].startswith("╭"), "boxes should be off:\n" + s2
        sidebar2 = "\n".join(l[96:] for l in s2.splitlines())
        for label in ("Sky", "Light", "Date", "Time", "Wield", "Style"):
            assert re.search(label + r"\s*:", sidebar2), f"{label} should be back in the sidebar:\n" + s2
        assert re.search(r"Mana\s*: 1/\d+", sidebar2), "mana reads current/max:\n" + s2
    finally:
        off.close()


def test_corner_bars_keep_sidebar_panels(g):
    """HUD_CORNER_BARS puts each box on one row and leaves the sidebar panels in place."""
    bars = Game(name="bn-e2e-corner-bars",
                options={"SAFEMODE": "false", "HUD_CORNER_BARS": "true", "HUD_ICONS": "ascii"})
    try:
        start_new_game(bars)
        bars.keys("x", delay=0.6)
        s = bars.screen()
        lines = s.splitlines()
        weather = next((i for i, l in enumerate(lines) if "Weather:" in l), None)
        assert weather is not None, "the weather bar is missing:\n" + s
        row = lines[weather]
        assert "Light:" in row and "Wind:" in row, \
            "one weather row must hold every reading:\n" + row
        assert lines[weather - 1].startswith("╭"), "the weather bar is one row:\n" + \
            "\n".join(lines[weather - 1:weather + 2])
        assert lines[weather + 1].startswith("╰"), "the weather bar is one row:\n" + \
            "\n".join(lines[weather - 1:weather + 2])
        # The starting loadout varies (fists or a weapon), so the bar is found by its frame and stance.
        combat = next((i for i, l in enumerate(lines) if l.startswith("│") and "Walking" in l), None)
        assert combat is not None, "the status bar is missing:\n" + s
        row = lines[combat]
        # The row is checked for its shape: weapon, style and stance, separated by bars.
        assert "Walking" in row and row.count("│") >= 2, \
            "one status row must hold weapon, style and stance:\n" + row
        assert lines[combat - 1].startswith("╭") and lines[combat + 1].startswith("╰"), \
            "the status bar is one row:\n" + "\n".join(lines[combat - 1:combat + 2])
        sidebar = "\n".join(l[96:] for l in lines)
        assert re.search(r"Pain\s*:", sidebar), "the sidebar keeps its needs panel:\n" + s
    finally:
        bars.close()


def test_body_panel(g):
    arena(g)
    settle(g)
    s = g.screen()
    assert "No wounds" in s, s
    body = next(l for l in s.splitlines() if "No wounds" in l)
    coord = next(l for l in s.splitlines() if "X,Y,Z" in l)
    # The wound list starts on the same label grid as the Location panel, with no figure beside it.
    assert body.index("No wounds") == coord.index("X,Y,Z"), body + "\n" + coord
    g.lua("gapi.get_avatar():add_effect(EffectTypeId.new('bleed'), TimeDuration.from_minutes(30), BodyPartTypeId.new('arm_l'), 1) out('ok')")
    settle(g)
    assert "bleeding" in g.screen(), g.screen()
    action_menu(g, "Info", "Body status")
    details = g.screen()
    g.keys("Escape", delay=0.8)
    g.lua("gapi.get_avatar():remove_effect(EffectTypeId.new('bleed'), BodyPartTypeId.new('arm_l')) out('ok')")
    assert "bleeding" in details and "disinfectant" in details, details
    settle(g)
    assert "No wounds" in g.screen(), g.screen()


def test_readable_map_glyphs(g):
    """Trees and saplings draw as ♣ and τ instead of digits."""
    arena(g)
    # Right next to the character, so even a dark start can see them.
    g.lua("M:set_ter_at(here(-1,-1), TerId.new('t_tree'):int_id()) M:set_ter_at(here(1,-1), TerId.new('t_tree_young'):int_id()) out('ok')")
    settle(g)
    s = g.screen()
    g.lua("M:set_ter_at(here(-1,-1), TerId.new('t_floor'):int_id()) M:set_ter_at(here(1,-1), TerId.new('t_floor'):int_id()) out('ok')")
    # Read the row from the same capture: a fresh screen can have scrolled by a line.
    y = next(i for i, line in enumerate(s.splitlines()) if "@" in line)
    row = s.splitlines()[y - 1]
    assert "♣" in row and "τ" in row, "\n".join(s.splitlines()[y - 2:y + 2])


def test_stance_toggle(g):
    """The stance key cycles every mode, refreshes the Status box and never moves the player."""
    arena(g)
    g.lua("gapi.get_avatar():set_movement_mode(CharacterMoveMode.walk) out('ok')")
    settle(g)
    before = bub_pos(g)
    # Crouching and standing back up spend moves upstream; only the cycle itself is asserted here.
    for mode, label in (("run", "Running"), ("crouch", "Crouching"),
                        ("prone", "Prone"), ("walk", "Walking")):
        g.keys("X", delay=0.8)
        assert label in g.screen(), f"HUD must refresh to {mode}:\n{g.screen()}"
        assert g.lua(f"out(gapi.get_avatar():get_movement_mode() == CharacterMoveMode.{mode})") == ["true"]
        assert bub_pos(g) == before, "changing stance must not move the player"


TESTS = [
    test_hud_box_options,
    test_boxes_replace_sidebar_rows,
    test_corner_bars_keep_sidebar_panels,
    test_body_panel,
    test_readable_map_glyphs,
    test_stance_toggle,
]
