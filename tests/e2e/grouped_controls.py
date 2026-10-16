import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from aim_reticle import action_clock
from helpers import HELPERS, arena, bub_pos, empty_inventory, settle, start_new_game
from map_mouse import firing_target_panel, mouse_state, no_mouse_movement_game
from safe_click import see_everything
from tmux_game import Game


DIRECTIONS = (("W", 0, -1), ("E", 1, -1), ("D", 1, 0), ("C", 1, 1),
              ("S", 0, 1), ("Z", -1, 1), ("A", -1, 0), ("Q", -1, -1))


def mouse_view(game):
    screen = game.screen()
    lines = screen.splitlines()
    top = next((y for y, line in enumerate(lines) if "Mouse View" in line), None)
    assert top is not None, "selection must show the actual tile inspector:\n" + screen
    title = lines[top].index("Mouse View")
    left = max(lines[top].rfind(corner, 0, title) for corner in ("╭", "┌", "+"))
    assert left >= 0, screen
    right = len(lines[top].rstrip())
    bottom = next((y for y in range(top + 1, len(lines))
                   if lines[y][left:left + 1] in ("╰", "└", "+")), None)
    assert bottom is not None, screen
    return "\n".join(line[left:right] for line in lines[top:bottom + 1])


def mark_direction(game, dx, dy):
    game.keys("Tab", delay=0.5)
    assert game.lua(
        "for dx=-1,1 do for dy=-1,1 do M:set_ter_at(here(dx,dy),TerId.new('t_floor'):int_id()) end end "
        f"M:set_ter_at(here({dx},{dy}),TerId.new('t_pavement'):int_id()) out('ok')"
    ) == ["ok"]


def test_grouped_shift_direction_looks_without_walking(_game):
    with no_mouse_movement_game("bn-e2e-grouped-look", ARROW_KEY_AIM="false") as game:
        for key, dx, dy in DIRECTIONS:
            mark_direction(game, dx, dy)
            before = bub_pos(game), action_clock(game)
            game.keys(key, delay=0.8)
            assert "pavement" in mouse_view(game), f"Shift+{key} must inspect direction {(dx, dy)}"
            assert (bub_pos(game), action_clock(game)) == before, "looking must be free and stationary"


def test_grouped_look_selects_the_space_interaction_tile(_game):
    with no_mouse_movement_game("bn-e2e-grouped-look-interact") as game:
        assert game.lua("for _,dx in ipairs({-1,1}) do "
                        "M:set_ter_at(here(dx,0),TerId.new('t_door_c'):int_id()) end out('ok')") == ["ok"]
        before = bub_pos(game)
        game.keys("D", "space", delay=0.8)
        game.keys("o", delay=1)
        assert game.lua("out(M:get_ter_at(here(1,0)):str_id():str(),"
                        "M:get_ter_at(here(-1,0)):str_id():str())") == ["t_door_o,t_door_c"]
        assert bub_pos(game) == before, "Space must open the looked-at door without walking"


def test_grouped_ctrl_direction_peeks_and_restores_position(_game):
    with no_mouse_movement_game("bn-e2e-grouped-peek") as game:
        for key, dx, dy in DIRECTIONS:
            mark_direction(game, dx, dy)
            before, clock = bub_pos(game), action_clock(game)
            game.keys("C-" + key.lower(), delay=0.8)
            assert "pavement" in game.screen(), f"Ctrl+{key} must peek from direction {(dx, dy)}:\n" + game.screen()
            game.keys("Escape", delay=1)
            assert bub_pos(game) == before, "physical peeking must restore the avatar's position"
            assert action_clock(game) > clock, "peeking keeps its normal time cost"


def test_grouped_shift_x_cycles_all_movement_modes(_game):
    with no_mouse_movement_game("bn-e2e-grouped-stances") as game:
        before = bub_pos(game)
        for mode in ("Running", "Crouching", "Prone", "Walking"):
            game.keys("X", delay=1)
            assert any(mode in line for line in game.screen().splitlines()[:15]), (
                "the HUD must show the next movement mode " + mode + ":\n" + game.screen())
            assert bub_pos(game) == before, "changing movement mode must not move the avatar"


