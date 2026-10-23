"""Modern map controls: contextual stairs, quick/area pickup and health."""
from aim_reticle import action_clock
from contextual_hub import contextual_game
from helpers import arena, bub_pos, count_at, count_carried, settle, spawn, wait_until


def stair_pair(game):
    arena(game)
    assert game.lua(
        "local a=gapi.get_avatar() a:clear_effects() a:set_underwater(false) "
        "local p=here(0,0) "
        "for dx=-4,4 do for dy=-4,4 do "
        "local q=TripointBubMs.new(p.x+dx,p.y+dy,p.z-1) "
        "M:set_ter_at(q,TerId.new('t_floor'):int_id()) "
        "M:set_furn_at(q,FurnId.new('f_null'):int_id()) M:clear_items_at(q) "
        "for _,fid in ipairs(M:get_field_ids_at(q)) do M:remove_field_at(q,fid) end "
        "M:remove_trap_at(q) local cr=gapi.get_creature_at(q) "
        "if cr and not cr:is_avatar() then park(cr) end end end "
        "M:set_ter_at(p,TerId.new('t_stairs_down'):int_id()) "
        "M:set_ter_at(TripointBubMs.new(p.x,p.y,p.z-1),TerId.new('t_stairs_up'):int_id()) "
        "out('ok')") == ["ok"]
    settle(game)


def test_modern_space_pagedown_and_click_use_stairs(_game):
    with contextual_game("bn-e2e-modern-stairs", SHOW_TIPS="false", SHOW_WELCOME="false") as game:
        for control in ("space", "PageDown", "click"):
            stair_pair(game)
            before, clock = bub_pos(game), action_clock(game)
            if control == "click":
                game.click(*game.find("@"))
            else:
                game.keys(control, delay=0.2)
            assert wait_until(lambda: bub_pos(game) == (before[0], before[1], before[2] - 1)), \
                f"{control} must use the stairs underfoot:\n" + game.screen()
            assert action_clock(game) > clock, "contextual stairs keep their normal move cost"
            game.keys("PageUp", delay=0.2)
            assert wait_until(lambda: bub_pos(game) == before), "PageUp must return upstairs"


def test_modern_click_on_other_stairs_only_selects(_game):
    with contextual_game("bn-e2e-modern-other-stairs", SHOW_TIPS="false") as game:
        assert game.lua("M:set_ter_at(here(1,0),TerId.new('t_stairs_down'):int_id()) out('ok')") == ["ok"]
        settle(game)
        before, clock = bub_pos(game), action_clock(game)
        x, y = game.find("@")
        game.click(x + 1, y)
        assert bub_pos(game) == before, "clicking other stairs must not move or change floors"
        assert action_clock(game) == clock


def test_modern_g_takes_everything_underfoot_without_menu(_game):
    with contextual_game("bn-e2e-modern-quick-pickup", SHOW_TIPS="false") as game:
        spawn(game, 0, 0, "rock", n=3)
        spawn(game, 0, 0, "stick", n=2)
        spawn(game, 1, 0, "pipe")
        before, clock = bub_pos(game), action_clock(game)
        game.keys("g", delay=0.2)
        assert wait_until(lambda: count_carried(game, "rock") == 3 and
                          count_carried(game, "stick") == 2), game.screen()
        assert "Weight" not in game.screen(), "quick pickup must not open a selection menu"
        assert count_at(game, 0, 0, "rock") == count_at(game, 0, 0, "stick") == 0
        assert count_at(game, 1, 0, "pipe") == 1, "quick pickup never includes adjacent tiles"
        assert bub_pos(game) == before
        assert action_clock(game) > clock, "quick pickup uses the normal timed activity"
        game.keys("g", delay=0.2)
        game.wait_for("There is nothing to pick up here.")


def test_modern_ctrl_g_opens_area_pickup(_game):
    with contextual_game("bn-e2e-modern-area-pickup", SHOW_TIPS="false") as game:
        spawn(game, 0, 0, "rock")
        spawn(game, 1, 0, "stick")
        before, clock = bub_pos(game), action_clock(game)
        game.keys("C-g", delay=0.2)
        game.wait_for("Pick up")
        game.wait_for("Weight")
        game.wait_for("rock")
        game.wait_for("stick")
        game.keys("Escape", delay=0.2)
        game.wait_gone("Pick up")
        assert count_carried(game, "rock") == count_carried(game, "stick") == 0
        assert count_at(game, 0, 0, "rock") == count_at(game, 1, 0, "stick") == 1
        assert bub_pos(game) == before and action_clock(game) == clock, "canceling area pickup is free"


def test_modern_h_opens_health(_game):
    with contextual_game("bn-e2e-modern-health", SHOW_TIPS="false") as game:
        before, clock = bub_pos(game), action_clock(game)
        game.keys("h", delay=0.2)
        game.wait_for("Bandages stop bleeding")
        for limb in ("Head", "Torso", "L. Arm", "R. Arm", "L. Leg", "R. Leg"):
            game.wait_for(limb)
        game.keys("Escape", delay=0.2)
        game.wait_gone("Bandages stop bleeding")
        assert bub_pos(game) == before and action_clock(game) == clock, "health inspection is free"


TESTS = [test_modern_space_pagedown_and_click_use_stairs,
         test_modern_click_on_other_stairs_only_selects,
         test_modern_g_takes_everything_underfoot_without_menu,
         test_modern_ctrl_g_opens_area_pickup, test_modern_h_opens_health]
