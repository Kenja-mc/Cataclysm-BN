from contextlib import contextmanager

from aim_reticle import action_clock
from helpers import HELPERS, arena, bub_pos, count_at, count_carried, empty_inventory, settle, spawn, start_new_game
from safe_click import see_everything
from tmux_game import Game


@contextmanager
def contextual_game(name, **options):
    game = Game(name=name, options={
        "CONTROL_SCHEME": "modern", "CONTEXTUAL_INTERACT": "true",
        "MOUSE_TILE_SELECTION": "true", "MOUSE_MOVE": "false", "SAFEMODE": "false",
        "AUTOSELECT_SINGLE_VALID_TARGET": "false", **options,
    })
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        empty_inventory(game)
        arena(game)
        see_everything(game, True)
        settle(game)
        assert game.lua("local a=gapi.get_avatar() a:set_str_bonus(10) out(a:get_str()>=4)") == ["true"]
        yield game
    finally:
        game.close()


def select_tile(game, dx, dy):
    x, y = game.find("@")
    game.click(x + dx, y + dy, button=2)


def doors(game, selected_dx=1):
    assert game.lua(
        f"M:set_ter_at(here({selected_dx},0),TerId.new('t_door_c'):int_id()) "
        "M:set_ter_at(here(-1,0),TerId.new('t_door_c'):int_id()) out('ok')"
    ) == ["ok"]


def door_state(game, selected_dx=1):
    return game.lua(
        f"out(M:get_ter_at(here({selected_dx},0)):str_id():str(),"
        "M:get_ter_at(here(-1,0)):str_id():str())"
    )


def test_contextual_selected_door_over_nearby(_game):
    with contextual_game("bn-e2e-context-door") as game:
        doors(game)
        before = bub_pos(game)
        clock = action_clock(game)
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        screen = game.screen()
        assert "open the" in screen and "smash the" in screen, screen
        game.keys("o", delay=1)
        assert bub_pos(game) == before, "opening the selected door must not walk"
        assert door_state(game) == ["t_door_o,t_door_c"], "only the selected door opens"
        assert action_clock(game) > clock, "normal door opening still spends moves"
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        assert "close the" in game.screen(), game.screen()
        game.keys("c", delay=1)
        assert door_state(game) == ["t_door_c,t_door_c"]
        assert bub_pos(game) == before, "closing the selected door must not walk"


def test_contextual_menu_cancel_is_free(_game):
    with contextual_game("bn-e2e-context-cancel") as game:
        doors(game)
        before = bub_pos(game)
        clock = action_clock(game)
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        assert "smash the" in game.screen(), game.screen()
        game.keys("Escape", delay=0.8)
        assert door_state(game) == ["t_door_c,t_door_c"], "Space must not auto-smash or open"
        assert bub_pos(game) == before
        assert action_clock(game) == clock, "canceling the action menu must be free"


def test_contextual_selected_jump(_game):
    with contextual_game("bn-e2e-context-jump") as game:
        # Bare floor avoids jump RNG.
        before = bub_pos(game)
        clock = action_clock(game)
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        assert "jump over the" in game.screen(), game.screen()
        game.keys("j", delay=1)
        assert bub_pos(game) == (before[0] + 2, before[1], before[2]), "jump crosses the selected tile"
        assert action_clock(game) > clock, "jump keeps its existing move cost"


def test_contextual_smash_only_selected_tile(_game):
    with contextual_game("bn-e2e-context-smash") as game:
        # Webs bash deterministically at this strength.
        assert game.lua(
            "for _,dx in ipairs({-1,1}) do "
            "M:add_field_at(here(dx,0),FieldTypeId.new('fd_web'):int_id(),1,TimeDuration.from_turns(0)) "
            "end out('ok')"
        ) == ["ok"]
        before = bub_pos(game)
        clock = action_clock(game)
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        assert "smash the" in game.screen(), game.screen()
        game.keys("S", delay=1)
        assert game.lua(
            "out(M:has_field_at(here(1,0),FieldTypeId.new('fd_web'):int_id()),"
            "M:has_field_at(here(-1,0),FieldTypeId.new('fd_web'):int_id()))"
        ) == ["false,true"], "explicit smash must touch only the selected tile"
        assert bub_pos(game) == before
        assert action_clock(game) > clock