def test_grouped_tab_cycles_visible_hostiles_and_wraps(_game):
    with no_mouse_movement_game("bn-e2e-grouped-targets") as game:
        assert game.lua("local a=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(1,0)) "
                        "local b=gapi.place_monster_at(MonsterTypeId.new('mon_zombie_rot'),here(-3,0)) "
                        "MAP_MOUSE_TARGETS={a,b} out(a ~= nil and b ~= nil)") == ["true"]
        before = bub_pos(game), action_clock(game)
        for key, decayed in (("Tab", False), ("Tab", True), ("Tab", False),
                             ("BTab", True), ("BTab", False)):
            game.keys(key, delay=0.8)
            panel = mouse_view(game)
            assert "zombie" in panel and ("decayed zombie" in panel) == decayed, panel
            assert (bub_pos(game), action_clock(game)) == before, "target cycling must not act or move"
        assert game.lua("M:set_ter_at(here(-1,0),TerId.new('t_wall'):int_id()) out('ok')") == ["ok"]
        game.keys("Tab", delay=0.8)
        panel = mouse_view(game)
        assert "zombie" in panel and "decayed zombie" not in panel, "hidden hostiles must be skipped"
        game.keys("f", delay=1)
        assert bub_pos(game) == before[0]
        assert action_clock(game) > before[1], "f must attack the cycled adjacent target"
        assert game.lua("for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end out('ok')") == ["ok"]
        empty = bub_pos(game), action_clock(game)
        game.keys("Tab", delay=0.8)
        assert "Mouse View" not in game.screen(), "no hostile targets must clear the selection"
        assert (bub_pos(game), action_clock(game)) == empty


def loaded_gun_and_east_hostile(game):
    assert game.lua("local a=gapi.get_avatar() GROUPED_GUN=a:create_item(ItypeId.new('model_10_revolver'),-1) "
                    "GROUPED_GUN:ammo_set(ItypeId.new('38_special'),6) "
                    "out(a:wield(GROUPED_GUN))") == ["true"]
    settle(game)
    assert game.lua("for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end "
                    "local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie_rot'),here(3,0)) "
                    "MAP_MOUSE_TARGETS={m} out(m ~= nil)") == ["true"]


def grouped_gun_state(game):
    return mouse_state(game), game.lua("out(GROUPED_GUN:ammo_remaining())")


def test_grouped_fire_from_empty_inspection_aims_at_hostile(_game):
    with no_mouse_movement_game("bn-e2e-grouped-empty-gun-aim") as game:
        loaded_gun_and_east_hostile(game)
        before = grouped_gun_state(game)
        for selection in ("shift", "mouse", "arrows"):
            if selection == "shift":
                game.keys("W", delay=0.8)
            elif selection == "mouse":
                x, y = game.find("@")
                game.click(x, y - 1, button=2)
            else:
                # First arrow snaps to the eastern hostile.
                game.keys("Up", "Left", "Left", "Left", "Up", delay=0.5)
            assert "zombie" not in mouse_view(game), "the inspection tile must be empty"
            assert grouped_gun_state(game) == before, "inspection must be free"
            game.keys("f", delay=1)
            panel = firing_target_panel(game)
            assert "decayed zombie" in panel, "f must aim at the actual hostile:\n" + panel
            game.keys("Escape", delay=0.6)
            assert "Mouse View" not in game.screen(), "normal gun aiming must clear inspection"
            assert grouped_gun_state(game) == before, "cancel must preserve ammo, health, position and time"


def test_grouped_distant_melee_selection_never_redirects_or_walks(_game):
    with no_mouse_movement_game("bn-e2e-grouped-distant-melee") as game:
        assert game.lua("local near=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(1,0)) "
                        "local selected=gapi.place_monster_at(MonsterTypeId.new('mon_zombie_rot'),here(0,-3)) "
                        "MAP_MOUSE_TARGETS={near,selected} out(near ~= nil and selected ~= nil)") == ["true"]
        before = mouse_state(game)
        game.keys("W", "W", "W", delay=0.5)
        assert "decayed zombie" in mouse_view(game), "the distant hostile must be selected"
        game.keys("f", delay=0.8)
        assert "reach" in game.screen(), "a distant melee target needs an informative rejection"
        assert mouse_state(game) == before, "out-of-reach melee must not attack another tile or walk"


