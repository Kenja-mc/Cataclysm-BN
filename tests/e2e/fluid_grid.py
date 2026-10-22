"""Fluid grid feedback: liquid that does not fit in the grid stays in its container."""
import json
import re
import tempfile
from pathlib import Path

from helpers import HELPERS, Game, arena, count_at, give, start_new_game
from tmux_game import ROOT

TANK = "f_e2e_small_tank"


def pause(game):
    # Classic vi-keys: x is Look Around, so wait with the pause key.
    game.keys(".", delay=0.6)


def fluid_grid_game(name):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-fluid-grid-"))
    mod_dir = userdir / "mods" / "e2e_fluid_grid"
    mod_dir.mkdir(parents=True)
    (mod_dir / "modinfo.json").write_text(json.dumps([{
        "type": "MOD_INFO", "id": "e2e_fluid_grid", "name": "E2E fluid grid",
        "description": "One-litre plumbed tank so a small pour already overfills the grid.",
        "category": "content", "dependencies": ["bn"],
    }]))
    (mod_dir / "furniture.json").write_text(json.dumps([
        {"type": "furniture", "id": TANK, "copy-from": "f_standing_tank",
         "name": "small test tank", "keg_capacity": 4},
        {"type": "furniture", "id": TANK + "_plumbed", "copy-from": "f_standing_tank_plumbed",
         "name": "small test tank (plumbed)", "keg_capacity": 4,
         "fluid_grid": {"role": "tank", "allow_input": True, "allow_output": True,
                        "allowed_liquids": "universal", "autofill": True,
                        "disconnected_variant": TANK, "use_keg_capacity": True}},
    ]))
    defaults = json.loads((ROOT / "data/mods/default.json").read_text())
    (userdir / "config").mkdir()
    (userdir / "config/default_mods.json").write_text(
        json.dumps([*defaults, "e2e_fluid_grid"]))
    game = Game(name=name, userdir=userdir,
                options={"SAFEMODE": "false", "CONTROL_SCHEME": "classic",
                         "AUTOSELECT_SINGLE_VALID_TARGET": "false"})
    try:
        start_new_game(game)
        pause(game)
        game.define_lua(HELPERS)
        arena(game)
        # The shelter special spans a multi-tile fluid grid, so work in open field instead:
        # there the one placed tank is the whole grid and holds one litre.
        assert game.lua(
            "local p=M:bub_to_abs(here(0,0)):to_omt() "
            "gapi.place_player_overmap_at(TripointAbsOmt.new(p.x+6,p.y+6,p.z)) "
            "local q=M:bub_to_abs(here(0,0)):to_omt() out(#overmapbuffer.fluid_grid_at(q))") == ["1"]
        pause(game)
        arena(game)
    except Exception:
        game.close()
        raise
    return game


def press_menu_row(game, label):
    """Choose a menu row by the hotkey shown next to it."""
    for line in game.screen().splitlines():
        match = re.search(r"│\s*(\w)\s+" + label + r"\b", line)
        if match:
            game.keys(match[1], delay=1.0)
            return
    raise AssertionError(f"the menu has no {label!r} row:\n" + game.screen())


def test_partial_grid_transfer_keeps_the_rest(_game):
    """5 L poured into the 1 L grid leaves 4 L in the container."""
    game = fluid_grid_game("bn-e2e-fluid-grid")
    try:
        # The tank holds the liquid: a bare floor would turn the item into a water field.
        assert game.lua(
            f"M:set_furn_at(here(1,0), FurnId.new('{TANK}'):int_id()) "
            "M:create_item_at(here(1,0), ItypeId.new('water_clean'), 20) out('ok')") == ["ok"]
        give(game, "plumber_toolkit", 1)
        assert count_at(game, 1, 0, "water_clean") == 20, game.screen()

        game.keys("e", delay=1.0)
        game.wait_for("Examine where?")
        game.keys("l", delay=1.0)
        game.wait_for("Select an action")
        press_menu_row(game, "Add to fluid grid")

        game.wait_for("is left behind", timeout=20)
        assert count_at(game, 1, 0, "water_clean") == 16, \
            f"4 L must stay in the container:\n{game.screen()}"
    finally:
        game.close()


TESTS = [test_partial_grid_transfer_keeps_the_rest]
