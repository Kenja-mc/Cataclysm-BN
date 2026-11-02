"""Modern f attacks what is aimed, then falls back to melee, aiming or smashing."""
import re
import time

from aim_reticle import action_clock
from contextual_hub import contextual_game, contextual_setup, select_tile
from fixtures import shared_game
from helpers import HELPERS, action_menu, bub_pos, settle, wait_until
from map_mouse import firing_target_panel
from pulp_key import finish_smash

LOADED_GUN = ("GUN=gapi.get_avatar():create_item(ItypeId.new('model_10_revolver'),-1) "
              "GUN:ammo_set(ItypeId.new('38_special'),6) "
              "out(gapi.get_avatar():wield(GUN))")
UNLOADED_GUN = ("GUN=gapi.get_avatar():create_item(ItypeId.new('model_10_revolver'),-1) "
                "out(gapi.get_avatar():wield(GUN))")


def latest_message(game):
    result = game.lua("local t=gapi.get_messages(1) out(t[1] and t[1].text or '')")
    return result[0] if result else ""


def clear_inspection(game):
    """Escape clears a reticle or a stale inspector without opening the main menu."""
    if "Mouse View" in game.screen():
        game.keys("Escape", delay=0.4)
        assert "Mouse View" not in game.screen()


def aim_empty(game, steps):
    """Move the reticle over an empty tile: the first arrow snaps to the player."""
    assert game.lua("out(#gapi.get_avatar():get_hostile_creatures(60))") == ["0"], \
        "an empty-tile aim must not see a hostile:\n" + game.screen()
    # With no targets, Tab clears any stale reticle instead of selecting something.
    game.keys("Tab", delay=0.3)
    for _ in range(steps):
        game.keys("Right", delay=0.25)
    assert "Mouse View" in game.screen(), "the reticle must be visible:\n" + game.screen()


def target_hostile(game):
    """Tab selects the only visible hostile, independent of glyph positions."""
    clear_inspection(game)
    game.keys("Tab", delay=0.4)
    assert "Mouse View" in game.screen(), "the hostile must be selected:\n" + game.screen()


def gun_mode(game, name):
    found = re.search(r"\[([^\]]+)\]\s*" + re.escape(name), game.screen())
    return found.group(1) if found else None


def wipe_monsters(game):
    assert game.lua("for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end out('ok')") == ["ok"]


def load_gun(game, loaded=True):
    assert game.lua(LOADED_GUN if loaded else UNLOADED_GUN) == ["true"]
    settle(game)
    # A spawned hostile during the wait would make the no-reticle paths ambiguous.
    wipe_monsters(game)


def ammo(game):
    return game.lua("out(GUN:ammo_remaining())")[0]


def wield(game, item):
    assert game.lua(f"local a=gapi.get_avatar() "
                    f"local it=a:create_item(ItypeId.new('{item}'),-1) out(a:wield(it))") == ["true"]


def spawn_zombie(game, dx, dy, hp=1000):
    assert game.lua(f"local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here({dx},{dy})) "
                    f"m:set_hp({hp}) out(m ~= nil)") == ["true"]


def create_corpse(game, dx, dy, monster="mon_bear"):
    assert game.lua(f"M:create_corpse_at(here({dx},{dy}),MonsterTypeId.new('{monster}')) out('ok')") == ["ok"]


def corpse_state(game, dx, dy):
    """Damage/max of the first corpse on the tile, regardless of stack order."""
    result = game.lua(
        f"local d,m='none','0' for _,it in ipairs(M:get_items_at(here({dx},{dy}))) do "
        "if d=='none' and it:is_corpse() then d=it:get_damage() m=it:get_max_damage() break end end "
        "out(d,m)")
    assert len(result) == 1, f"expected one corpse-state result, got {result!r}"
    state = result[0].split(",")
    assert len(state) == 2, f"expected corpse damage and maximum, got {result!r}"
    return state


