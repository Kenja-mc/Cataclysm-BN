"""RMB selects for free; LMB acts on nearby usable tiles or attacks, never walks."""
from contextlib import contextmanager
import re

from aim_reticle import action_clock
from fixtures import shared_game
from helpers import HELPERS, arena, bub_pos, empty_inventory, settle
from safe_click import see_everything


def no_mouse_setup(game):
    # Activate queued NPCs before they can escape the sweep and steal the clicked "@".
    settle(game)
    empty_inventory(game)
    arena(game)
    see_everything(game, True)
    assert game.lua("local a=gapi.get_avatar() "
                    # Stun redirects an attack's movement step.
                    "a:clear_effects() "
                    "for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end "
                    "for _,n in ipairs(gapi.get_all_npcs()) do park(n) end "
                    "MAP_MOUSE_TARGETS={} "
                    "for dx=-4,4 do for dy=-4,4 do local p=here(dx,dy) "
                    "M:remove_trap_at(p) "
                    "for _,fid in ipairs(M:get_field_ids_at(p)) do M:remove_field_at(p,fid) end "
                    "end end out('ok')") == ["ok"]
    settle(game)
    # Keep every clicked "@" unambiguously the avatar.
    assert game.lua("local a=gapi.get_avatar():get_pos_ms() local n=0 "
                    "for _,cr in ipairs(gapi.get_all_creatures()) do "
                    "if not cr:is_avatar() then local p=cr:get_pos_ms() "
                    "if math.abs(p.x-a.x)<=13 and math.abs(p.y-a.y)<=13 and p.z==a.z then "
                    "n=n+1 end end end out(n)") == ["0"], \
        "a creature arrived after the fixture sweep:\n" + game.screen()


@contextmanager
def no_mouse_movement_game(name, mouse_move="false", **options):
    game_options = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false",
                    "MOUSE_TILE_SELECTION": "true", "ARROW_KEY_AIM": "true",
                    "SAFE_CLICK_WALK": "true", **options}
    if mouse_move is not None:
        game_options["MOUSE_MOVE"] = mouse_move
    with shared_game(name, options=game_options, define=HELPERS, setup=no_mouse_setup) as game:
        yield game


def mouse_state(game):
    """Observe turns, position, and both sides' health without assuming attacks hit.

    One console round trip, not three: the click tests sample this several times per tile
    and the console costs about a second per call on a loaded runner.
    """
    parts = game.lua(
        "local a=gapi.get_avatar() local steps=-a:get_moves() local p=a:abs_pos() "
        "local hp={a:get_hp()} "
        "for _,m in ipairs(MAP_MOUSE_TARGETS) do hp[#hp+1]=m:get_hp() end "
        "out(gapi.current_turn():to_turn(), steps, p.x, p.y, p.z, table.concat(hp,','))"
    )[0].split(",")
    turn, moves, x, y, z = (int(v) for v in parts[:5])
    return ((turn, moves), (x, y, z), parts[5:])


def firing_target_panel(game):
    """Read only the framed firing window, not the sidebar's other creature names."""
    screen = game.screen()
    lines = screen.splitlines()
    titles = [(y, line.index("< Firing ")) for y, line in enumerate(lines) if "< Firing " in line]
    assert len(titles) == 1, "expected the actual firing window:\n" + screen
    top, title = titles[0]
    left = title - 2
    right = len(lines[top].rstrip())
    bottom = next((y for y in range(top + 1, len(lines))
                   if lines[y][left:left + 1] in ("└", "╰", "+")), None)
    assert bottom is not None, "expected the firing window's bottom border:\n" + screen
    return "\n".join(line[left:right] for line in lines[top:bottom + 1])


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


def assert_no_map_context(game):
    screen = game.screen()
    assert not any(title in screen for title in ("Interact with what?", "Interact with the ")), \
        "selection must not open an interaction menu:\n" + screen
    assert not re.search(r"│\s*\S\s+(?:open the|close the|pick up items|examine the)\b[^│]*│", screen), \
        "selection must not offer action rows:\n" + screen