def test_contextual_distant_selection_does_not_fall_back(_game):
    with contextual_game("bn-e2e-context-distant") as game:
        doors(game, selected_dx=3)
        before = bub_pos(game)
        clock = action_clock(game)
        select_tile(game, 3, 0)
        game.keys("space", delay=0.8)
        assert door_state(game, selected_dx=3) == ["t_door_c,t_door_c"]
        assert bub_pos(game) == before, "an unreachable selection must not start travel"
        assert action_clock(game) == clock, "an unreachable selection must not act elsewhere"


def test_contextual_no_selection_keeps_direction_prompt(_game):
    with contextual_game("bn-e2e-context-direction") as game:
        doors(game)
        before = bub_pos(game)
        game.keys("space", delay=0.8)
        assert "Interact with which tile?" in game.screen(), game.screen()
        game.keys("a", delay=0.8)
        assert "open the" in game.screen(), game.screen()
        game.keys("o", delay=1)
        assert door_state(game) == ["t_door_c,t_door_o"]
        assert bub_pos(game) == before


def test_contextual_disabled_and_classic_keep_legacy_examine(_game):
    for scheme, contextual, key in (("modern", "false", "space"), ("classic", "true", "e")):
        with contextual_game(f"bn-e2e-context-legacy-{scheme}", CONTROL_SCHEME=scheme,
                             CONTEXTUAL_INTERACT=contextual) as game:
            doors(game)
            before = bub_pos(game)
            clock = action_clock(game)
            select_tile(game, 1, 0)
            game.keys(key, delay=0.8)
            assert "Examine where?" in game.screen(), game.screen()
            game.keys("Escape", delay=0.8)
            assert door_state(game) == ["t_door_c,t_door_c"]
            assert bub_pos(game) == before
            assert action_clock(game) == clock


def test_contextual_selected_pickup_uses_action_menu(_game):
    with contextual_game("bn-e2e-context-pickup") as game:
        spawn(game, 1, 0, "rock")
        spawn(game, -1, 0, "stick")
        before = bub_pos(game)
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        screen = game.screen()
        assert "pick up items" in screen and "examine the" in screen, screen
        game.keys("g", delay=1)
        assert "Pick up" in game.screen(), game.screen()
        game.keys("g", delay=1)
        assert count_carried(game, "rock") == 1
        assert count_at(game, 1, 0, "rock") == 0
        assert count_at(game, -1, 0, "stick") == 1
        assert bub_pos(game) == before


def test_contextual_direction_rejects_unseen_tiles(_game):
    with contextual_game("bn-e2e-context-unseen", SHOW_TIPS="false",
                         SHOW_WELCOME="false") as game:
        see_everything(game, False)
        assert game.lua("local a=gapi.get_avatar() "
                        "a:add_effect(EffectTypeId.new('blind'),TimeDuration.from_hours(1)) "
                        "out(a:is_blind())") == ["true"]
        settle(game)
        assert game.lua(
            "M:set_ter_at(here(1,0),TerId.new('t_door_c'):int_id()) "
            "M:add_field_at(here(0,0),FieldTypeId.new('fd_web'):int_id(),1,TimeDuration.from_turns(0)) "
            "M:create_item_at(here(0,0),ItypeId.new('rock'),-1) "
            "out(gapi.get_avatar():sees(here(0,0)),gapi.get_avatar():sees(here(1,0)))"
        ) == ["true,false"]
        position, clock = bub_pos(game), action_clock(game)
        game.keys("space", delay=0.8)
        prompt = game.screen()
        assert "Interact with which tile?" in prompt, prompt
        assert not any("door" in line.lower() for line in prompt.splitlines()
                       if "smash the" in line), "contextual choices exposed an unseen door:\n" + prompt
        game.keys("d", "S", delay=0.8)
        assert game.lua("out(M:get_ter_at(here(1,0)):str_id():str())") == ["t_door_c"]
        assert bub_pos(game) == position
        assert action_clock(game) == clock, "an unseen direction must not dispatch an action"


TESTS = [
    test_contextual_selected_door_over_nearby,
    test_contextual_menu_cancel_is_free,
    test_contextual_selected_jump,
    test_contextual_smash_only_selected_tile,
    test_contextual_distant_selection_does_not_fall_back,
    test_contextual_no_selection_keeps_direction_prompt,
    test_contextual_disabled_and_classic_keep_legacy_examine,
    test_contextual_selected_pickup_uses_action_menu,
    test_contextual_direction_rejects_unseen_tiles,
]
