"""Safe click-to-walk: far clicks need a second click, and a hostile in view limits a click to one step."""
from contextlib import contextmanager

from fixtures import shared_game
from helpers import HELPERS, arena, bub_pos, settle, wait_until


def see_everything(g, on):
    verb = "set_mutation" if on else "unset_mutation"
    assert g.lua(f"gapi.get_avatar():{verb}(MutationBranchId.new('DEBUG_NIGHTVISION')) out('ok')") == ["ok"]


def click_walk_setup(game):
    arena(game)
    see_everything(game, True)
    assert game.lua("for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end "
                    "for _,n in ipairs(gapi.get_all_npcs()) do park(n) end out('ok')") == ["ok"]
    settle(game)


@contextmanager
def click_walk_game(name, **options):
    """Keep legacy travel opt-in and isolated."""
    with shared_game(name, define=HELPERS, setup=click_walk_setup,
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false",
                              "MOUSE_TILE_SELECTION": "true", "MOUSE_MOVE": "true",
                              "SAFE_CLICK_WALK": "true", **options}) as game:
        yield game


def test_safe_click_preview(_g):
    with click_walk_game("bn-e2e-safe-click-preview") as g:
        start = bub_pos(g)
        x, y = g.find("@")
        g.click(x + 3, y)
        # Lua cancels the pending confirmation.
        assert bub_pos(g) == start, "the first far click must only preview travel"
        g.click(x + 3, y)
        g.click(x + 3, y)
        assert wait_until(lambda: bub_pos(g) == (start[0] + 3, start[1], start[2])), (start, bub_pos(g))


def test_safe_click_hostile_one_step(_g):
    with click_walk_game("bn-e2e-safe-click-hostile") as g:
        assert g.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(-4,0)) "
                     "out('ok')") == ["ok"]
        settle(g)
        start = bub_pos(g)
        x, y = g.find("@")
        g.click(x + 3, y)
        assert bub_pos(g) == (start[0] + 1, start[1], start[2]), "a visible hostile limits travel to one step"


def test_safe_click_option_off(_g):
    with click_walk_game("bn-e2e-safe-click-off", SAFE_CLICK_WALK="false") as game:
        start = bub_pos(game)
        x, y = game.find("@")
        game.click(x + 3, y)
        assert wait_until(lambda: bub_pos(game) == (start[0] + 3, start[1], start[2])), (start, bub_pos(game))


def test_safe_click_hostile_npc_and_danger(_g):
    with click_walk_game("bn-e2e-safe-click-npc") as game:
        assert game.lua("HOSTILE_NPC=M:place_npc(here(4,0),'farmer') "
                        "HOSTILE_NPC:clear_bionics() HOSTILE_NPC:clear_mutations() "
                        "HOSTILE_NPC:clear_morale() HOSTILE_NPC:drop_all_items() out('ok')") == ["ok"]
        settle(game)
        assert game.lua("HOSTILE_NPC:set_attitude(NpcAttitude.NPCATT_KILL) "
                        "out(HOSTILE_NPC:is_enemy(),gapi.get_creature_at(HOSTILE_NPC:get_pos_ms()) ~= nil)") == ["true,true"]
        start = bub_pos(game)
        x, y = game.find("@")
        game.click(x - 3, y)
        assert bub_pos(game) == (start[0] - 1, start[1], start[2])

        # A visible hostile must not bypass confirmation for a dangerous destination.
        assert game.lua("out(M:add_field_at(here(-3,0),FieldTypeId.new('fd_acid'):int_id(),"
                        "3,TimeDuration.from_turns(0)))") == ["true"]
        start = bub_pos(game)
        x, y = game.find("@")
        game.click(x - 3, y)
        assert bub_pos(game) == start, "danger still requires confirmation with a hostile in view"


TESTS = [test_safe_click_preview, test_safe_click_hostile_one_step, test_safe_click_option_off,
         test_safe_click_hostile_npc_and_danger]