def wait_pulped(game, dx, dy):
    deadline = time.time() + 30
    while time.time() < deadline:
        # Let the activity advance before opening the console again.
        time.sleep(1.0)
        state = corpse_state(game, dx, dy)
        if state[0] != "none" and state[0] == state[1]:
            return
    raise AssertionError(f"corpse was not pulped: {corpse_state(game, dx, dy)}")


def clear_tile(game, dx, dy):
    assert game.lua(f"M:clear_items_at(here({dx},{dy})) out('ok')") == ["ok"]


def disarm(game):
    assert game.lua("gapi.get_avatar():drop_all_items() out('ok')") == ["ok"]


def add_web(game, dx, dy):
    assert game.lua(f"M:add_field_at(here({dx},{dy}),FieldTypeId.new('fd_web'):int_id(),1,"
                    "TimeDuration.from_turns(0)) out('ok')") == ["ok"]


def remove_web(game, dx, dy):
    assert game.lua(f"for _,fid in ipairs(M:get_field_ids_at(here({dx},{dy}))) do "
                    f"M:remove_field_at(here({dx},{dy}),fid) end out('ok')") == ["ok"]


def web_present(game, dx, dy):
    return game.lua(f"out(M:has_field_at(here({dx},{dy}),FieldTypeId.new('fd_web'):int_id()))")[0]


def terrain(game, dx, dy):
    return game.lua(f"out(M:get_ter_at(here({dx},{dy})):str_id():str())")[0]


def wall(game, dx, dy):
    assert game.lua(f"M:set_ter_at(here({dx},{dy}),TerId.new('t_wall'):int_id()) out('ok')") == ["ok"]


def face_east(game):
    """Bump a blocking wall so the attack key has a tile ahead without walking."""
    position = bub_pos(game)
    game.keys("d", delay=0.6)
    assert bub_pos(game) == position, "the faced tile must block the step"


def test_aimed_hostile_attacks_before_smashing(_game):
    with contextual_game("bn-e2e-aimed-hostile") as game:
        wipe_monsters(game)
        spawn_zombie(game, 1, 0)
        position, clock = bub_pos(game), action_clock(game)
        target_hostile(game)
        game.keys("f", delay=1)
        assert bub_pos(game) == position, "an aimed attack must not walk"
        assert action_clock(game) > clock, "attacking the aimed hostile must spend moves"


def test_aimed_hostile_with_gun_aims_at_selected_enemy(_game):
    with contextual_game("bn-e2e-aimed-selected-gun") as game:
        wipe_monsters(game)
        load_gun(game)
        spawn_zombie(game, 1, 0)
        spawn_zombie(game, 3, 0)
        before = bub_pos(game), action_clock(game), ammo(game)
        select_tile(game, 3, 0)
        game.keys("f", delay=1)
        panel = firing_target_panel(game)
        assert "zombie" in panel, "a selected hostile with a gun must enter aiming:\n" + panel
        assert re.search(r"Range:\s*3/", panel), "the adjacent hostile must not replace selection:\n" + panel
        game.keys("Escape", delay=0.6)
        assert (bub_pos(game), action_clock(game), ammo(game)) == before


def test_aimed_door_smashes_despite_adjacent_hostile(_game):
    with contextual_game("bn-e2e-aimed-door-hostile") as game:
        wipe_monsters(game)
        wield(game, "hammer_sledge")
        settle(game)
        wipe_monsters(game)
        # Pin bash strength above a wooden door's resistance, rather than rolling for damage.
        assert game.lua("gapi.get_avatar():set_str_bonus(100) "
                        "M:set_ter_at(here(-1,0),TerId.new('t_door_c'):int_id()) out('ok')") == ["ok"]
        spawn_zombie(game, 1, 0)
        position, clock = bub_pos(game), action_clock(game)
        select_tile(game, -1, 0)
        game.keys("f", delay=1)
        assert terrain(game, -1, 0) != "t_door_c", "f must smash the selected door, not the hostile"
        assert bub_pos(game) == position, "smashing must not walk"
        assert action_clock(game) > clock, "the selected door smash must spend moves"



