"""Modern f attacks what is aimed, then falls back to melee, aiming or smashing."""
import re
import time

from aim_reticle import action_clock
from contextual_hub import contextual_game, contextual_setup
from fixtures import shared_game
from helpers import HELPERS, action_menu, bub_pos, settle, wait_until

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


def answer_no(game):
    # Modern turns Y/N hotkeys off; the cursor starts on No and Enter confirms it.
    game.keys("Enter", delay=0.5)


def answer_yes(game):
    game.keys("Left", "Enter", delay=0.5)


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
    return game.lua(
        f"local d,m='none','0' for _,it in ipairs(M:get_items_at(here({dx},{dy}))) do "
        "if d=='none' and it:is_corpse() then d=it:get_damage() m=it:get_max_damage() break end end "
        "out(d,m)")


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


def test_reachable_corpse_pulps_with_a_gun(_game):
    with contextual_game("bn-e2e-aimed-pulp-gun") as game:
        wipe_monsters(game)
        load_gun(game)
        clear_tile(game, 1, 0)
        create_corpse(game, 1, 0)
        aim_empty(game, 2)
        game.keys("f", delay=0.5)
        assert "< Firing " not in game.screen(), "a reached corpse is pulped, not shot"
        game.wait_for("thoroughly pulped", timeout=30)
        state = corpse_state(game, 1, 0)
        if state[0] == "none" or state[0] != state[1]:
            wait_pulped(game, 1, 0)


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
        assert "< Firing " in game.screen(), "a loaded gun can aim at any corpse"
        assert corpse_state(game, 1, 0)[0] == "0"
        assert action_clock(game) == clock, "opening the aiming screen spends no time"
        game.keys("Escape", delay=0.6)


def test_out_of_reach_corpse_with_gun_opens_aim(_game):
    with contextual_game("bn-e2e-aimed-far-corpse") as game:
        wipe_monsters(game)
        create_corpse(game, 3, 0)
        load_gun(game)
        position = bub_pos(game)
        aim_empty(game, 4)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " in game.screen(), "a distant corpse must open the ordinary aiming screen"
        assert ammo(game) == "6", "aiming must not fire"
        assert bub_pos(game) == position
        assert action_clock(game) == clock, "opening the aiming screen spends no time"
        game.keys("Escape", delay=0.6)


def test_out_of_reach_smashable_with_gun_opens_aim(_game):
    with contextual_game("bn-e2e-aimed-far-wall") as game:
        wipe_monsters(game)
        wall(game, 3, 0)
        load_gun(game)
        aim_empty(game, 4)
        clock = action_clock(game)
        game.keys("f", delay=1)
        assert "< Firing " in game.screen(), "a distant obstacle is shot at, not smashed"
        assert terrain(game, 3, 0) == "t_wall", "the distant wall must stay intact"
        assert action_clock(game) == clock
        game.keys("Escape", delay=0.6)


def test_aimed_empty_ground_asks_before_firing(_game):
    with contextual_game("bn-e2e-aimed-empty-gun") as game:
        wipe_monsters(game)
        load_gun(game)
        aim_empty(game, 2)
        clock = action_clock(game)
        game.keys("f", delay=1)
        game.wait_for("Fire at the empty ground?")
        assert ammo(game) == "6", "asking must not fire"
        assert action_clock(game) == clock, "asking must not spend time"
        answer_no(game)
        game.wait_gone("Fire at the empty ground?")
        assert "< Firing " not in game.screen(), "declining must not open the aiming screen"
        assert action_clock(game) == clock, "declining must not spend time"

        game.keys("f", delay=1)
        game.wait_for("Fire at the empty ground?")
        answer_yes(game)
        assert "< Firing " in game.screen(), "confirming must open the ordinary aiming screen"
        assert ammo(game) == "6", "the aiming screen itself fires nothing"
        game.keys("Escape", delay=0.6)


def test_aimed_non_empty_tile_uses_generic_fire_prompt(_game):
    with contextual_game("bn-e2e-aimed-item") as game:
        wipe_monsters(game)
        load_gun(game)
        assert game.lua("M:create_item_at(here(1,0),ItypeId.new('rock'),-1) out('ok')") == ["ok"]
        aim_empty(game, 2)
        clock = action_clock(game)
        game.keys("f", delay=1)
        game.wait_for("Fire at that tile?")
        assert "Fire at the empty ground?" not in game.screen(), \
            "an item pile is not empty ground:\n" + game.screen()
        assert action_clock(game) == clock
        answer_no(game)
        game.wait_gone("Fire at that tile?")

        # A friendly creature is not a hostile target and not "empty ground" either.
        assert game.lua("M:clear_items_at(here(1,0)) out('ok')") == ["ok"]
        assert game.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_dog'),here(1,0)) "
                        "m:make_friendly() out(m ~= nil)") == ["true"]
        aim_empty(game, 2)
        game.keys("f", delay=1)
        game.wait_for("Fire at that tile?")
        assert "Fire at the empty ground?" not in game.screen()
        answer_no(game)
        game.wait_gone("Fire at that tile?")


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
        assert ammo(game) == "6"
        assert action_clock(game) == clock
        game.keys("Escape", delay=0.6)


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
        assert terrain(game, 1, 0) == "t_wall", "the faced wall must stay intact"
        assert action_clock(game) == clock
        game.keys("Escape", delay=0.6)


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
         test_aimed_reach_weapon_swings_without_a_second_aim,
         test_aimed_bayonet_gun_in_melee_mode_swings_adjacent,
         test_aimed_smashable_object_smashes,
         test_reachable_corpse_pulps_unless_hostile,
         test_reachable_corpse_pulps_with_a_gun,
         test_reachable_non_reviving_corpse_is_not_pulped,
         test_out_of_reach_corpse_with_gun_opens_aim,
         test_out_of_reach_smashable_with_gun_opens_aim,
         test_aimed_empty_ground_asks_before_firing,
         test_aimed_non_empty_tile_uses_generic_fire_prompt,
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
