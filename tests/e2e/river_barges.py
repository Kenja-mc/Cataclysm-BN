"""New worlds load the Stocked River Barges mod and its sealed cargo crates hold loot."""
import json

from helpers import HELPERS, Game, arena, settle, start_new_game


def test_new_worlds_stock_river_barges(_g):
    game = Game(name="bn-e2e-barges", options={"SAFEMODE": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        mods = [json.loads(path.read_text()) for path in (game.userdir / "save").glob("*/mods.json")]
        assert len(mods) == 1 and "stocked_river_barges" in mods[0], mods
        game.keys("F12", delay=0.6)
        game.wait_for("Map…")
        game.keys("m", delay=0.6)
        game.wait_for("Spawn nested mapgen")
        game.keys("n", delay=0.6)
        game.keys("/", delay=0.4)
        game.type("stocked_barge_crate_sealed")
        game.wait_for("stocked_barge_crate_sealed")
        game.keys("Enter", delay=0.6)  # Ends the filter.
        game.keys("Enter", delay=0.8)  # Picks the chunk and opens the look cursor.
        game.wait_for("Show extended description")
        game.keys("Enter", delay=0.8)  # The look cursor starts on the avatar.
        game.wait_gone("Show extended description")
        settle(game)
        out = game.lua("local p=here(0,0) out(M:get_furn_at(p):str_id():str(), #M:get_items_at(p):items())")
        furniture, items = out[0].split(",")
        assert furniture == "f_crate_c" and int(items) > 0, out
    finally:
        game.close()


TESTS = [test_new_worlds_stock_river_barges]