def test_grouped_direct_empty_or_friendly_gun_click_never_retargets(_game):
    with no_mouse_movement_game("bn-e2e-grouped-direct-empty-gun") as game:
        loaded_gun_and_east_hostile(game)
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_dog'),here(0,1)) "
                        "m:make_friendly() MAP_MOUSE_TARGETS[2]=m out(m ~= nil)") == ["true"]
        before = grouped_gun_state(game)
        for dy in (-1, 1):
            x, y = game.find("@")
            game.click(x, y + dy)
            assert "< Firing " not in game.screen(), "direct clicks must not aim at another tile"
            assert grouped_gun_state(game) == before, "direct clicks must not fire, damage, walk or spend time"


def change_grouped_control_scheme(game, save):
    # Esc clears inspection; use an options hotkey.
    game.keys("F6", delay=0.8)
    game.wait_for(" OPTIONS ")
    header = next(((line.index("[Interface]") + 2, y)
                   for y, line in enumerate(game.screen().splitlines())
                   if "[Interface]" in line), None)
    assert header is not None, game.screen()
    game.click(*header)
    for _ in range(180):
        screen = game.screen()
        row = next(((line.index("Control scheme"), y)
                    for y, line in enumerate(screen.splitlines())
                    if re.search(r"│\s*\d+\s*│\s*(?:>>\s*)?Control scheme\s*│", line)), None)
        if row:
            game.hover(*row)
            assert re.search(r"Control scheme\s*│\s*Modern \(WASD\)", game.screen()), game.screen()
            game.keys("Right", delay=0.3)
            assert re.search(r"Control scheme\s*│\s*Classic", game.screen()), game.screen()
            break
        selected = next((line for line in screen.splitlines() if ">>" in line), "")
        if re.search(r">>\s*\+", selected):
            game.keys("Right", delay=0.1)
        game.keys("Down", delay=0.05)
    else:
        raise AssertionError("could not locate Control scheme:\n" + game.screen())
    game.keys("Escape", delay=0.5)
    game.wait_for("Save changes?")
    game.keys("y" if save else "n", "Enter", delay=0.7)
    return game.screen()


def test_grouped_live_classic_switch_clears_inspection_before_fire(_game):
    with TemporaryDirectory(prefix="bn-e2e-grouped-options-") as directory:
        bindings = Path(directory) / "keybindings.json"
        bindings.write_text(json.dumps([{
            "type": "keybinding", "id": "open_options", "category": "DEFAULTMODE",
            "bindings": [{"input_method": "keyboard", "key": "F6"}],
        }]))
        game = Game(name="bn-e2e-grouped-live-classic", keybindings=str(bindings),
                    options={"CONTROL_SCHEME": "modern", "MOUSE_MOVE": "false",
                             "ARROW_KEY_AIM": "true", "MOUSE_TILE_SELECTION": "true",
                             "SAFEMODE": "false"})
        try:
            start_new_game(game)
            game.define_lua(HELPERS)
            empty_inventory(game)
            arena(game)
            see_everything(game, True)
            loaded_gun_and_east_hostile(game)
            before = grouped_gun_state(game)
            game.keys("W", delay=0.8)
            assert "zombie" not in mouse_view(game)
            change_grouped_control_scheme(game, save=False)
            # Esc proves the canceled switch kept inspection.
            game.keys("Escape", delay=0.7)
            assert "MAIN MENU" not in game.screen(), "canceling options must preserve inspection"
            assert grouped_gun_state(game) == before
            game.keys("W", delay=0.8)
            assert "zombie" not in mouse_view(game)
            screen = change_grouped_control_scheme(game, save=True)
            assert "Mouse View" not in screen, "a saved scheme switch must clear the live inspector"
            game.keys("f", delay=1)
            panel = firing_target_panel(game)
            assert "decayed zombie" in panel, "Classic f must use ordinary gun aiming:\n" + panel
            game.keys("Escape", delay=0.6)
            assert grouped_gun_state(game) == before, "switching and canceling aim must be free"
        finally:
            game.close()


TESTS = [test_grouped_shift_direction_looks_without_walking,
         test_grouped_look_selects_the_space_interaction_tile,
         test_grouped_ctrl_direction_peeks_and_restores_position,
         test_grouped_shift_x_cycles_all_movement_modes,
         test_grouped_tab_cycles_visible_hostiles_and_wraps,
         test_grouped_fire_from_empty_inspection_aims_at_hostile,
         test_grouped_distant_melee_selection_never_redirects_or_walks,
         test_grouped_direct_empty_or_friendly_gun_click_never_retargets,
         test_grouped_live_classic_switch_clears_inspection_before_fire]