def test_aimed_reach_weapon_swings_without_a_second_aim(_game):
    with contextual_game("bn-e2e-aimed-spear") as game:
        wipe_monsters(game)
        wield(game, "spear_wood")
        settle(game)
        wipe_monsters(game)
        spawn_zombie(game, 2, 0)
        position, clock = bub_pos(game), action_clock(game)
        target_hostile(game)
        game.keys("f", delay=1)
        assert "< Firing " not in game.screen(), "a reach weapon must swing, not re-open targeting"
        assert "Attack where?" not in game.screen(), "the aimed creature needs no second direction"
        assert bub_pos(game) == position
        assert action_clock(game) > clock, "the reach swing must spend moves"


def test_aimed_bayonet_gun_in_melee_mode_swings_adjacent(_game):
    with contextual_game("bn-e2e-aimed-bayonet") as game:
        wipe_monsters(game)
        wield(game, "sks")
        settle(game)
        wipe_monsters(game)
        # The rifle carries an integrated bayonet as its second firing mode.
        action_menu(game, "Combat", "Toggle attack mode of Wielded Item")
        spawn_zombie(game, 1, 0)
        position, clock = bub_pos(game), action_clock(game)
        target_hostile(game)
        game.keys("f", delay=1)
        assert "< Firing " not in game.screen(), "a gun in melee mode must swing, not aim"
        assert bub_pos(game) == position
        assert action_clock(game) > clock, "the bayonet swing must spend moves"


def test_aimed_smashable_object_smashes(_game):
    with contextual_game("bn-e2e-aimed-smash") as game:
        wipe_monsters(game)
        add_web(game, 1, 0)
        add_web(game, -1, 0)
        position, clock = bub_pos(game), action_clock(game)
        aim_empty(game, 2)
        game.keys("f", delay=1)
        assert web_present(game, 1, 0) == "false", "the aimed web must be smashed"
        assert web_present(game, -1, 0) == "true", "only the aimed tile is smashed"
        assert bub_pos(game) == position
        assert action_clock(game) > clock, "smashing spends its normal moves"


def test_reachable_corpse_pulps_unless_hostile(_game):
    with contextual_game("bn-e2e-aimed-pulp") as game:
        wipe_monsters(game)
        clear_tile(game, 1, 0)
        create_corpse(game, 1, 0)
        aim_empty(game, 2)
        game.keys("f", delay=0.5)
        game.wait_for("thoroughly pulped", timeout=30)
        state = corpse_state(game, 1, 0)
        if state[0] == "none" or state[0] != state[1]:
            # A previous test's message can satisfy wait_for before this pulp finishes.
            wait_pulped(game, 1, 0)

        # A hostile standing on the corpse takes the attack instead of being pulped.
        clear_tile(game, 1, 0)
        create_corpse(game, 1, 0)
        spawn_zombie(game, 1, 0)
        target_hostile(game)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert action_clock(game) > clock, "the hostile must be attacked"
        assert corpse_state(game, 1, 0)[0] == "0", "a hostile on the tile must stop the pulping"


def test_reachable_corpse_with_gun_choice_cancel_preserves_state(_game):
    with contextual_game("bn-e2e-aimed-pulp-gun-cancel") as game:
        wipe_monsters(game)
        load_gun(game)
        clear_tile(game, 1, 0)
        create_corpse(game, 1, 0)
        before = (bub_pos(game), action_clock(game), ammo(game), corpse_state(game, 1, 0))
        assert before[3][0] == "0", "the revivable bear corpse must start undamaged"
        aim_empty(game, 2)
        game.keys("f", delay=0.5)
        assert_corpse_choice(game)
        game.keys("Escape", delay=0.5)
        game.wait_gone("Attack the selected tile")
        # Do not reselect or open Lua: the next attack must still target the same corpse.
        game.keys("f", delay=0.5)
        assert_corpse_choice(game)
        game.keys("Escape", delay=0.5)
        assert (bub_pos(game), action_clock(game), ammo(game), corpse_state(game, 1, 0)) == before, \
            "cancelling must preserve position, moves, ammunition and corpse damage"


