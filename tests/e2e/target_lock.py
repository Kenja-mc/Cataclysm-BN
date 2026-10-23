"""A locked selection owns the inspector and the only highlight; fire acts on it."""
from aim_reticle import action_clock
from contextual_hub import colored_cells
from cursor_panning import pan_game, _right_edge
from helpers import arena, bub_pos, empty_inventory, settle, wait_until
from map_mouse import mouse_state, mouse_view, no_mouse_movement_game
from safe_click import see_everything


def screen_cells(game):
    return colored_cells(game.screen_colors())


def test_locked_enemy_freezes_hover_and_fire_targets_it(_g):
    with no_mouse_movement_game("bn-e2e-target-lock") as game:
        settle(game)
        empty_inventory(game)
        arena(game)
        see_everything(game, True)
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(1,0)) "
                        "MAP_MOUSE_TARGETS={m} out(m ~= nil)") == ["true"]
        position = bub_pos(game)
        x, y = game.find("@")
        empty_cell = (x, y + 2)
        cells = screen_cells(game)
        empty_before = cells[empty_cell[1]][empty_cell[0]][1]
        enemy_before = cells[y][x + 1][1]

        game.click(x + 1, y, button=2)
        screen = game.screen()
        assert "Interact with the" not in screen, "an enemy right click only locks:\n" + screen
        assert "< Firing " not in screen, "an enemy right click must not aim"
        assert "zombie" in mouse_view(game), "the locked enemy must stay inspected"
        cells = screen_cells(game)
        assert cells[y][x + 1][1] != enemy_before, "the locked enemy must be highlighted"
        assert cells[empty_cell[1]][empty_cell[0]][1] == empty_before, "only the enemy is highlighted"

        # Moving the pointer elsewhere must not move the inspector or add a second highlight.
        game.hover(*empty_cell)
        assert "zombie" in mouse_view(game), "hover must not replace the locked inspector"
        cells = screen_cells(game)
        assert cells[y][x + 1][1] != enemy_before, "the locked enemy keeps its highlight"
        assert cells[empty_cell[1]][empty_cell[0]][1] == empty_before, \
            "the hovered tile must not gain a highlight"

        clock = action_clock(game)
        game.keys("f", delay=1)
        assert bub_pos(game) == position, "f must attack the locked enemy without walking"
        assert action_clock(game) > clock, "f must spend the attack's moves"


def test_right_click_door_lists_free_actions_and_keeps_selection(_g):
    with no_mouse_movement_game("bn-e2e-target-door-menu") as game:
        settle(game)
        empty_inventory(game)
        arena(game)
        see_everything(game, True)
        assert game.lua("M:set_ter_at(here(1,0),TerId.new('t_door_c'):int_id()) out('ok')") == ["ok"]
        before = mouse_state(game)
        x, y = game.find("@")

        game.click(x + 1, y, button=2)
        screen = game.screen()
        assert "Interact with the" in screen, "RMB must list the door's actions:\n" + screen
        assert "open the" in screen and "smash the" in screen, screen
        assert mouse_state(game) == before, "listing actions must not act, move, or spend time"

        game.keys("Escape", delay=0.6)
        game.wait_gone("Interact with the")
        panel = mouse_view(game)
        assert "closed wood door" in panel, "closing the actions must keep the selection:\n" + panel
        assert mouse_state(game) == before, "closing the actions must stay free"

        x, y = game.find("@")
        game.click(x + 1, y, button=2)
        game.wait_for("Interact with the")
        game.keys("o", delay=1)
        assert wait_until(lambda: game.lua(
            "out(M:get_ter_at(here(1,0)):str_id():str())") == ["t_door_o"]), game.screen()
        assert bub_pos(game) == before[1], "opening the selected door must not walk"
        assert action_clock(game) > before[0], "the chosen action keeps its normal move cost"


def test_right_click_distant_door_shows_unreachable_actions(_g):
    with no_mouse_movement_game("bn-e2e-target-door-far") as game:
        settle(game)
        empty_inventory(game)
        arena(game)
        see_everything(game, True)
        assert game.lua("M:set_ter_at(here(3,0),TerId.new('t_door_c'):int_id()) out('ok')") == ["ok"]
        before = mouse_state(game)
        x, y = game.find("@")

        game.click(x + 3, y, button=2)
        screen = game.screen()
        assert "Interact with the" in screen, "RMB must still list what the tile offers:\n" + screen
        assert "You can't reach that tile." in screen, screen
        assert "open the" in screen, screen
        assert mouse_state(game) == before, "listing unreachable actions must stay free"
        # The rows are disabled, so their hotkeys must not run them.
        game.keys("o", delay=0.6)
        assert wait_until(lambda: game.lua(
            "out(M:get_ter_at(here(3,0)):str_id():str())") == ["t_door_c"]), game.screen()
        assert mouse_state(game) == before, "an unreachable action must not run or spend time"
        game.keys("Escape", delay=0.6)
        assert "Mouse View" in game.screen(), "closing the list must keep the selection"


def test_f_without_selection_attacks_an_adjacent_enemy(_g):
    with no_mouse_movement_game("bn-e2e-target-auto-attack") as game:
        settle(game)
        empty_inventory(game)
        arena(game)
        see_everything(game, True)
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(1,0)) "
                        "out(m ~= nil)") == ["true"]
        position = bub_pos(game)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert bub_pos(game) == position, "f must attack in place without walking"
        assert action_clock(game) > clock, "f must spend the attack's moves"


def test_f_without_a_reachable_enemy_does_nothing(_g):
    with no_mouse_movement_game("bn-e2e-target-out-of-reach") as game:
        settle(game)
        empty_inventory(game)
        arena(game)
        see_everything(game, True)
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(2,0)) "
                        "out(m ~= nil and gapi.get_avatar():sees(here(2,0)))") == ["true"], \
            "the unreachable enemy must be visible, or the test proves nothing"
        position = bub_pos(game)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert bub_pos(game) == position, "no reachable enemy must never start walking"
        assert action_clock(game) == clock, "no reachable enemy must spend no moves"
        assert "< Firing " not in game.screen(), "a melee miss must not open gun aiming"


def test_locked_selection_stops_edge_panning(_g):
    with pan_game("bn-e2e-target-lock-pan") as pan:
        empty_inventory(pan)
        arena(pan)
        see_everything(pan, True)
        settle(pan)
        assert pan.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(1,0)) "
                       "out(m ~= nil)") == ["true"]
        x, y = pan.find("@")
        pan.click(x + 1, y, button=2)
        assert "zombie" in mouse_view(pan)
        x_locked, y_player = pan.find("@")
        pan.hover(_right_edge(pan), y_player)
        assert pan.find("@")[0] == x_locked, "a locked selection must stop edge panning the view"
        assert "zombie" in mouse_view(pan), "panning must not replace the locked inspector"
        # Leave the shared panning profile unlocked for the rest of the suite.
        pan.keys("Escape", delay=0.3)


TESTS = [
    test_locked_enemy_freezes_hover_and_fire_targets_it,
    test_right_click_door_lists_free_actions_and_keeps_selection,
    test_right_click_distant_door_shows_unreachable_actions,
    test_f_without_selection_attacks_an_adjacent_enemy,
    test_f_without_a_reachable_enemy_does_nothing,
    test_locked_selection_stops_edge_panning,
]
