import re
from contextlib import contextmanager

from agent_actions import actions_for, classify_screen, menu_rows
from aim_reticle import action_clock
from fixtures import shared_game
from helpers import HELPERS, arena, bub_pos, count_at, count_carried, empty_inventory, settle, spawn, wait_until
from safe_click import see_everything


def contextual_setup(game):
    # Effects, fields and view state survive from the previous test on the shared profile game.
    assert game.lua("gapi.get_avatar():clear_effects() "
                    "for dx=-4,4 do for dy=-4,4 do local p=here(dx,dy) M:remove_trap_at(p) "
                    "for _,fid in ipairs(M:get_field_ids_at(p)) do M:remove_field_at(p,fid) end "
                    "end end out('ok')") == ["ok"]
    empty_inventory(game)
    arena(game)
    see_everything(game, True)
    settle(game)
    assert game.lua("local a=gapi.get_avatar() a:set_str_bonus(10) out(a:get_str()>=4)") == ["true"]


@contextmanager
def contextual_game(name, **options):
    with shared_game(name, define=HELPERS, setup=contextual_setup, options={
        "CONTROL_SCHEME": "modern", "CONTEXTUAL_INTERACT": "true",
        "MOUSE_TILE_SELECTION": "true", "MOUSE_MOVE": "false", "SAFEMODE": "false",
        "AUTOSELECT_SINGLE_VALID_TARGET": "false", **options,
    }) as game:
        yield game


def select_tile(game, dx, dy):
    x, y = game.find("@")
    game.click(x + dx, y + dy, button=2)
    # Modern right click also lists a reachable object's actions. These tests exercise the
    # Space route, so close that list and keep the selection before pressing Space.
    if "Interact with the" in game.screen():
        game.keys("Escape", delay=0.3)
        game.wait_gone("Interact with the")


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


def test_contextual_selected_door_opens_without_a_menu(_game):
    with contextual_game("bn-e2e-context-door") as game:
        doors(game)
        before = bub_pos(game)
        clock = action_clock(game)
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        assert "Interact with" not in game.screen(), \
            "a door is the obvious action and must not open a menu:\n" + game.screen()
        assert door_state(game) == ["t_door_o,t_door_c"], "only the selected door opens"
        assert action_clock(game) > clock, "normal door opening still spends moves"
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        assert door_state(game) == ["t_door_c,t_door_c"], "the same tile closes again"
        assert bub_pos(game) == before, "neither opening nor closing walks"


def test_contextual_selected_vault_over_obstacle(_game):
    with contextual_game("bn-e2e-context-jump") as game:
        assert game.lua("M:set_furn_at(here(1,0), FurnId.new('f_sandbag_half'):int_id()) "
                        "out('ok')") == ["ok"]
        before = bub_pos(game)
        clock = action_clock(game)
        select_tile(game, 1, 0)
        game.keys("space", delay=1.2)
        assert bub_pos(game) == (before[0] + 2, before[1], before[2]), \
            f"a lone climbable obstacle vaults: {before} -> {bub_pos(game)}\n" + game.screen()
        assert action_clock(game) > clock, "jump keeps its existing move cost"


def test_contextual_attack_key_smashes_aimed_terrain(_game):
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
        game.keys("f", delay=1)
        assert game.lua(
            "out(M:has_field_at(here(1,0),FieldTypeId.new('fd_web'):int_id()),"
            "M:has_field_at(here(-1,0),FieldTypeId.new('fd_web'):int_id()))"
        ) == ["false,true"], "the attack key must smash only the aimed tile"
        assert bub_pos(game) == before
        assert action_clock(game) > clock, "smashing spends the same moves it always did"


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


def interact_menu(game):
    """The rows of Space's "Interact with what?" list, as {label: hotkey}, with the capture."""
    game.wait_for("Interact with what?")
    game.settle_screen()
    screen = game.screen()
    rows = {row.label: row.hotkey for row in menu_rows(screen, limit=len(screen.splitlines()))}
    assert rows, "the nearby interaction menu must contain actionable rows:\n" + screen
    return rows, screen


def colored_cells(line):
    """Visible cells and their effective SGR state from a real tmux color capture."""
    state = {"fg": 39, "bg": 49, "bold": False, "reverse": False}
    cells = []
    cursor = 0
    while cursor < len(line):
        match = re.match(r"\x1b\[([0-9;]*)m", line[cursor:])
        if match:
            codes = [int(code or 0) for code in match.group(1).split(";")]
            index = 0
            while index < len(codes):
                code = codes[index]
                if code == 0:
                    state = {"fg": 39, "bg": 49, "bold": False, "reverse": False}
                elif code in (1, 22):
                    state["bold"] = code == 1
                elif code in (7, 27):
                    state["reverse"] = code == 7
                elif code in (38, 48):
                    count = 3 if codes[index + 1] == 5 else 5
                    state["fg" if code == 38 else "bg"] = tuple(codes[index:index + count])
                    index += count - 1
                elif 30 <= code <= 37 or 90 <= code <= 97 or code == 39:
                    state["fg"] = code
                elif 40 <= code <= 47 or 100 <= code <= 107 or code == 49:
                    state["bg"] = code
                index += 1
            cursor += match.end()
        else:
            cells.append((line[cursor], dict(state)))
            cursor += 1
    return cells