def assert_corpse_choice(game):
    game.wait_for("Attack the selected tile")
    screen = game.screen()
    assert "Fire" in screen and "Pulp" in screen, "the ambiguity needs both choices:\n" + screen
    assert "< Firing " not in screen, "opening the choice must not start firing"


def test_reachable_corpse_with_gun_fire_choice_opens_aim(_game):
    with contextual_game("bn-e2e-aimed-pulp-gun-fire") as game:
        wipe_monsters(game)
        load_gun(game)
        clear_tile(game, 1, 0)
        create_corpse(game, 1, 0)
        before = (bub_pos(game), action_clock(game), ammo(game), corpse_state(game, 1, 0))
        aim_empty(game, 2)
        game.keys("f", delay=0.5)
        assert_corpse_choice(game)
        game.keys("Home", delay=0.2)
        game.keys("Enter", delay=0.5)
        panel = firing_target_panel(game)
        assert re.search(r"Range:\s*1/", panel), "Fire must aim at the selected corpse:\n" + panel
        game.keys("Escape", delay=0.6)
        assert (bub_pos(game), action_clock(game), ammo(game), corpse_state(game, 1, 0)) == before, \
            "choosing Fire and cancelling aim must not shoot, pulp, move or spend time"


def test_reachable_corpse_with_gun_pulp_choice_pulps(_game):
    with contextual_game("bn-e2e-aimed-pulp-gun-pulp") as game:
        wipe_monsters(game)
        load_gun(game)
        clear_tile(game, 1, 0)
        create_corpse(game, 1, 0)
        assert corpse_state(game, 1, 0)[0] == "0"
        position, clock = bub_pos(game), action_clock(game)
        aim_empty(game, 2)
        game.keys("f", delay=0.5)
        captures = [("before choice", game.screen())]
        try:
            assert_corpse_choice(game)
            captures.append(("choice open", game.screen()))
            game.keys("Down", delay=0.3)
            captures.append(("Pulp selected", game.screen()))
            game.keys("Enter", delay=0.5)
            captures.append(("after Enter", game.screen()))
            assert "< Firing " not in captures[-1][1], "Pulp must not open aiming"
            # Let the real activity finish before Lua opens a debug menu and interrupts it.
            finish_smash(game)
            game.wait_for("thoroughly pulped", timeout=30)
            game.wait_gone("smashing", timeout=30)
            captures.append(("after pulp completion", game.screen()))
            state = corpse_state(game, 1, 0)
            assert state[0] != "none" and state[0] == state[1], \
                f"the selected corpse must be fully pulped, got {state!r}"
            assert game.lua("out(gapi.get_avatar():is_wielding(GUN),GUN:ammo_remaining())") == ["true,6"], \
                "pulping must keep the loaded gun wielded without firing"
            assert bub_pos(game) == position, "pulping must not walk"
            assert action_clock(game) > clock, "pulping must spend its normal moves"
        except Exception as error:
            captures.append(("failure in borrowed game", game.screen()))
            evidence = "\n\n".join(f"{label}:\n{screen}" for label, screen in captures)
            raise AssertionError(f"{error}\n\n{evidence}") from error


def test_reachable_non_reviving_corpse_is_not_pulped(_game):
    with contextual_game("bn-e2e-aimed-deer") as game:
        wipe_monsters(game)
        clear_tile(game, 1, 0)
        create_corpse(game, 1, 0, "mon_deer")
        aim_empty(game, 2)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "There's nothing there to attack." in latest_message(game)
        assert corpse_state(game, 1, 0)[0] == "0", "a deer corpse cannot be pulped"
        assert "< Firing " not in game.screen()
        assert action_clock(game) == clock, "rejecting a dead corpse must not spend time"

        # With a loaded gun the same corpse is a valid aiming target.
        load_gun(game)
        aim_empty(game, 2)
        clock = action_clock(game)
        game.keys("f", delay=1)
        game.wait_for("Attack the selected tile")
        assert "Fire" in game.screen(), "a non-reviving corpse must still offer firing"
        game.keys("Home", delay=0.2)
        game.keys("Enter", delay=0.5)
        assert "< Firing " in game.screen(), "a loaded gun can aim at any corpse"
        game.keys("Escape", delay=0.6)
        assert corpse_state(game, 1, 0)[0] == "0"
        assert action_clock(game) == clock, "opening the aiming screen spends no time"


