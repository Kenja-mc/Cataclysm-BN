from helpers import HELPERS, arena, bub_pos, exploration_arena, settle, start_new_game, wait_until
from tmux_game import Game


def test_smart_safe_mode(g):
    smart = Game(name="bn-e2e-smart-safe", options={"SAFEMODE": "true"})
    try:
        start_new_game(smart)
        smart.define_lua(HELPERS)
        exploration_arena(smart)
        assert smart.lua("for _,cr in ipairs(gapi.get_all_monsters()) do "
                         "cr:make_friendly() end out('ok')") == ["ok"]
        smart.lua("for dx=-1,1 do for dy=-1,1 do if dx ~= 0 or dy ~= 0 then "
                  "M:set_ter_at(here(6+dx,dy), TerId.new('t_reinforced_glass'):int_id()) end end end "
                  "M:set_ter_at(here(6,0), TerId.new('t_floor'):int_id()) "
                  "gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(6,0)) out('ok')")
        settle(smart)
        smart.keys("x", delay=0.6)
        start = bub_pos(smart)
        smart.keys("n", delay=0.6)
        assert wait_until(lambda: bub_pos(smart) != start, timeout=60), \
            "auto-explore should run with a zombie locked in a glass cell:\n" + smart.screen()
        smart.keys("Escape", delay=0.3)
        arena(smart)
        smart.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(3,0)) out('ok')")
        smart.keys("x", delay=0.6)
        smart.keys("n", delay=0.6)
        assert wait_until(lambda: "enemies in sight" in smart.screen(), timeout=30), \
            "a zombie that can reach you should stop auto-explore:\n" + smart.screen()
    finally:
        smart.close()


def test_smart_safe_mode_horde(g):
    smart = Game(name="bn-e2e-smart-horde", options={"SAFEMODE": "false"})
    try:
        start_new_game(smart)
        smart.define_lua(HELPERS)
        arena(smart)
        assert smart.lua(
            "for _,cr in ipairs(gapi.get_all_monsters()) do cr:make_friendly() end "
            "for dx=-12,12 do for dy=-12,12 do local p=here(dx,dy) "
            "M:set_ter_at(p, TerId.new('t_floor'):int_id()) "
            "M:set_furn_at(p, FurnId.new('f_null'):int_id()) end end "
            "for dx=-2,2 do for dy=-2,2 do if math.max(math.abs(dx),math.abs(dy))==2 then "
            "M:set_ter_at(here(dx,dy), TerId.new('t_reinforced_glass'):int_id()) end end end "
            "for dx=-6,4,2 do for _,dy in ipairs({-6,6}) do "
            "gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(dx,dy)) end end out('ok')"
        ) == ["ok"]
        settle(smart)
        smart.keys("n", delay=0.6)
        assert "enemies in sight" not in smart.screen(), \
            "all twelve blocked routes should be checked:\n" + smart.screen()
        smart.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(6,6)) out('ok')")
        settle(smart)
        smart.keys("n", delay=0.6)
        assert "enemies in sight" in smart.screen(), \
            "the unchecked thirteenth hostile must block auto-explore:\n" + smart.screen()
    finally:
        smart.close()


TESTS = [
    test_smart_safe_mode,
    test_smart_safe_mode_horde,
]
