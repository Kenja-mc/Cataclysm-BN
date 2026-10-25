"""Modern action routes exercised through the real game, not binding-file assertions."""
import re

from aim_reticle import action_clock
from contextual_hub import contextual_game, doors, door_state, interact_menu, select_tile
from fixtures import retire
from helpers import bub_pos, count_at, count_carried, give, spawn, wait_until
from map_mouse import assert_no_map_context, mouse_view


def test_contextual_left_click_opens_and_closes_without_walking(_g):
    with contextual_game("bn-e2e-click-door") as game:
        doors(game)
        position = bub_pos(game)
        for expected in ("t_door_o,t_door_c", "t_door_c,t_door_c"):
            clock = action_clock(game)
            x, y = game.find("@")
            game.click(x + 1, y)
            assert wait_until(lambda: door_state(game) == [expected]), game.screen()
            assert bub_pos(game) == position, "using a clicked door must not walk"
            assert action_clock(game) > clock, "clicked actions retain their normal move cost"
            assert_no_map_context(game)


def test_contextual_left_click_pickup_without_walking(_g):
    with contextual_game("bn-e2e-click-pickup") as game:
        spawn(game, 1, 0, "rock")
        spawn(game, -1, 0, "stick")
        position, clock = bub_pos(game), action_clock(game)
        x, y = game.find("@")
        game.click(x + 1, y)
        assert wait_until(lambda: count_carried(game, "rock") == 1), game.screen()
        assert "Pick up" not in game.screen(), "a lone item needs no picker"
        assert count_at(game, 1, 0, "rock") == 0
        assert count_at(game, -1, 0, "stick") == 1, "click must not pick up another tile"
        assert bub_pos(game) == position
        assert action_clock(game) > clock, "pickup retains its normal move cost"


def test_contextual_empty_and_distant_clicks_only_select(_g):
    with contextual_game("bn-e2e-click-select") as game:
        doors(game, selected_dx=3)
        position, clock = bub_pos(game), action_clock(game)
        for dx, dy in ((1, 0), (3, 0), (0, -3)):
            for _ in range(2):
                x, y = game.find("@")
                game.click(x + dx, y + dy)
                assert_no_map_context(game)
                panel = mouse_view(game)
                assert ("closed wood door" in panel) == (dx == 3), panel
                assert door_state(game, selected_dx=3) == ["t_door_c,t_door_c"]
                assert (bub_pos(game), action_clock(game)) == (position, clock), \
                    "empty/distant clicks must only inspect, never act elsewhere or walk"


def test_ctrl_peek_keeps_selected_interaction(_g):
    with contextual_game("bn-e2e-peek-selection") as game:
        doors(game)
        # Keep enough moves to measure the physical peek's exact cost without turn rollover.
        assert game.lua("gapi.get_avatar():set_moves(100000) out('ok')") == ["ok"]
        position, clock = bub_pos(game), action_clock(game)
        select_tile(game, -1, 0)
        game.wait_for("Mouse View")
        assert "closed wood door" in mouse_view(game)
        assert (bub_pos(game), action_clock(game)) == (position, clock), "selection must be free"
        game.keys("C-w", delay=0.2)
        game.wait_for("Look Around")
        game.keys("Escape", delay=0.2)
        game.wait_gone("Look Around")
        assert bub_pos(game) == position, "physical peek returns to the starting tile"
        after = action_clock(game)
        assert after[0] == clock[0] and after[1] - clock[1] == 200, \
            f"physical peek must retain its 200-move cost: {clock} -> {after}"
        game.keys("space", delay=0.2)
        game.wait_for("Interact with the")
        game.keys("o", delay=0.2)
        assert wait_until(lambda: door_state(game) == ["t_door_c,t_door_o"]), game.screen()
        assert bub_pos(game) == position, "Space must still act on the selected west door"
        retire(game)