def test_out_of_reach_corpse_with_gun_opens_aim(_game):
    with contextual_game("bn-e2e-aimed-far-corpse") as game:
        wipe_monsters(game)
        create_corpse(game, 3, 0)
        load_gun(game)
        position = bub_pos(game)
        aim_empty(game, 4)
        clock = action_clock(game)
        game.keys("f", delay=1)
        game.wait_for("Attack the selected tile")
        assert "Fire" in game.screen(), "an unreachable corpse must still offer firing"
        game.keys("Home", delay=0.2)
        game.keys("Enter", delay=0.5)
        assert "< Firing " in game.screen(), "a distant corpse must open the ordinary aiming screen"
        game.keys("Escape", delay=0.6)
        assert ammo(game) == "6", "aiming must not fire"
        assert bub_pos(game) == position
        assert action_clock(game) == clock, "opening the aiming screen spends no time"


def test_out_of_reach_smashable_with_gun_opens_aim(_game):
    with contextual_game("bn-e2e-aimed-far-wall") as game:
        wipe_monsters(game)
        wall(game, 3, 0)
        load_gun(game)
        aim_empty(game, 4)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " in game.screen(), "a distant obstacle is shot at, not smashed"
        game.keys("Escape", delay=0.6)
        assert terrain(game, 3, 0) == "t_wall", "the distant wall must stay intact"
        assert action_clock(game) == clock


def test_aimed_empty_ground_opens_aim_at_selected_tile_without_confirmation(_game):
    with contextual_game("bn-e2e-aimed-empty-gun") as game:
        wipe_monsters(game)
        load_gun(game)
        clear_tile(game, 3, 0)
        before = bub_pos(game), action_clock(game), ammo(game)
        aim_empty(game, 4)
        game.keys("f", delay=1)
        screen = game.screen()
        assert "Fire at the empty ground?" not in screen, "empty floor needs no yes/no prompt"
        assert "Fire at that tile?" not in screen, "empty floor needs no generic confirmation"
        panel = firing_target_panel(game)
        assert re.search(r"Range:\s*3/", panel), "aim must start at the selected floor:\n" + panel
        game.keys("Right", delay=0.5)
        panel = firing_target_panel(game)
        assert re.search(r"Range:\s*4/", panel), "the selected floor must be east, not another tile:\n" + panel
        game.keys("Escape", delay=0.6)
        assert (bub_pos(game), action_clock(game), ammo(game)) == before, \
            "opening and cancelling aim must not move, fire or spend time"


def test_aimed_non_empty_tile_opens_ordinary_aim(_game):
    with contextual_game("bn-e2e-aimed-item") as game:
        wipe_monsters(game)
        load_gun(game)
        assert game.lua("M:create_item_at(here(1,0),ItypeId.new('rock'),-1) out('ok')") == ["ok"]
        before = bub_pos(game), action_clock(game), ammo(game)
        aim_empty(game, 2)
        game.keys("f", delay=1)
        panel = firing_target_panel(game)
        assert re.search(r"Range:\s*1/", panel), "an item pile must open ordinary aiming:\n" + panel
        game.keys("Escape", delay=0.6)
        assert (bub_pos(game), action_clock(game), ammo(game)) == before

        # A friendly creature is not a hostile target, but can still be aimed at.
        clear_tile(game, 1, 0)
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_dog'),here(1,0)) "
                        "m:make_friendly() out(m ~= nil)") == ["true"]
        aim_empty(game, 2)
        game.keys("f", delay=1)
        panel = firing_target_panel(game)
        assert "Friendly" in panel and re.search(r"Range:\s*1/", panel), \
            "ordinary aiming must retain the selected adjacent friendly:\n" + panel
        game.keys("Escape", delay=0.6)
        assert (bub_pos(game), action_clock(game), ammo(game)) == before


