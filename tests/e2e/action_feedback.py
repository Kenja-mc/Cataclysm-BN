"""Every verb leaves a trace on the HUD or the map, not only a line in the message log.

Each test presses one Modern binding and reads the drawn screen: the STATUS rule's stance,
the LOADOUT weapon and ammo, the carried weight, or a map tile glyph. Floating HUD windows
are off so nothing draws over the map region these reads assume.
"""
import re
from contextlib import contextmanager

from contextual_hub import doors, select_tile
from fixtures import shared_game
from helpers import (HELPERS, action_menu, arena, bub_pos, count_at, count_carried,
                     empty_inventory, give, settle, wait_until)
from hud_status import regions
from inventory_mouse import display_name, row_of
from safe_click import see_everything

OPTIONS = {
    "CONTROL_SCHEME": "modern",
    "SAFEMODE": "false",
    "SHOW_WELCOME": "false",
    "SHOW_TIPS": "false",
    "ANIMATIONS": "false",
    "INITIAL_TIME": "12",
    "HUD_WINDOWS": "false",
    "CONTEXTUAL_INTERACT": "true",
    "MOUSE_TILE_SELECTION": "true",
    "MOUSE_MOVE": "false",
    "AUTOSELECT_SINGLE_VALID_TARGET": "false",
}

COLS = 160


def verb_setup(game):
    game.resize(COLS, 45)
    empty_inventory(game)
    arena(game)
    see_everything(game, True)
    assert game.lua("gapi.get_avatar():set_movement_mode(CharacterMoveMode.walk) out('ok')") == ["ok"]
    settle(game)
    game.settle_screen()


@contextmanager
def verb_game():
    with shared_game("bn-e2e-action-feedback", options=OPTIONS, cols=COLS, rows=45,
                     layout="fusion", define=HELPERS, setup=verb_setup) as game:
        yield game


def sidebar(screen):
    return regions(screen, COLS)[1]


def rule_rows(screen, title):
    return [line for line in sidebar(screen).splitlines()
            if re.search(r"├─* *" + title + r"\b", line)]


def rule_row(screen, title):
    rows = rule_rows(screen, title)
    assert len(rows) <= 1, f"one {title} rule expected:\n" + screen
    return rows[0] if rows else ""


def section_lines(screen, title, count):
    lines = sidebar(screen).splitlines()
    heads = [y for y, line in enumerate(lines)
             if re.search(r"├─* *" + title + r"\b", line)]
    assert len(heads) <= 1, f"one {title} rule expected:\n" + screen
    if not heads:
        return [""] * count
    return lines[heads[0] + 1:heads[0] + 1 + count]


def stance(screen):
    match = re.search(r"\bSTATUS\s+(\S+)", rule_row(screen, "STATUS"))
    return match.group(1) if match else ""


def weapon_line(screen):
    """The row right under the LOADOUT rule: the held weapon as the section draws it."""
    return section_lines(screen, "LOADOUT", 1)[0]


def names(screen_row, name):
    """Whether a drawn row names `name`, ignoring the edge, its markers and loose spacing."""
    bare = re.sub(r"[│├─◆@]", " ", screen_row)
    return " ".join(name.split()).casefold() in " ".join(bare.split()).casefold()


def picker_row(game, name, header):
    """The row naming `name` inside the open picker, never the sidebar's own copy of it."""
    lines = game.screen().splitlines()
    start = next((y for y, line in enumerate(lines) if header in line), None)
    assert start is not None, f"no {header!r} picker:\n" + game.screen()
    for y in range(start, len(lines)):
        if name in lines[y]:
            return lines[y].index(name), y
    raise AssertionError(f"no {header!r} row for {name!r}:\n" + game.screen())


def glyph_at(game, dx, dy):
    screen = game.screen()
    lines = screen.splitlines()
    for y, line in enumerate(lines):
        if "@" in line[:95]:
            x = line.index("@")
            break
    else:
        return ""
    if not 0 <= y + dy < len(lines) or not 0 <= x + dx < len(lines[y + dy]):
        return ""
    return lines[y + dy][x + dx]


def wait_glyph(game, dx, dy, expected, what):
    assert wait_until(lambda: glyph_at(game, dx, dy) == expected, timeout=10), \
        f"{what}: expected {expected!r} at {dx:+d},{dy:+d}\n" + game.screen()


def test_cycle_move_changes_the_status_stance(_game):
    with verb_game() as game:
        assert wait_until(lambda: stance(game.screen()) == "Walking", timeout=10), \
            "the fixture must start walking:\n" + game.screen()
        before = bub_pos(game)
        game.keys("X", delay=1)
        assert "Change to which movement mode?" in game.screen(), game.screen()
        game.keys("r", delay=1)
        assert wait_until(lambda: stance(game.screen()) == "Running", timeout=10), \
            "the STATUS rule must read Running:\n" + game.screen()
        assert bub_pos(game) == before, "changing movement mode must not move the avatar"


