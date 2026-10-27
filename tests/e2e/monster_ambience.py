"""Monster idle ambience is data-driven, jittered per creature and crowd-capped.

These tests observe the sound markers the normal sound pipeline paints, not audio. They run the
curses binary, whose `has_asset()` reports every id as present because a marker is that build's
only sound cue. A sound build additionally requires the loaded pack to provide the clip: without it
there is no cue and no marker, so nothing is silent-but-visible (issue #32). No shipped monster
declares `idle_sound`, so the fixture installs a mod that does.
"""
import json
import math
import time
import tempfile
from pathlib import Path

from helpers import HELPERS, Game, settle, start_new_game
from sound_feedback import glyph_cells
from tmux_game import ROOT

MOD_ID = "e2e_monster_ambience"
NOISY = "e2e_idle_zombie"
SILENT = "e2e_silent_zombie"


def ambience_game(name, **options):
    """A dark, sealed room so every idle sound is heard but never seen."""
    userdir = Path(tempfile.mkdtemp(prefix=f"bn-e2e-{name}-"))
    mod_dir = userdir / "mods" / MOD_ID
    mod_dir.mkdir(parents=True)
    (mod_dir / "modinfo.json").write_text(json.dumps([{
        "type": "MOD_INFO", "id": MOD_ID, "name": "E2E monster ambience",
        "description": "Two immobile zombies: one declares an idle sound, one does not.",
        "category": "content", "dependencies": ["bn"],
    }]))
    (mod_dir / "monsters.json").write_text(json.dumps([
        {"type": "MONSTER", "id": NOISY, "name": "idle test zombie", "symbol": "Z",
         "color": "light_green", "default_faction": "zombie", "bodytype": "human",
         "species": ["ZOMBIE"], "material": ["flesh"], "volume": "62500 ml",
         "weight": "81500 g", "hp": 80, "speed": 70, "vision_day": 0, "vision_night": 0,
         "flags": ["IMMOBILE", "NO_BREATHE"], "idle_sound": "e2e_monster_idle"},
        {"type": "MONSTER", "id": SILENT, "name": "silent test zombie", "symbol": "Z",
         "color": "light_green", "default_faction": "zombie", "bodytype": "human",
         "species": ["ZOMBIE"], "material": ["flesh"], "volume": "62500 ml",
         "weight": "81500 g", "hp": 80, "speed": 70, "vision_day": 0, "vision_night": 0,
         "flags": ["IMMOBILE", "NO_BREATHE"]},
    ]))
    defaults = json.loads((ROOT / "data/mods/default.json").read_text())
    (userdir / "config").mkdir()
    (userdir / "config/default_mods.json").write_text(json.dumps([*defaults, MOD_ID]))
    game = Game(name=f"bn-e2e-{name}", userdir=userdir,
                options={"SAFEMODE": "false", "SHOW_TIPS": "false", "SHOW_WELCOME": "false",
                         "ANIMATIONS": "false", "SOUND_MARKER_TURNS": "1", **options})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        settle(game)
        assert game.lua(
            "local a=gapi.get_avatar() local p=a:get_pos_ms() "
            "a:clear_bionics() a:clear_mutations() a:clear_morale() a:drop_all_items() "
            "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) "
            "for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end "
            "for dx=-10,10 do for dy=-10,10 do local q=here(dx,dy) "
            "M:set_ter_at(q, TerId.new('t_floor'):int_id()) "
            "M:set_furn_at(q, FurnId.new('f_null'):int_id()) M:clear_items_at(q) "
            "for _,fid in ipairs(M:get_field_ids_at(q)) do M:remove_field_at(q,fid) end "
            "end end out('ok')") == ["ok"]
        settle(game)
    except Exception:
        game.close()
        raise
    return game


def ring_positions(count):
    """Cells ordered by Chebyshev ring, inner rings first, so a crowd surrounds the player."""
    out = []
    for radius in range(2, 8):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) == radius:
                    out.append((dx, dy))
    return out[:count]


def spawn(game, type_id, positions):
    code = " ".join(
        f"local m=gapi.place_monster_at(MonsterTypeId.new('{type_id}'),here({dx},{dy})) "
        "if not m then error('place_monster_at failed') end"
        for dx, dy in positions)
    assert game.lua(code + " out('ok')") == ["ok"]


def marker_count(game):
    """Sound markers in the map area, using the glyph bounds the marker tests already define."""
    return len(glyph_cells(game, "?"))


def wait_for_marker(game, turns=26):
    for _ in range(turns):
        settle(game)
        if marker_count(game):
            return True
    return False


def test_idle_sound_needs_the_data_field_and_rerolls_its_cooldown(_g):
    """A monster without `idle_sound` is silent; one with it emits again after 8-20 s."""
    game = ambience_game("ambience-cooldown", MONSTER_AMBIENCE="true")
    try:
        spawn(game, SILENT, ring_positions(6))
        for _ in range(24):
            settle(game)
        assert marker_count(game) == 0, \
            "a monster without idle_sound must not emit a sound or a marker:\n" + game.screen()

        assert game.lua("for _,m in ipairs(gapi.get_all_monsters()) do park(m) end out('ok')") == ["ok"]
        settle(game)
        spawn(game, NOISY, [(3, 0)])
        assert wait_for_marker(game), \
            "a monster with idle_sound should emit within its 8-20 second cooldown:\n" + game.screen()

        for _ in range(4):
            settle(game)
            if marker_count(game) == 0:
                break
        assert wait_for_marker(game), \
            "the per-creature cooldown should reroll after an emission:\n" + game.screen()
    finally:
        game.close()


def test_crowd_cap_drops_the_excess(_g):
    """Sixty idle creatures stay within the code's own four-per-250 ms budget."""
    game = ambience_game("ambience-crowd", MONSTER_AMBIENCE="true")
    try:
        spawn(game, NOISY, ring_positions(60))
        peak = 0
        total = 0
        for _ in range(30):
            # The cap is a wall-clock window, so derive the allowance from the turn's measured
            # duration instead of assuming one turn fits in one window. A slow CI runner that
            # spends longer than 250 ms in a turn legitimately opens another window.
            started = time.monotonic()
            settle(game)
            windows = max(1, math.ceil((time.monotonic() - started) / 0.25))
            count = marker_count(game)
            assert count <= 4 * windows, \
                f"at most four new creature ambience sounds fit in each 250 ms, not {count}:\n" + game.screen()
            peak = max(peak, count)
            total += count
        assert peak > 0 and total > 0, \
            "the crowd should still make some idle sounds:\n" + game.screen()
    finally:
        game.close()


def test_option_off_silences_the_crowd(_g):
    """The asset-blocked toggle defaults off, and off means no sound and no marker."""
    game = ambience_game("ambience-off", MONSTER_AMBIENCE="false")
    try:
        spawn(game, NOISY, ring_positions(40))
        for _ in range(24):
            settle(game)
        assert marker_count(game) == 0, \
            "with the monster ambience toggle off nothing may be heard:\n" + game.screen()
    finally:
        game.close()


TESTS = [
    test_idle_sound_needs_the_data_field_and_rerolls_its_cooldown,
    test_crowd_cap_drops_the_excess,
    test_option_off_silences_the_crowd,
]