def test_aimed_empty_ground_without_a_weapon_logs(_game):
    with contextual_game("bn-e2e-aimed-empty-unarmed") as game:
        wipe_monsters(game)
        aim_empty(game, 2)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " not in game.screen(), "no ranged weapon must not open aiming"
        assert "Fire at the empty ground?" not in game.screen(), "no weapon has nothing to confirm"
        assert "There's nothing there to attack." in latest_message(game)
        assert action_clock(game) == clock, "nothing to attack must not spend time"


def test_loaded_gun_does_not_delay_an_aimed_smash(_game):
    with contextual_game("bn-e2e-aimed-smash-gun") as game:
        wipe_monsters(game)
        load_gun(game)
        add_web(game, 1, 0)
        aim_empty(game, 2)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " not in game.screen(), "the aimed object is smashed, not shot"
        assert web_present(game, 1, 0) == "false", "the aimed web must be smashed"
        assert action_clock(game) > clock, "smashing keeps its moves"


def test_no_reticle_adjacent_hostile_melees_with_a_gun(_game):
    with contextual_game("bn-e2e-aimed-adjacent-gun") as game:
        wipe_monsters(game)
        load_gun(game)
        spawn_zombie(game, 1, 0)
        position, clock = bub_pos(game), action_clock(game)
        clear_inspection(game)
        game.keys("f", delay=1)
        assert "< Firing " not in game.screen(), "an adjacent enemy is a melee attack, not a shot"
        assert bub_pos(game) == position
        assert action_clock(game) > clock, "the melee attack must spend moves"
        assert ammo(game) == "6", "a melee attack must not fire"


def test_no_reticle_loaded_gun_opens_aim(_game):
    with contextual_game("bn-e2e-aimed-gun-aim") as game:
        wipe_monsters(game)
        load_gun(game)
        spawn_zombie(game, 3, 0)
        clear_inspection(game)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " in game.screen(), "nothing adjacent must fall through to gun aiming"
        game.keys("Escape", delay=0.6)
        assert ammo(game) == "6"
        assert action_clock(game) == clock


def test_no_reticle_loaded_gun_beats_a_faced_obstacle(_game):
    with contextual_game("bn-e2e-aimed-gun-first") as game:
        wipe_monsters(game)
        load_gun(game)
        wall(game, 1, 0)
        face_east(game)
        clear_inspection(game)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " in game.screen(), "a loaded gun opens aiming before smashing"
        game.keys("Escape", delay=0.6)
        assert terrain(game, 1, 0) == "t_wall", "the faced wall must stay intact"
        assert action_clock(game) == clock


def test_no_reticle_unloaded_gun_smashes_a_faced_obstacle(_game):
    with contextual_game("bn-e2e-aimed-empty-gun-smash") as game:
        wipe_monsters(game)
        load_gun(game, loaded=False)
        wall(game, 1, 0)
        face_east(game)
        clear_inspection(game)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " not in game.screen(), "an unloaded gun falls through to smashing"
        assert action_clock(game) > clock, "smashing the faced wall must spend moves"


def test_no_reticle_unloaded_gun_without_a_target_reports(_game):
    with contextual_game("bn-e2e-aimed-empty-gun-msg") as game:
        wipe_monsters(game)
        load_gun(game, loaded=False)
        # Walk onto open floor so the faced tile is not worth smashing.
        game.keys("d", delay=0.6)
        wipe_monsters(game)
        clear_inspection(game)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " not in game.screen(), "an unloaded gun must not open aiming"
        assert "is not loaded" in latest_message(game)
        assert action_clock(game) == clock, "reporting an empty gun must not spend time"


def test_no_reticle_unarmed_smashes_ahead(_game):
    with contextual_game("bn-e2e-aimed-smash-ahead") as game:
        wipe_monsters(game)
        wall(game, 1, 0)
        face_east(game)
        clear_inspection(game)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " not in game.screen()
        assert action_clock(game) > clock, "smashing the faced wall must spend moves"