def test_crouch_changes_the_status_stance(_game):
    with verb_game() as game:
        assert wait_until(lambda: stance(game.screen()) == "Walking", timeout=10), \
            "the fixture must start walking:\n" + game.screen()
        game.keys("X", delay=1)
        assert "Change to which movement mode?" in game.screen(), game.screen()
        game.keys("c", delay=1)
        assert wait_until(lambda: stance(game.screen()) == "Crouching", timeout=10), \
            "the STATUS rule must read Crouching:\n" + game.screen()


def test_wield_changes_the_loadout_weapon(_game):
    with verb_game() as game:
        give(game, "pipe")
        game.settle_screen()
        assert wait_until(lambda: names(weapon_line(game.screen()), "fists"), timeout=10), \
            "the unarmed LOADOUT line names the fists:\n" + game.screen()
        pipe = display_name(game, "pipe")
        game.keys("i", delay=1)
        game.wait_for("Inventory", timeout=15)
        x, y = row_of(game, pipe)
        game.click(x, y, button=2)
        game.wait_for("Reassign", timeout=15)
        game.keys("h", delay=1.5)
        assert wait_until(lambda: names(weapon_line(game.screen()), "pipe"), timeout=10), \
            f"the LOADOUT weapon line must name the wielded pipe ({pipe!r}), " \
            f"read {weapon_line(game.screen())!r}:\n" + game.screen()
        assert not names(weapon_line(game.screen()), "fists")


def test_drop_leaves_the_item_on_the_ground_tile(_game):
    with verb_game() as game:
        give(game, "rock")
        game.settle_screen()
        assert wait_until(lambda: bool(rule_row(game.screen(), "LOADOUT")), timeout=10), \
            "the LOADOUT rule must be drawn:\n" + game.screen()
        before = rule_row(game.screen(), "LOADOUT")
        rock = display_name(game, "rock")
        game.keys("i", delay=1)
        game.wait_for("Inventory", timeout=15)
        x, y = row_of(game, rock)
        game.click(x, y, button=2)
        game.wait_for("Reassign", timeout=15)
        game.keys("D", delay=1.5)
        game.wait_gone("Inventory", timeout=10)
        assert count_carried(game, "rock") == 0, "the rock must leave the inventory"
        assert count_at(game, 0, 0, "rock") == 1, "the rock must lie at the feet"
        assert wait_until(lambda: rule_row(game.screen(), "LOADOUT") != before, timeout=10), \
            "the carried weight summary must drop in the same turn:\n" + game.screen()
        game.keys("w", delay=0.8)
        wait_glyph(game, 0, 1, "*", "the dropped rock must draw on the tile it fell on")


def test_unload_changes_the_loadout_ammo(_game):
    with verb_game() as game:
        gun = re.sub(r"\s*\(.*\)$", "", display_name(game, "model_10_revolver"))
        assert game.lua("local a=gapi.get_avatar() "
                        "local w=a:create_item(ItypeId.new('model_10_revolver'),-1) "
                        "w:ammo_set(ItypeId.new('38_special'),6) out(a:wield(w))") == ["true"]
        game.settle_screen()
        assert wait_until(lambda: "6/6" in weapon_line(game.screen()), timeout=10), \
            "the LOADOUT line must show the loaded gun's rounds:\n" + game.screen()
        action_menu(game, "Inventory", "Unload or Empty Wielded Item")
        game.wait_for("Unload item", timeout=15)
        x, y = picker_row(game, gun, "WEAPON HELD")
        game.double_click(x, y)
        assert wait_until(lambda: "0/6" in weapon_line(game.screen()), timeout=10), \
            "the LOADOUT ammo count must fall to 0/6:\n" + game.screen()


def test_open_door_changes_the_map_glyph(_game):
    with verb_game() as game:
        doors(game)
        game.settle_screen()
        before = bub_pos(game)
        wait_glyph(game, 1, 0, "+", "the door must draw closed before opening")
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        wait_glyph(game, 1, 0, "'", "the opened door must draw open")
        wait_glyph(game, -1, 0, "+", "only the selected door may open")
        assert bub_pos(game) == before, "opening a door must not walk"


TESTS = [
    test_cycle_move_changes_the_status_stance,
    test_crouch_changes_the_status_stance,
    test_wield_changes_the_loadout_weapon,
    test_drop_leaves_the_item_on_the_ground_tile,
    test_unload_changes_the_loadout_ammo,
    test_open_door_changes_the_map_glyph,
]
