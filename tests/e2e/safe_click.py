"""Safe click-to-walk: far clicks need a second click, and a hostile in view limits a click to one step."""
import time

from helpers import HELPERS, arena, bub_pos, settle, start_new_game


def wait_until(cond, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.3)
    return False


def see_everything(g, on):
    verb = "set_mutation" if on else "unset_mutation"
    assert g.lua(f"gapi.get_avatar():{verb}(MutationBranchId.new('DEBUG_NIGHTVISION')) out('ok')") == ["ok"]


def test_safe_click_preview(g):
    arena(g)
    # A dark shelter hides the tile three steps away, and an unseen tile offers no walk.
    see_everything(g, True)
    # Earlier tests leave monsters further out; seeing one would limit the click to one step.
    assert g.lua("for dx=-60,60 do for dy=-60,60 do local m=gapi.get_monster_at(here(dx,dy)) "
                 "if m then m:set_hp(0) end end end out('ok')") == ["ok"]
    settle(g)
    try:
        start = bub_pos(g)
        x, y = g.find("@")
        g.hover(x + 3, y)
        assert "click: walk here (3 steps)" in g.screen(), g.screen()
        g.click(x + 3, y)
        assert "click again to walk here (3 steps)" in g.screen(), g.screen()
        # Reading the position opens the Lua console with a key, which also cancels the click.
        assert bub_pos(g) == start, (start, bub_pos(g))
        g.hover(x + 3, y)
        g.click(x + 3, y)
        g.click(x + 3, y)
        assert wait_until(lambda: bub_pos(g) == (start[0] + 3, start[1], start[2])), (start, bub_pos(g))
    finally:
        see_everything(g, False)


def test_safe_click_hostile_one_step(g):
    arena(g)
    see_everything(g, True)
    assert g.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(-4,0)) out('ok')") == ["ok"]
    settle(g)
    try:
        start = bub_pos(g)
        x, y = g.find("@")
        g.hover(x + 3, y)
        assert "click: step toward (hostile in view)" in g.screen(), g.screen()
        g.click(x + 3, y)
        after = bub_pos(g)
        assert max(abs(after[0] - start[0]), abs(after[1] - start[1])) == 1, (start, after)
    finally:
        see_everything(g, False)
        arena(g)


def test_safe_click_option_off(_g):
    from tmux_game import Game

    game = Game(name="bn-e2e-safe-click-off", options={"SAFEMODE": "false", "SAFE_CLICK_WALK": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        see_everything(game, True)
        settle(game)
        start = bub_pos(game)
        x, y = game.find("@")
        game.click(x + 3, y)
        assert wait_until(lambda: bub_pos(game) == (start[0] + 3, start[1], start[2])), (start, bub_pos(game))
    finally:
        game.close()


def test_safe_click_hostile_npc_and_danger(_g):
    from tmux_game import Game

    game = Game(name="bn-e2e-safe-click-npc", options={"SAFEMODE": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        see_everything(game, True)
        settle(game)
        assert game.lua("HOSTILE_NPC=M:place_npc(here(4,0),'farmer') "
                        "HOSTILE_NPC:clear_bionics() HOSTILE_NPC:clear_mutations() "
                        "HOSTILE_NPC:clear_morale() HOSTILE_NPC:drop_all_items() out('ok')") == ["ok"]
        settle(game)
        assert game.lua("HOSTILE_NPC:set_attitude(NpcAttitude.NPCATT_KILL) "
                        "out(HOSTILE_NPC:is_enemy(),gapi.get_creature_at(HOSTILE_NPC:get_pos_ms()) ~= nil)") == ["true,true"]
        start = bub_pos(game)
        x, y = game.find("@")
        game.hover(x - 3, y)
        assert "click: step toward (hostile in view)" in game.screen(), game.screen()
        game.click(x - 3, y)
        assert bub_pos(game) == (start[0] - 1, start[1], start[2])

        # A visible hostile must not bypass confirmation for a dangerous destination.
        assert game.lua("out(M:add_field_at(here(-3,0),FieldTypeId.new('fd_acid'):int_id(),"
                        "3,TimeDuration.from_turns(0)))") == ["true"]
        start = bub_pos(game)
        x, y = game.find("@")
        game.hover(x - 3, y)
        game.click(x - 3, y)
        assert "click again: walk into danger" in game.screen(), game.screen()
        assert bub_pos(game) == start
    finally:
        game.close()


TESTS = [test_safe_click_preview, test_safe_click_hostile_one_step, test_safe_click_option_off,
         test_safe_click_hostile_npc_and_danger]