def test_shift_f_no_reticle_attacks_a_nearby_hostile(_game):
    with contextual_game("bn-e2e-aimed-force-near") as game:
        wipe_monsters(game)
        load_gun(game)
        spawn_zombie(game, 1, 0)
        position, clock = bub_pos(game), action_clock(game)
        clear_inspection(game)
        game.keys("F", delay=1)
        assert "< Firing " not in game.screen(), "Shift+F must never open aiming"
        assert bub_pos(game) == position
        assert action_clock(game) > clock, "Shift+F must attack a nearby hostile"
        assert ammo(game) == "6", "Shift+F must not fire"


def test_shift_f_without_a_hostile_reports_without_time(_game):
    with contextual_game("bn-e2e-aimed-force-none") as game:
        wipe_monsters(game)
        load_gun(game)
        clear_inspection(game)
        clock = action_clock(game)
        game.keys("F", delay=1)
        assert "< Firing " not in game.screen(), "Shift+F must never open aiming"
        assert "No hostile creature is within your weapon's reach." in latest_message(game)
        assert action_clock(game) == clock, "an empty forced melee must not spend time"
        assert ammo(game) == "6"


def test_shift_f_rejects_terrain_and_corpses(_game):
    with contextual_game("bn-e2e-aimed-force-terrain") as game:
        wipe_monsters(game)
        load_gun(game)
        add_web(game, 1, 0)
        aim_empty(game, 2)
        clock = action_clock(game)
        game.keys("F", delay=1)
        assert web_present(game, 1, 0) == "true", "Shift+F must not smash terrain"
        assert action_clock(game) == clock

        remove_web(game, 1, 0)
        clear_tile(game, 1, 0)
        create_corpse(game, 1, 0)
        assert corpse_state(game, 1, 0)[0] == "0", "the corpse fixture must be fresh"
        aim_empty(game, 2)
        game.keys("F", delay=1)
        assert corpse_state(game, 1, 0)[0] == "0", "Shift+F must not pulp"
        assert action_clock(game) == clock

        assert game.lua("M:clear_items_at(here(1,0)) out('ok')") == ["ok"]
        wall(game, 1, 0)
        aim_empty(game, 2)
        game.keys("F", delay=1)
        assert terrain(game, 1, 0) == "t_wall", "Shift+F must not smash a wall"
        assert action_clock(game) == clock

        assert game.lua("M:set_ter_at(here(1,0),TerId.new('t_floor'):int_id()) out('ok')") == ["ok"]
        aim_empty(game, 2)
        game.keys("F", delay=1)
        assert action_clock(game) == clock, "Shift+F on empty ground must do nothing"
        assert "< Firing " not in game.screen()
        assert ammo(game) == "6"


def test_shift_f_rejects_an_out_of_reach_hostile(_game):
    with contextual_game("bn-e2e-aimed-force-far") as game:
        wipe_monsters(game)
        load_gun(game)
        spawn_zombie(game, 3, 0)
        target_hostile(game)
        clock = action_clock(game)
        game.keys("F", delay=1)
        assert "out of your weapon's reach" in latest_message(game)
        assert "< Firing " not in game.screen()
        assert action_clock(game) == clock, "a rejected forced melee must not spend time"
        assert ammo(game) == "6"


def test_shift_f_forces_melee_with_a_gun(_game):
    with contextual_game("bn-e2e-aimed-force-melee") as game:
        wipe_monsters(game)
        load_gun(game)
        spawn_zombie(game, 1, 0)
        position = bub_pos(game)
        target_hostile(game)
        clock = action_clock(game)
        game.keys("F", delay=1)
        assert "< Firing " not in game.screen(), "Shift+F must never open the aiming screen"
        assert bub_pos(game) == position, "the forced melee must not walk"
        assert action_clock(game) > clock, "Shift+F must attack"
        assert ammo(game) == "6", "Shift+F must not fire"


def test_fire_mode_lives_in_the_action_menu(_game):
    with contextual_game("bn-e2e-aimed-fire-mode") as game:
        wipe_monsters(game)
        wield(game, "m4a1")
        settle(game)
        wipe_monsters(game)
        before = gun_mode(game, "M4A1")
        assert before, "the wielded rifle must show its firing mode:\n" + game.screen()
        clock = action_clock(game)
        action_menu(game, "Combat", "Toggle attack mode of Wielded Item")
        assert wait_until(lambda: gun_mode(game, "M4A1") != before), game.screen()
        assert action_clock(game) == clock, "changing the fire mode stays free"