def test_space_and_b_reach_butchery_for_own_corpse(_g):
    for route in ("space", "B"):
        with contextual_game("bn-e2e-corpse-route") as game:
            give(game, "knife_butcher")
            assert game.lua("M:create_corpse_at(here(0,0),MonsterTypeId.new('mon_zombie')) out('ok')") == ["ok"]
            position, clock = bub_pos(game), action_clock(game)
            game.keys(route, delay=0.2)
            if route == "space":
                rows, screen = interact_menu(game)
                corpse = [label for label in rows if "butcher" in label and label.endswith("(here)")]
                assert len(corpse) == 1, screen
                game.keys(rows[corpse[0]], delay=0.2)
            game.wait_for("Choose corpse to butcher")
            game.keys("Enter", delay=0.2)
            game.wait_for("Quick butchery")
            assert "Full butchery" in game.screen() and "Dissect corpse" in game.screen(), game.screen()
            game.keys("Escape", delay=0.2)
            game.wait_gone("Quick butchery")
            assert (bub_pos(game), action_clock(game)) == (position, clock), \
                "opening and canceling butchery must be free and stationary"
            assert game.lua("local n=0 for _,it in pairs(M:get_items_at(here(0,0))) do "
                            "if it:is_corpse() then n=n+1 end end out(n)") == ["1"]


def test_modern_use_at_p_reach_their_screens(_g):
    with contextual_game("bn-e2e-direct-info") as game:
        give(game, "pipe")
        position, clock = bub_pos(game), action_clock(game)
        game.keys("v", delay=0.2)
        game.wait_for("Use which item?")
        name = game.screen()
        assert "pipe" in name, name
        game.keys("Escape", delay=0.2)
        game.wait_gone("Use which item?")
        game.keys("@", delay=0.2)
        game.wait_for("Strength:")
        assert all(label in game.screen() for label in ("Dexterity:", "Intelligence:", "Perception:"))
        game.keys("Escape", delay=0.2)
        game.wait_gone("Strength:")
        assert game.lua("gapi.add_msg('E2E direct message route') out('ok')") == ["ok"]
        game.keys("P", delay=0.2)
        game.wait_for("to filter")
        screen = game.screen()
        assert any(re.search(r"│[^│]*E2E direct message route[^│]*│", line)
                   for line in screen.splitlines()), \
            "P must show the injected message inside the actual message-log frame:\n" + screen
        game.keys("Escape", delay=0.2)
        game.wait_gone("to filter")
        assert (bub_pos(game), action_clock(game)) == (position, clock), "browsing these screens must be free"
        # Actually wield through the advertised direct route, not just open its picker.
        game.keys("v", delay=0.2)
        game.wait_for("Use which item?")
        game.wait_for("pipe (1)")
        game.keys("Enter", delay=0.2)
        game.wait_gone("Use which item?")
        assert wait_until(lambda: game.lua(
            "local a=gapi.get_avatar() for _,it in ipairs(a:all_items(false)) do "
            "if a:is_wielding(it) then out(it:get_type():str()) end end") == ["pipe"]), game.screen()
        assert bub_pos(game) == position
        assert action_clock(game) > clock, "wielding must retain its normal move cost"


def test_modern_f_changes_fire_mode_without_firing(_g):
    with contextual_game("bn-e2e-fire-mode", HUD_ICONS="ascii") as game:
        assert game.lua("local a=gapi.get_avatar() ROUTE_GUN=a:create_item(ItypeId.new('m4a1'),-1) "
                        "out(a:wield(ROUTE_GUN))") == ["true"]
        def mode():
            found = re.search(r"\[([^\]]+)\]\s*M4A1", game.screen())
            assert found, "the wielded gun must display its firing mode:\n" + game.screen()
            return found.group(1)
        before = mode()
        position, clock = bub_pos(game), action_clock(game)
        ammo = game.lua("out(ROUTE_GUN:ammo_remaining())")
        game.keys("F", delay=0.2)
        assert wait_until(lambda: mode() != before), game.screen()
        assert game.lua("out(ROUTE_GUN:ammo_remaining())") == ammo, "changing mode must not fire"
        assert (bub_pos(game), action_clock(game)) == (position, clock)


TESTS = [test_contextual_left_click_opens_and_closes_without_walking,
         test_contextual_left_click_pickup_without_walking,
         test_contextual_empty_and_distant_clicks_only_select,
         test_ctrl_peek_keeps_selected_interaction,
         test_space_and_b_reach_butchery_for_own_corpse,
         test_modern_use_at_p_reach_their_screens,
         test_modern_f_changes_fire_mode_without_firing]