def test_contextual_no_selection_lists_nearby_actions(_game):
    with contextual_game("bn-e2e-context-direction") as game:
        doors(game)
        before = bub_pos(game)
        game.keys("space", delay=0.2)
        rows, screen = interact_menu(game)
        assert "Interact with which tile?" not in screen, "the direction prompt is gone:\n" + screen
        menu = classify_screen(screen)
        assert menu not in ("game", "tutorial", "unknown"), \
            "the open nearby list must be classified as a menu:\n" + screen
        actions = {action.id for action in actions_for(
            menu, mode="exact", scheme="modern", text=screen, colored=game.screen_colors())}
        assert {"menu_select", "menu_cancel"} <= actions, actions
        assert all("press_" + key in actions for key in rows.values()), \
            f"the real nearby rows must be actionable by the decision model: {actions}\n{screen}"
        east = [label for label in rows if label.startswith("open the") and label.endswith("(east)")]
        west = [label for label in rows if label.startswith("open the") and label.endswith("(west)")]
        assert len(east) == 1 and len(west) == 1, f"both doors must be listed with their side: {rows}\n{screen}"
        game.keys(rows[west[0]], delay=0.2)
        game.wait_gone("Interact with what?")
        assert door_state(game) == ["t_door_c,t_door_o"], "the picked row opens only the west door"
        assert bub_pos(game) == before



def test_contextual_nearby_row_highlights_its_tile(_game):
    with contextual_game("bn-e2e-context-highlight") as game:
        doors(game)
        position, clock = bub_pos(game), action_clock(game)
        x, y = game.find("@")

        def door_styles():
            cells = colored_cells(game.screen_colors().splitlines()[y])
            return cells[x - 1][1], cells[x + 1][1]

        baseline = door_styles()
        game.keys("space", delay=0.2)
        rows, screen = interact_menu(game)
        east = next(label for label in rows if label.startswith("open the") and label.endswith("(east)"))
        west = next(label for label in rows if label.startswith("open the") and label.endswith("(west)"))
        styles = {}
        for direction, label, index in (("east", east, 1), ("west", west, 0)):
            row = next(row for row in menu_rows(game.screen()) if row.label == label)
            game.hover(row.x, row.y)
            assert wait_until(lambda: (current := door_styles())[index] != baseline[index]
                              and current[1 - index] == baseline[1 - index]), \
                f"hovering the {direction} row must highlight only its tile:\n" + game.screen()
            styles[direction] = door_styles()
        assert styles["east"][0] != styles["west"][0], "west tile must light up when its row is focused:\n" + screen
        assert styles["east"][1] != styles["west"][1], "east tile must stop being highlighted:\n" + screen
        game.keys("Escape", delay=0.2)
        game.wait_gone("Interact with what?")
        assert door_state(game) == ["t_door_c,t_door_c"]
        assert (bub_pos(game), action_clock(game)) == (position, clock), \
            "previewing rows must not act, walk or spend time"

def test_contextual_space_uses_the_last_moved_direction(_game):
    with contextual_game("bn-e2e-context-faced") as game:
        # A step east leaves that tile as the one Space acts on when nothing is aimed.
        game.keys("d", delay=0.9)
        spawn(game, 1, 0, "rock")
        settle(game)
        game.keys("space", delay=0.8)
        assert wait_until(lambda: count_carried(game, "rock") == 1), \
            "the faced tile is acted on without the nearby list:\n" + game.screen()


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


def test_contextual_selected_pickup_takes_or_lists(_game):
    with contextual_game("bn-e2e-context-pickup") as game:
        spawn(game, 1, 0, "rock")
        before = bub_pos(game)
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        assert wait_until(lambda: count_carried(game, "rock") == 1), game.screen()
        assert "Pick up" not in game.screen(), "a lone item needs no picker"
        assert bub_pos(game) == before
        spawn(game, 1, 0, "rock")
        spawn(game, 1, 0, "stick")
        select_tile(game, 1, 0)
        game.keys("space", delay=0.8)
        game.wait_for("Pick up")
        game.keys("Escape", delay=0.6)


def test_pickup_keys_take_a_lone_item_and_list_a_pile(_game):
    with contextual_game("bn-e2e-context-pickup-keys") as game:
        spawn(game, 1, 0, "rock")
        select_tile(game, 1, 0)
        game.keys("g", delay=1.0)
        assert wait_until(lambda: count_carried(game, "rock") == 1), game.screen()
        spawn(game, 1, 0, "rock")
        spawn(game, 1, 0, "stick")
        select_tile(game, 1, 0)
        game.keys("G", delay=0.8)
        game.wait_for("Pick up")
        game.keys("Escape", delay=0.6)


def test_contextual_nearby_list_skips_unseen_tiles(_game):
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
        game.keys("space", delay=0.2)
        rows, screen = interact_menu(game)
        assert rows and all(label.endswith("(here)") for label in rows), \
            "only the seen tile underfoot may be offered:\n" + screen
        assert not any("door" in label.lower() for label in rows), \
            "contextual choices exposed an unseen door:\n" + screen
        game.keys("Escape", delay=0.2)
        game.wait_gone("Interact with what?")
        assert game.lua("out(M:get_ter_at(here(1,0)):str_id():str())") == ["t_door_c"]
        assert bub_pos(game) == position
        assert action_clock(game) == clock, "canceling the nearby list must not dispatch an action"


TESTS = [
    test_contextual_selected_door_opens_without_a_menu,
    test_contextual_selected_vault_over_obstacle,
    test_contextual_attack_key_smashes_aimed_terrain,
    test_contextual_distant_selection_does_not_fall_back,
    test_contextual_no_selection_lists_nearby_actions,
    test_contextual_nearby_row_highlights_its_tile,
    test_contextual_space_uses_the_last_moved_direction,
    test_contextual_disabled_and_classic_keep_legacy_examine,
    test_contextual_selected_pickup_takes_or_lists,
    test_pickup_keys_take_a_lone_item_and_list_a_pile,
    test_contextual_nearby_list_skips_unseen_tiles,
]