def assert_clicks_are_free(game, dx, dy):
    before = mouse_state(game)
    x, y = game.find("@")
    for button in (0, 2):
        game.click(x + dx, y + dy, button=button)
        assert_no_map_context(game)
        assert mouse_state(game) == before, f"button {button} at {(dx, dy)} must not act or move"
        # No intervening key or console call between these clicks: confirmation must not enable travel.
        game.click(x + dx, y + dy, button=button)
        game.click(x + dx, y + dy, button=button)
        assert_no_map_context(game)
        assert mouse_state(game) == before, f"repeated button {button} at {(dx, dy)} must not act or move"


def exercise_no_mouse_movement(game):
    assert_clicks_are_free(game, 1, 0)
    assert_clicks_are_free(game, 3, 0)
    assert game.lua("out(M:add_field_at(here(3,0),FieldTypeId.new('fd_acid'):int_id(),"
                    "3,TimeDuration.from_turns(0)))") == ["true"]
    assert_clicks_are_free(game, 3, 0)
    assert game.lua("M:remove_field_at(here(3,0),FieldTypeId.new('fd_acid'):int_id()) "
                    "local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(-3,0)) "
                    "MAP_MOUSE_TARGETS={m} out(m ~= nil)") == ["true"]
    assert_clicks_are_free(game, 1, 0)
    assert_clicks_are_free(game, 3, 0)
    assert_clicks_are_free(game, -3, 0)



def test_map_clicks_never_move(_g):
    for safe, mouse_move in (("true", None), ("false", "false")):
        with no_mouse_movement_game(f"bn-e2e-map-no-move-{safe}", mouse_move=mouse_move,
                                    SAFE_CLICK_WALK=safe) as game:
            exercise_no_mouse_movement(game)


def test_legacy_map_clicks_never_move(_g):
    with no_mouse_movement_game("bn-e2e-legacy-no-move", MOUSE_TILE_SELECTION="false",
                                SAFE_CLICK_WALK="false") as game:
        exercise_no_mouse_movement(game)


def test_right_click_locks_enemies_and_opens_object_actions(_g):
    with no_mouse_movement_game("bn-e2e-map-select-no-context") as game:
        assert game.lua("local a=gapi.get_avatar() local w=a:create_item(ItypeId.new('model_10_revolver'),-1) "
                        "w:ammo_set(ItypeId.new('38_special'),6) out(a:wield(w))") == ["true"]
        settle(game)
        assert game.lua("M:set_ter_at(here(1,0),TerId.new('t_door_o'):int_id()) "
                        "local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(3,0)) "
                        "MAP_MOUSE_TARGETS={m} out(m ~= nil)") == ["true"]
        before = mouse_state(game)
        # An enemy right click only locks: no aim window, no action list.
        x, y = game.find("@")
        game.click(x + 3, y, button=2)
        assert "< Firing " not in game.screen(), "RMB selects an armed target without entering aim"
        assert_no_map_context(game)
        assert "Mouse View" in game.screen(), "RMB must inspect the selected tile:\n" + game.screen()
        assert mouse_state(game) == before, "RMB selection must not act, move, or damage either creature"
        # An object right click lists its actions at once, still for free.
        x, y = game.find("@")
        game.click(x + 1, y, button=2)
        screen = game.screen()
        assert "Interact with the" in screen, "RMB must list the door's actions:\n" + screen
        assert "close the" in screen and "smash the" in screen, screen
        assert mouse_state(game) == before, "listing actions must not act, move, or spend time"
        game.keys("Escape", delay=0.6)
        game.wait_gone("Interact with the")
        assert "Mouse View" in game.screen(), "closing the actions must keep the selection"
        assert mouse_state(game) == before, "closing the actions must stay free"
        game.keys("Escape", delay=0.6)
        assert "Mouse View" not in game.screen(), "Escape must clear the kept selection"


def test_mouse_selects_when_arrow_aim_disabled(_g):
    with no_mouse_movement_game("bn-e2e-mouse-no-arrow-aim", ARROW_KEY_AIM="false") as game:
        # Pin arrows to walking first, then prove that mouse selection still creates an attack reticle.
        start = bub_pos(game)
        game.keys("Right", delay=1)
        assert bub_pos(game) == (start[0] + 1, start[1], start[2])
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(1,0)) "
                        "MAP_MOUSE_TARGETS={m} out(m ~= nil)") == ["true"]
        before = mouse_state(game)
        x, y = game.find("@")
        game.click(x + 1, y, button=2)
        panel = mouse_view(game)
        assert "zombie" in panel, "RMB must select the zombie east of the avatar:\n" + game.screen()
        assert mouse_state(game) == before, "mouse selection must be free even when arrows walk"
        # Stun redirects movement even when f requests an adjacent attack.
        assert game.lua("out(gapi.get_avatar():has_effect(EffectTypeId.new('stunned')))") == ["false"], \
            "the avatar must be able to act when f is pressed:\n" + game.screen()
        game.keys("f", delay=1)
        after = bub_pos(game)
        assert after == before[1], (
            f"f must attack the selection without moving ({before[1]} -> {after}); "
            f"state {mouse_state(game)}\n" + game.screen())
        assert action_clock(game) > before[0], "f must spend moves on the selected melee attack"


