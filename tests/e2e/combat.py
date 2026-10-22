"""Bump attacks, the attack command and the electromagnetic unit.

Tests that take `g` run on the runner's main game; BUMP_ATTACK=false needs its own.
"""
from aim_reticle import action_clock
from helpers import HELPERS, action_menu, arena, bub_pos, empty_inventory, settle, start_new_game
from tmux_game import Game


def test_walking_into_enemy_attacks(g):
    """Misses still count as bump attacks."""
    empty_inventory(g)
    arena(g)
    settle(g)
    try:
        assert g.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) out('ok')") == ["ok"]
        before = bub_pos(g)
        clock = action_clock(g)
        g.keys("d", delay=1)
        assert bub_pos(g) == before, "a bump attack must not step into the occupied tile"
        assert action_clock(g) > clock, "walking into the zombie must spend moves attacking"
    finally:
        arena(g)


def test_bump_attack_can_be_disabled(_g):
    game = Game(name="bn-e2e-no-bump",
                options={"CONTROL_SCHEME": "modern", "BUMP_ATTACK": "false", "SAFEMODE": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        empty_inventory(game)
        arena(game)
        settle(game)
        assert game.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) out('ok')") == ["ok"]
        before = bub_pos(game)
        clock = action_clock(game)
        game.keys("d", delay=1)
        assert bub_pos(game) == before, "an occupied tile must still block movement"
        assert action_clock(game) == clock, "BUMP_ATTACK=false must prevent a movement key from attacking"
    finally:
        game.close()


def test_attack_command(g):
    empty_inventory(g)
    arena(g)
    settle(g)
    try:
        assert g.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) out('ok')") == ["ok"]
        before = bub_pos(g)
        clock = action_clock(g)
        action_menu(g, "Interact", "Attack in a direction")
        g.keys("d", delay=1)
        assert bub_pos(g) == before, "a directed attack must not move the player"
        assert action_clock(g) > clock, "the directional attack must spend moves attacking"
    finally:
        arena(g)


def test_magnet_pull_through_monster(g):
    """Upstream #9354: pulling metal through a monster with the electromagnetic unit crashed."""
    arena(g)
    assert g.lua("local u=gapi.get_avatar() u:add_bionic(BionicDataId.new('bio_magnet')) "
                 "u:set_max_power_level(Energy.from_kilojoule(100)) out('ok')") == ["ok"]
    for _ in range(4):
        out = g.lua("spawn(5,0,'throwing_knife',1,nil) spawn(4,0,'throwing_axe',1,nil) "
                    "local u=gapi.get_avatar() u:set_power_level(Energy.from_kilojoule(100)) "
                    "if not gapi.get_monster_at(here(2,0)) then gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(2,0)) end "
                    "out(u:activate_bionic(BionicDataId.new('bio_magnet'), false))")
        assert out and out[-1] == "true", g.screen()
    assert "wasd move" in g.screen(), "game should still be running"
    g.lua("for dx=-6,6 do for dy=-6,6 do local m=gapi.get_monster_at(here(dx,dy)) if m then park(m) end end end out('ok')")
    # The pulls spend turns beside a zombie: clear the grab it left and let the turn finish.
    g.lua("gapi.get_avatar():clear_effects() out('ok')")
    settle(g)


TESTS = [
    test_walking_into_enemy_attacks,
    test_bump_attack_can_be_disabled,
    test_attack_command,
    test_magnet_pull_through_monster,
]