def test_classic_keeps_f_fire_and_shift_f_fire_mode(_game):
    options = {"CONTROL_SCHEME": "classic", "SAFEMODE": "false",
               "AUTOSELECT_SINGLE_VALID_TARGET": "false"}
    with shared_game("bn-e2e-aimed-classic", define=HELPERS, setup=contextual_setup,
                     options=options) as game:
        wipe_monsters(game)

        # Classic F still switches the firing mode of a multi-mode gun on the map.
        wield(game, "m4a1")
        settle(game)
        wipe_monsters(game)
        before = gun_mode(game, "M4A1")
        assert before, "the wielded rifle must show its firing mode:\n" + game.screen()
        clock = action_clock(game)
        game.keys("F", delay=0.8)
        assert wait_until(lambda: gun_mode(game, "M4A1") != before), game.screen()
        assert action_clock(game) == clock, "changing the fire mode stays free"

        # A melee weapon on an aimed or empty tile never smashes in Classic.
        disarm(game)
        wield(game, "pipe")
        settle(game)
        wipe_monsters(game)
        add_web(game, 1, 0)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert web_present(game, 1, 0) == "true", "Classic f must not smash"
        assert "Fire at the empty ground?" not in game.screen(), "Classic has no ground prompt"
        assert "You have no ranged weapon wielded." in latest_message(game)
        assert action_clock(game) == clock, "Classic's rejection must not spend time"

        # Classic f keeps its ordinary gun aiming. End here: no Lua call after the aim
        # screen, which keeps the console out of any pending activity state.
        disarm(game)
        load_gun(game)
        game.keys("f", delay=1)
        assert "< Firing " in game.screen(), "Classic f must keep its ordinary gun aiming"
        game.keys("Escape", delay=0.6)
        assert "< Firing " not in game.screen(), "Classic aiming must cancel"


TESTS = [test_aimed_hostile_attacks_before_smashing,
         test_aimed_hostile_with_gun_aims_at_selected_enemy,
         test_aimed_door_smashes_despite_adjacent_hostile,
         test_aimed_reach_weapon_swings_without_a_second_aim,
         test_aimed_bayonet_gun_in_melee_mode_swings_adjacent,
         test_aimed_smashable_object_smashes,
         test_reachable_corpse_pulps_unless_hostile,
         test_reachable_corpse_with_gun_choice_cancel_preserves_state,
         test_reachable_corpse_with_gun_fire_choice_opens_aim,
         test_reachable_corpse_with_gun_pulp_choice_pulps,
         test_reachable_non_reviving_corpse_is_not_pulped,
         test_out_of_reach_corpse_with_gun_opens_aim,
         test_out_of_reach_smashable_with_gun_opens_aim,
         test_aimed_empty_ground_opens_aim_at_selected_tile_without_confirmation,
         test_aimed_non_empty_tile_opens_ordinary_aim,
         test_aimed_empty_ground_without_a_weapon_logs,
         test_loaded_gun_does_not_delay_an_aimed_smash,
         test_no_reticle_adjacent_hostile_melees_with_a_gun,
         test_no_reticle_loaded_gun_opens_aim,
         test_no_reticle_loaded_gun_beats_a_faced_obstacle,
         test_no_reticle_unloaded_gun_smashes_a_faced_obstacle,
         test_no_reticle_unloaded_gun_without_a_target_reports,
         test_no_reticle_unarmed_smashes_ahead,
         test_shift_f_no_reticle_attacks_a_nearby_hostile,
         test_shift_f_without_a_hostile_reports_without_time,
         test_shift_f_rejects_terrain_and_corpses,
         test_shift_f_rejects_an_out_of_reach_hostile,
         test_shift_f_forces_melee_with_a_gun,
         test_fire_mode_lives_in_the_action_menu,
         test_classic_keeps_f_fire_and_shift_f_fire_mode]