def test_right_click_selection_f_targets_selected_enemy(_g):
    with no_mouse_movement_game("bn-e2e-rmb-ranged-target") as game:
        assert game.lua("local a=gapi.get_avatar() MAP_MOUSE_GUN=a:create_item(ItypeId.new('model_10_revolver'),-1) "
                        "MAP_MOUSE_GUN:ammo_set(ItypeId.new('38_special'),6) "
                        "out(a:wield(MAP_MOUSE_GUN))") == ["true"]
        settle(game)
        assert game.lua("local near=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(-2,0)) "
                        "local selected=gapi.place_monster_at(MonsterTypeId.new('mon_zombie_rot'),here(3,0)) "
                        "MAP_MOUSE_TARGETS={near,selected} out(near ~= nil and selected ~= nil)") == ["true"]
        before = mouse_state(game)
        x, y = game.find("@")
        game.click(x + 3, y, button=2)
        assert mouse_state(game) == before, "selecting a ranged target must not fire or move"
        assert game.lua("out(MAP_MOUSE_GUN:ammo_remaining())") == ["6"]
        game.keys("f", delay=1)
        panel = firing_target_panel(game)
        assert "decayed zombie" in panel, "f must target the clicked hostile, not the nearer zombie:\n" + panel
        # In Modern's firing context RMB changes selection, never firing a round.
        x, y = game.find("@")
        game.click(x - 2, y, button=2)
        panel = firing_target_panel(game)
        assert "zombie" in panel and "decayed zombie" not in panel, \
            "RMB must select the nearer zombie in the firing window:\n" + panel
        game.keys("Escape", delay=0.6)
        assert game.lua("out(MAP_MOUSE_GUN:ammo_remaining())") == ["6"], "RMB in aiming must not fire"
        assert mouse_state(game) == before, "selecting and canceling aim must be free"


def test_left_click_aims_at_clicked_enemy_and_fires(_g):
    with no_mouse_movement_game("bn-e2e-lmb-ranged-target", AIM_AFTER_FIRING="false") as game:
        assert game.lua("local a=gapi.get_avatar() MAP_MOUSE_GUN=a:create_item(ItypeId.new('model_10_revolver'),-1) "
                        "MAP_MOUSE_GUN:ammo_set(ItypeId.new('38_special'),6) "
                        "out(a:wield(MAP_MOUSE_GUN))") == ["true"]
        settle(game)
        assert game.lua("local near=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(-2,0)) "
                        "local selected=gapi.place_monster_at(MonsterTypeId.new('mon_zombie_rot'),here(3,0)) "
                        "MAP_MOUSE_TARGETS={near,selected} out(near ~= nil and selected ~= nil)") == ["true"]
        before = mouse_state(game)
        x, y = game.find("@")
        game.click(x + 3, y)
        panel = firing_target_panel(game)
        assert "decayed zombie" in panel, "LMB must aim at the clicked hostile, not the nearer zombie:\n" + panel
        x, y = game.find("@")
        game.click(x - 2, y, button=2)
        panel = firing_target_panel(game)
        assert "zombie" in panel and "decayed zombie" not in panel, \
            "RMB must select without firing in the firing window:\n" + panel
        game.click(x - 2, y)
        assert game.lua("out(MAP_MOUSE_GUN:ammo_remaining())") == ["5"], "LMB in aiming must fire exactly one round"
        assert bub_pos(game) == before[1], "mouse firing must not move the player"
        assert action_clock(game) > before[0], "mouse firing must spend moves"

def test_classic_aiming_keeps_mouse_buttons(_g):
    with no_mouse_movement_game("bn-e2e-classic-mouse-aim", CONTROL_SCHEME="classic",
                                AIM_AFTER_FIRING="false") as game:
        assert game.lua("local a=gapi.get_avatar() MAP_MOUSE_GUN=a:create_item(ItypeId.new('model_10_revolver'),-1) "
                        "MAP_MOUSE_GUN:ammo_set(ItypeId.new('38_special'),6) "
                        "out(a:wield(MAP_MOUSE_GUN))") == ["true"]
        settle(game)
        assert game.lua("local near=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(-2,0)) "
                        "local selected=gapi.place_monster_at(MonsterTypeId.new('mon_zombie_rot'),here(3,0)) "
                        "MAP_MOUSE_TARGETS={near,selected} out(near ~= nil and selected ~= nil)") == ["true"]
        before = mouse_state(game)
        game.keys("f", delay=1)
        x, y = game.find("@")
        game.click(x + 3, y)
        panel = firing_target_panel(game)
        assert "decayed zombie" in panel, "Classic LMB must select without firing:\n" + panel
        game.keys("Escape", delay=0.6)
        assert game.lua("out(MAP_MOUSE_GUN:ammo_remaining())") == ["6"]
        assert mouse_state(game) == before, "Classic mouse selection must be free"
        game.keys("f", delay=1)
        x, y = game.find("@")
        game.click(x + 3, y)
        game.click(x + 3, y, button=2)
        assert game.lua("out(MAP_MOUSE_GUN:ammo_remaining())") == ["5"], "Classic RMB must fire"
        assert bub_pos(game) == before[1]
        assert action_clock(game) > before[0]


def test_hover_inspects_without_acting(_g):
    with no_mouse_movement_game("bn-e2e-map-hover") as g:
        before = mouse_state(g)
        x, y = g.find("@")
        g.hover(x + 3, y)
        assert "Mouse View" in g.screen(), "hover must show the actual tile inspector:\n" + g.screen()
        assert mouse_state(g) == before, "hovering must not act or move"


def test_left_click_attacks_adjacent_enemy(_g):
    with no_mouse_movement_game("bn-e2e-map-melee-attack") as g:
        assert g.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(1,0)) "
                     "MAP_MOUSE_TARGETS={m} out(m ~= nil)") == ["true"]
        before = mouse_state(g)
        x, y = g.find("@")
        g.click(x + 1, y)
        assert bub_pos(g) == before[1], "LMB attacks the clicked enemy without moving"
        assert action_clock(g) > before[0], "LMB must spend moves attacking even if the swing misses"


def test_smart_targeting(_g):
    """Aiming starts on the hostile with a clear firing line and names an ally standing in the way."""
    with no_mouse_movement_game("bn-e2e-smart-targeting") as g:
        assert g.lua("local u=gapi.get_avatar() "
                     "local w=u:create_item(ItypeId.new('model_10_revolver'), -1) "
                     "w:ammo_set(ItypeId.new('38_special'), 6) out(u:wield(w))") == ["true"]
        settle(g)
        # The dog blocks the eastern hostile's firing line.
        assert g.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(4,0)) "
                     "local d=gapi.place_monster_at(MonsterTypeId.new('mon_dog'), here(2,0)) d:make_friendly() "
                     "gapi.place_monster_at(MonsterTypeId.new('mon_zombie_rot'), here(-4,0)) out('ok')") == ["ok"]
        g.keys("f", delay=2)
        panel = firing_target_panel(g)
        assert "decayed zombie" in panel, "aiming should start on the hostile with a clear line:\n" + panel
        assert "Ally in the line of fire" not in panel, panel
        g.keys("Tab", delay=2)
        panel = firing_target_panel(g)
        assert "Ally in the line of fire: Labrador mutt" in panel, \
            "cycling to the blocked hostile should name the ally in the way:\n" + panel
TESTS = [test_map_clicks_never_move, test_legacy_map_clicks_never_move,
         test_right_click_locks_enemies_and_opens_object_actions,
         test_mouse_selects_when_arrow_aim_disabled,
         test_right_click_selection_f_targets_selected_enemy,
         test_left_click_aims_at_clicked_enemy_and_fires, test_classic_aiming_keeps_mouse_buttons,
         test_hover_inspects_without_acting, test_left_click_attacks_adjacent_enemy,
         test_smart_targeting]
