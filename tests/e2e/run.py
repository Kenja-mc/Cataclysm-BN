#!/usr/bin/env python3
"""End-to-end checks for the overhaul, played through the real curses binary in tmux."""
import json
import re
import sys
import time
import traceback
from pathlib import Path

from tmux_game import ROOT, Game, start_new_game

from helpers import *
from vehicle_box import TESTS as VEHICLE_BOX_TESTS
from cursor_panning import TESTS as CURSOR_PANNING_TESTS
from npc_palette import TESTS as NPC_PALETTE_TESTS
from hud_sidebar import TESTS as HUD_SIDEBAR_TESTS
from construction_tab import TESTS as CONSTRUCTION_TAB_TESTS
from dispose_menu import TESTS as DISPOSE_MENU_TESTS
from fire_feedback import TESTS as FIRE_FEEDBACK_TESTS
from keyhints_small import TESTS as KEYHINTS_SMALL_TESTS
from safe_mode_sleep import TESTS as SAFE_MODE_SLEEP_TESTS
from vehicle_memory import TESTS as VEHICLE_MEMORY_TESTS
from aim_reticle import TESTS as AIM_RETICLE_TESTS, action_clock
from safe_click import TESTS as SAFE_CLICK_TESTS
from inventory_mouse import TESTS as INVENTORY_MOUSE_TESTS
from pickup_flow import TESTS as PICKUP_FLOW_TESTS
from options_menu import TESTS as OPTIONS_MENU_TESTS
from map_mouse import TESTS as MAP_MOUSE_TESTS, firing_target_panel, mouse_state, no_mouse_movement_game
from inventory_hub import TESTS as INVENTORY_HUB_TESTS
from contextual_hub import TESTS as CONTEXTUAL_HUB_TESTS
from grouped_controls import TESTS as GROUPED_CONTROLS_TESTS
from hud_status import TESTS as HUD_STATUS_TESTS





def test_welcome_card(g):
    assert getattr(g, "saw_welcome", False), "first new game should show the welcome card"
    card = g.welcome_screen
    assert "Unsupported" not in card and "%" not in card, "the card text must be formatted:\n" + card


def test_death_mode_choice(g):
    """Caves of Qud style: the first game asks Permadeath or Roleplay; the harness picks Roleplay."""
    import json
    assert getattr(g, "saw_death_choice", False), "welcome should ask how death works"
    opts = {o["name"]: o["value"] for o in json.loads((g.userdir / "config" / "options.json").read_text())}
    assert opts.get("PROMPT_ON_CHARACTER_DEATH") == "true", opts.get("PROMPT_ON_CHARACTER_DEATH")


def test_first_time_tip(g):
    arena(g)
    g.lua("gapi.get_avatar():set_value('tip_seen_hostile','') out('ok')")
    assert g.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(4,0)) out('ok')") == ["ok"]
    settle(g)
    assert "Tip: Something hostile" in g.screen(), g.screen()
    assert g.lua("out(gapi.get_avatar():get_value('tip_seen_hostile'))") == ["1"]
    g.lua("local m=gapi.get_monster_at(here(4,0)) if m then park(m) end out('ok')")



def test_auto_explore(g):
    """n walks toward unseen ground; runs before any test spawns hostiles, which would block it."""
    # The start shelter can be fully seen with its doors shut; a cross of floor opens it to the outdoors.
    assert g.lua("for d=-30,30 do for _,p in ipairs({here(d,0), here(0,d)}) do "
                 "M:set_ter_at(p, TerId.new('t_floor'):int_id()) M:set_furn_at(p, FurnId.new('f_null'):int_id()) "
                 "end end out('ok')") == ["ok"]
    settle(g)
    start = bub_pos(g)
    g.keys("n", delay=0.6)
    assert wait_until(lambda: bub_pos(g) != start, timeout=15), "n should start walking:\n" + g.screen()
    assert "Auto-move canceled" not in g.screen(), g.screen()


def test_wasd_movement(g):
    arena(g)
    steps = {"d": (1, 0), "a": (-1, 0), "s": (0, 1), "w": (0, -1),
             "e": (1, -1), "z": (-1, 1), "c": (1, 1), "q": (-1, -1)}
    for key, (dx, dy) in steps.items():
        before = bub_pos(g)
        g.keys(key, delay=0.8)
        after = bub_pos(g)
        assert after == (before[0] + dx, before[1] + dy, before[2]), f"{key}: {before} -> {after}"


def test_wait_keeps_position(g):
    before = bub_pos(g)
    g.keys("x", delay=0.8)
    assert bub_pos(g) == before


def test_blocked_step_says_why(g):
    """Walking into a wall tells you what is in the way instead of silently doing nothing."""
    arena(g)
    assert g.lua("M:set_ter_at(here(1,0), TerId.new('t_wall'):int_id()) out('ok')") == ["ok"]
    before = bub_pos(g)
    g.keys("d", delay=0.8)
    assert bub_pos(g) == before
    assert "is in the way" in g.screen(), g.screen()


def test_quick_stack(g):
    arena(g)
    spawn(g, 2, 0, "usb_drive", furn="f_rack")
    give(g, "usb_drive", 3)
    give(g, "plastic_six_dice", 1)
    assert count_carried(g, "usb_drive") == 3
    action_menu(g, "Interact", "Quick stack to nearby storage")
    settle(g)
    assert count_at(g, 2, 0, "usb_drive") == 4, "drives should join the rack"
    assert count_carried(g, "usb_drive") == 0
    assert count_carried(g, "plastic_six_dice") == 1, "nothing nearby holds dice, so they stay"
    # The random starting profession may carry something of the drives' category, which also goes.
    assert re.search(r"Stashed \d+ items into 1 spot", g.screen()), g.screen()


def test_quick_stack_not_through_windows(g):
    arena(g)
    assert g.lua("M:set_ter_at(here(1,0), TerId.new('t_window'):int_id()) out('ok')") == ["ok"]
    spawn(g, 2, 0, "usb_drive", furn="f_rack")
    give(g, "usb_drive", 2)
    action_menu(g, "Interact", "Quick stack to nearby storage")
    settle(g)
    assert count_carried(g, "usb_drive") == 2, "a shelf behind a window is out of reach"
    assert count_at(g, 2, 0, "usb_drive") == 1
    g.lua("M:set_ter_at(here(1,0), TerId.new('t_floor'):int_id()) out('ok')")


def test_black_powder_loot_keeps_its_modifier(g):
    """Loot retains either native black-powder ballistics or the full stack modifier."""
    arena(g)
    g.lua("M:clear_items_at(here(2,0)) for i=1,5 do M:place_items('ammo_rifle_blackpowder_handloads', 100, here(2,0), here(2,0), false) end out('ok')")
    rows = g.lua("for _,it in pairs(M:get_items_at(here(2,0))) do "
                 "local bp=0 for _,e in pairs(it:get_type():obj():slot_ammo().ammo_effects) do if e:str()=='BLACKPOWDER' then bp=1 end end "
                 "out(it:get_type():str(), it.charges, it:get_var_num('stack_mod:black_powder', 0), bp) end")
    assert rows, "the group should spawn something"
    for row in rows:
        item_id, charges, modifier, blackpowder = row.split(",")
        if int(blackpowder):
            # A modifier would apply the native round's black-powder penalty twice.
            assert int(float(modifier)) == 0, f"{item_id} is black powder already: {row}"
        else:
            assert int(float(modifier)) == int(charges), f"every spawned round is black powder: {rows}"


def test_sort_pile(g):
    arena(g)
    spawn(g, 3, 0, "usb_drive", furn="f_rack")
    spawn(g, -3, 0, "flyer", furn="f_rack")
    spawn(g, 0, 0, "usb_drive", 2)
    spawn(g, 0, 0, "character_sheet", 1)
    spawn(g, 0, 0, "plastic_six_dice", 1)
    action_menu(g, "Interact", "Sort the pile you're standing on")
    settle(g)
    assert count_at(g, 3, 0, "usb_drive") == 3, "same item goes to the same shelf"
    assert count_at(g, -3, 0, "character_sheet") == 1, "books follow books"
    assert count_at(g, 0, 0, "plastic_six_dice") == 1, "unmatched items stay in the pile"


def wait_until(check, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return True
        time.sleep(1)
    return False


def craft_by_name(g, name):
    open_crafting(g)
    g.keys("f", delay=0.8)
    g.type(name)
    g.keys("Enter", delay=1.5)
    for _ in range(3):
        if "Searched" not in g.screen():
            break
        g.keys("Enter", delay=1.5)


def test_crafting_opens_on_content(g):
    open_crafting(g)
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert "< FAVORITE >" not in s, "crafting should not open on the empty favorites list"


def test_recraft_after_reload(g):
    """Upstream #10083: recraft crashed after save, quit to menu and reload in one session."""
    # Materials on the floor nearby also exercise the larger crafting reach.
    arena(g)
    spawn(g, 3, 0, "glass_shard", 3)
    settle(g)
    craft_by_name(g, "glass shard trap")
    # A heavily loaded character puts the result on the ground; either way it was crafted.
    made = lambda: count_carried(g, "glass_shard_trap") + count_at(g, 0, 0, "glass_shard_trap")
    assert wait_until(lambda: made() == 1), g.screen()
    g.keys("Escape", delay=1)
    g.keys("S", delay=1)
    g.keys("y", "Enter", delay=1)
    load_first_save(g)
    g.define_lua(HELPERS)
    action_menu(g, "Craft", "Recraft last recipe")
    assert wait_until(lambda: made() == 2), g.screen()


DURATION = (r"\d+ (?:seconds?|minutes?|hours?|days?|weeks?)"
            r"(?: and \d+ (?:seconds?|minutes?|hours?|days?|weeks?))?")


def flat_text(g):
    return " ".join(g.screen().split())


def test_craft_parts_chain(_g):
    """Known blockers, charged part quantities and producer timing stay consistent."""
    g = Game(name="bn-e2e-craft-parts",
             options={"SAFEMODE": "false", "CRAFTING_PART_CHAINS": "true"})
    try:
        start_new_game(g)
        g.define_lua(HELPERS)
        assert g.lua(
            "local a=gapi.get_avatar() a:clear_bionics() a:clear_mutations() "
            "a:clear_morale() a:drop_all_items() "
            "a:set_mutation(MutationBranchId.new('DEBUG_STORAGE')) "
            "for _,id in ipairs({'tinfoil_hat','handrolled_cig','rolling_paper'}) do "
            "a:learn_recipe(RecipeId.new(id)) end out('prepared')"
        ) == ["prepared"]
        arena(g)
        settle(g)

        def browse_recipe(name):
            open_crafting(g)
            g.wait_for("[f]ilter", timeout=10)
            g.keys("f", delay=0.8)
            g.wait_for("Search:", timeout=10)
            g.type(name)
            g.keys("Enter", delay=1.5)

        def close_recipes():
            g.keys("Escape", delay=0.8)

        browse_recipe("tinfoil hat")
        screen = flat_text(g)
        assert "aluminum foil" in screen, screen
        assert "parts:" not in screen, screen
        assert "Part:" not in screen and "Part (blocked):" not in screen, screen
        close_recipes()

        give(g, "tobacco", 20)
        settle(g)
        browse_recipe("hand-rolled cigarette")
        screen = flat_text(g)
        assert "parts:known" in screen, screen
        assert "Part (blocked):" in screen, screen
        blocked = screen.split("Part (blocked):", 1)[1]
        paper = re.search(r"Missing:\s*(?:(\d+)\s+paper|paper\s*\((\d+)\))", blocked)
        assert paper and int(paper.group(1) or paper.group(2)) == 1, screen
        close_recipes()

        give(g, "paper", 12)
        settle(g)
        browse_recipe("hand-rolled cigarette")
        assert "parts:make" in flat_text(g), g.screen()
        g.keys("b", delay=1)
        g.keys("Home", delay=0.2)
        for _ in range(11):
            g.keys("Down", delay=0.4)
        part = re.search(r"Part: rolling paper \(make (\d+) more, ~(" + DURATION + r")\)",
                         flat_text(g))
        assert part, g.screen()
        assert part.group(1) == "12", g.screen()

        g.keys("p", delay=1.5)
        assert "rolling paper" in flat_text(g).lower(), g.screen()
        g.keys("b", delay=1)
        g.keys("Home", delay=0.2)
        g.keys("Down", delay=0.8)
        made = re.search(r"Time to complete:\s*(" + DURATION + r")", flat_text(g))
        assert made, g.screen()
        assert made.group(1) == part.group(2), g.screen()
        close_recipes()
    finally:
        g.close()


def load_first_save(g, timeout=120):
    """After save-and-quit the main menu reopens on Load; Enter picks the world, then the character."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = g.screen()
        if "X,Y,Z" in s and " move " in s:
            return
        if "»" in s:
            g.keys("Enter", delay=2)
        else:
            time.sleep(0.5)
    raise AssertionError("could not load the save\n" + g.screen())


def test_aim_defaults(g):
    action_menu(g, "Inventory", "Advanced Inventory management")
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert "Surrounding area" in s or "Surrounding" in s or "AL" in s, "left pane should show the surroundings"
    assert "Inventory" in s


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


def test_unified_batteries(g):
    """Battery variants merged into light/medium/heavy cells plus atomic ones."""
    out = g.lua("out(ItypeId.new('light_minus_battery_cell'):is_valid(), ItypeId.new('heavy_disposable_cell'):is_valid(), "
                "ItypeId.new('light_battery_cell'):is_valid(), ItypeId.new('light_atomic_battery_cell'):is_valid())")
    assert out == ["false,false,true,true"], out


def zombie_hp(g):
    out = g.lua("local m=gapi.get_monster_at(here(1,0)) if m then out(m:get_hp()) else out(-1) end")
    return int(out[0])


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


def test_action_menu_opens_character_info(g):
    def character_sheet_visible(screen):
        return all(label in screen for label in ("Strength:", "Dexterity:", "Intelligence:", "Perception:"))

    arena(g)
    settle(g)
    try:
        before = bub_pos(g)
        clock = action_clock(g)
        action_menu(g, "Info", "View Player Info")
        assert character_sheet_visible(g.screen()), "the action menu must open the actual character sheet:\n" + g.screen()
        g.keys("Escape", delay=0.6)
        assert not character_sheet_visible(g.screen()), "Escape must return from the character sheet"
        assert bub_pos(g) == before
        assert action_clock(g) == clock, "browsing character information must not spend moves"
    finally:
        arena(g)


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


def test_right_click_selects_adjacent_enemy_for_f(_g):
    with no_mouse_movement_game("bn-e2e-map-melee-select") as g:
        assert g.lua("local m=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(1,0)) "
                     "MAP_MOUSE_TARGETS={m} out(m ~= nil)") == ["true"]
        before = mouse_state(g)
        x, y = g.find("@")
        g.click(x + 1, y, button=2)
        assert "Mouse View" in g.screen(), "RMB must inspect the selected enemy:\n" + g.screen()
        assert not re.search(r"\battack (?:the )?zombie\b", g.screen()), \
            "RMB must not open an action menu:\n" + g.screen()
        assert mouse_state(g) == before, "RMB must not spend moves, move, or damage either creature"
        g.keys("f", delay=1)
        assert bub_pos(g) == before[1], "f attacks the selected enemy without moving"
        assert action_clock(g) > before[0], "f must spend moves attacking even if the swing misses"





def test_black_powder_rounds_stack(g):
    """Black powder handloads are a stack modifier, so they merge into the factory 9mm stack."""
    arena(g)
    out = g.lua("local p=here(1,0) M:create_item_at(p, ItypeId.new('9mm'), 20) "
                "local it=gapi.create_item(ItypeId.new('9mm'), 10) it:set_var_str('stack_mod:black_powder','10') M:add_item(p, it) "
                "local s=M:get_items_at(p):items() out(#s, s[1].charges, s[1]:get_var_str('stack_mod:black_powder',''))")
    assert out == ["1,30,10"], out
    name = g.lua("out(M:get_items_at(here(1,0)):items()[1]:display_name(1))")
    assert name and "10 black powder" in name[0], name
    assert g.lua("out(ItypeId.new('bp_9mm'):is_valid())") == ["false"]


REVOLVER = ("local w=nil for _,it in ipairs(gapi.get_avatar():all_items(false)) do "
            "if it:get_type():str()=='model_10_revolver' then w=it end end ")


def test_black_powder_survives_reloading(g):
    arena(g)
    assert g.lua("local u=gapi.get_avatar() u:drop_all_items() M:clear_items_at(here(0,0)) "
                 "local w=u:create_item(ItypeId.new('model_10_revolver'), -1) "
                 "local a=u:create_item(ItypeId.new('38_special'), 6) a:set_var_str('stack_mod:black_powder','3') "
                 "out(u:wield(w))") == ["true"]
    for _ in range(6):
        g.keys("r", delay=1)
        g.keys("r", delay=2)
    out = g.lua(REVOLVER + "out(w.charges, w:get_var_str('stack_mod:black_powder','0'), w:display_name(1))")
    charges, black_powder, name = out[0].split(",", 2)
    assert int(charges) == 6, out
    assert int(black_powder) == 3, "the three black powder rounds move into the cylinder"
    assert "3 black powder" in name, name


def test_jewelry_is_one_item_per_form(g):
    """Rings, bracelets and the like are one item each; metal and gem are a variant the item remembers."""
    arena(g)
    assert g.lua("out(ItypeId.new('ruby_gold_ring'):is_valid(), ItypeId.new('copper_ring'):is_valid())") == ["false,false"]
    out = g.lua("local r=gapi.create_item(ItypeId.new('jewelry_ring'), -1) r:set_var_str('variant','ruby_gold_ring') "
                "gapi.get_avatar():add_item(r) out(r:display_name(1))")
    assert "ruby and gold ring" in out[0], out
    prices = g.lua("local d=gapi.create_item(ItypeId.new('jewelry_bracelet'), -1) d:set_var_str('variant','diamond_gold_bracelet') "
                   "local q=gapi.create_item(ItypeId.new('jewelry_bracelet'), -1) q:set_var_str('variant','copper_bracelet') "
                   "out(d:price(false), q:price(false))")
    diamond, copper = (float(v) for v in prices[0].split(","))
    assert diamond > copper * 5, prices
    assert g.lua("give('hammer',1)") == ["ok"]

    def open_disassembly():
        action_menu(g, "Craft", "Disassemble items")
        if "Disassemble item" in g.screen():
            return True
        g.keys("Escape", delay=0.5)
        return False
    assert wait_until(open_disassembly), g.screen()
    g.keys("/", delay=0.5)
    g.type("ruby")
    g.keys("Enter", delay=1)
    assert "gold (2) and 1 ruby" in g.screen(), "the yield lists the ring's gold and ruby\n" + g.screen()
    # A second Enter straight after the first is swallowed, so move the cursor in between.
    g.keys("Down", "Up", "Enter", delay=0.5)
    assert wait_until(lambda: g.lua("count_at(0,0,'ruby')") == ["1"], 60), g.screen()
    assert g.lua("count_at(0,0,'gold_small')") == ["2"]


def test_mixed_jewelry_stacks(g):
    """Different rings stack like Don't Starve items; each still keeps its own gem, metal and price."""
    out = g.lua("local u=gapi.get_avatar() local p=0 for _,v in ipairs({'ruby_gold_ring','copper_ring'}) do "
                "local r=gapi.create_item(ItypeId.new('jewelry_ring'), -1) r:set_var_str('variant',v) p=p+r:price(false) u:add_item(r) end "
                "out(p)")
    assert float(out[0]) > 0, out
    g.keys("i", delay=1)
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert any("2 " in l and "rings" in l for l in s.splitlines()), "both rings share one inventory line\n" + s


def test_folded_families(g):
    """Novels, board games and judo belts are one item each, with the old items as variants."""
    out = g.lua("local b=gapi.create_item(ItypeId.new('paperback'), -1) b:set_var_str('variant','novel_western') "
                "local j=gapi.create_item(ItypeId.new('judo_belt'), -1) j:set_var_str('variant','judo_belt_black') "
                "out(b:display_name(1), j:display_name(1), ItypeId.new('novel_western'):is_valid())")
    book, belt, old_id_valid = out[0].split(",")
    assert "western novel" in book and "black belt" in belt and old_id_valid == "false", out


def test_mre_unpacks_its_entree(g):
    """MRE boxes are one item; the entree is a variant and unpacking yields it."""
    arena(g)
    out = g.lua("local m=gapi.create_item(ItypeId.new('mre_ration'), -1) m:set_var_str('variant','mre_lemontuna') "
                "gapi.get_avatar():add_item(m) out(m:display_name(1))")
    assert "Lemon Pepper Tuna" in out[0], out
    action_menu(g, "Craft", "Disassemble items")
    g.keys("/", delay=0.5)
    g.type("Lemon")
    g.keys("Enter", "Down", "Up", delay=0.5)
    assert "Lemon Pepper Tuna" in g.screen(), g.screen()
    g.keys("Enter", delay=1)
    assert "lemon pepper tuna entree" in g.screen().lower(), "the entree is listed in the yield"
    # Prompts start on No; y only selects Yes, and Enter confirms it.
    g.keys("y", delay=1)
    assert "Really disassemble?" in g.screen(), "y alone must not answer the prompt"
    g.keys("Enter", delay=1)
    # The entree lands on the floor.
    assert wait_until(lambda: g.lua("count_at(0,0,'mre_lemontuna')") == ["1"], 60), g.screen()
    assert count_carried(g, "mre_ration") == 0


def test_wasd_menu_navigation(g):
    """Letter shortcuts must not steal WASD from a real list menu."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(g.lua,
                                 "local menu=UiList.new() menu:title('WASD navigation') "
                                 "menu:add(10,'First choice') menu:add(20,'Second choice') "
                                 "menu:add(30,'Third choice') out(menu:query())")
        g.wait_for("< WASD navigation >")
        g.keys("s", "s", "w", "a", "d", "Enter", delay=0.4)
        assert result.result() == ["20"], g.screen()

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(g.lua,
                                 "local menu=UiList.new() menu:title('Filter typing') "
                                 "menu:add(10,'Other item') menu:add(20,'wasd first') "
                                 "menu:add(30,'wasd second') out(menu:query())")
        g.wait_for("< Filter typing >")
        g.keys("/", delay=0.4)
        g.type("wasd")
        g.keys("Down", "Up", "Down", "Enter", "Enter", delay=0.4)
        assert result.result() == ["30"], g.screen()

    arena(g)
    spawn(g, 0, 0, "rock")
    spawn(g, 0, 0, "stick")
    before = {item: count_carried(g, item) for item in ("rock", "stick")}
    g.keys("g", delay=0.8)
    g.wait_for("rock")
    def selected(item):
        return re.search(r"< [^<>]*" + item + r"[^<>]* >", g.screen()) is not None
    first = "rock" if selected("rock") else "stick"
    assert selected(first), g.screen()
    second = "stick" if first == "rock" else "rock"
    g.keys("s", delay=0.4)
    assert selected(second), "S must navigate to the other item\n" + g.screen()
    g.keys("d", "w", delay=0.4)
    assert selected(first), "W must navigate back without wielding\n" + g.screen()
    g.keys("d", "a", "Enter", delay=0.4)
    assert count_carried(g, second) == before[second] + 1, "D marks the selected item"
    assert count_carried(g, first) == before[first], "A unmarks the selected item"


def item_picker_rows(screen, names):
    """Read each fixture item's displayed shortcut from its picker row."""
    rows = []
    for line in screen.splitlines():
        if "│" not in line:
            continue
        inner = line[:line.rfind("│")]
        for name in names:
            at = inner.find(name)
            if at >= 2 and inner[at - 1] == " " and inner[at - 2].isalnum():
                rows.append((inner[at - 2], name))
    return rows


def test_modern_wield_nearby_rows_keep_their_shortcut(g):
    """A nearby item's displayed shortcut must wield that item, not move the cursor."""
    # Three nearby rows force a collision with the cursor digit 2 before remapping.
    arena(g)
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)
    for item, (dx, dy) in {"rock": (1, 0), "stick": (0, 1), "pipe": (-1, 0)}.items():
        spawn(g, dx, dy, item)
    names = {}
    for item in ("rock", "stick", "pipe"):
        out = g.lua(f"local it=gapi.create_item(ItypeId.new('{item}'),-1) out(it:display_name(1))")
        assert len(out) == 1, out
        names[out[0]] = item
    action_menu(g, "Inventory", "Wield")
    assert "Wield item" in g.screen(), g.screen()
    rows = item_picker_rows(g.screen(), names)
    assert len(rows) == len(names), f"one row per fixture item: {rows}\n{g.screen()}"
    assert sorted(name for _, name in rows) == sorted(names), rows
    cursor_keys = ("2", "4", "6", "8")
    labelled = ([row for row in rows if row[0] in cursor_keys]
                or [row for row in rows if not row[0].isdigit()]
                or rows[-1:])
    shortcut, name = labelled[0]
    g.keys(shortcut, delay=1.5)
    assert "Wield item" not in g.screen(), f"{shortcut!r} should pick the {name} row\n" + g.screen()
    wielded = g.lua("local a=gapi.get_avatar() local w={} for _,it in ipairs(a:all_items(false)) do "
                    "if a:is_wielding(it) then w[#w+1]=it:get_type():str() end end out(table.concat(w,','))")
    assert wielded == [names[name]], f"{shortcut!r} should wield {names[name]}, got {wielded}\n" + g.screen()
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)


def test_classic_control_scheme(g):
    """Options → Control scheme → Classic brings back vi-keys and bump attacks."""
    classic = Game(name="bn-e2e-classic", options={"SAFEMODE": "false", "CONTROL_SCHEME": "classic"})
    try:
        start_new_game(classic)
        classic.keys(".", delay=0.6)
        classic.define_lua(HELPERS)
        arena(classic)
        for key, (dx, dy) in {"l": (1, 0), "k": (0, -1), "h": (-1, 0), "j": (0, 1)}.items():
            before = bub_pos(classic)
            classic.keys(key, delay=0.8)
            assert bub_pos(classic) == (before[0] + dx, before[1] + dy, before[2]), key
        assert "wasd move" not in classic.screen()
        # Bump attacks come with the scheme even though options.json only names the scheme.
        assert classic.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) out('ok')") == ["ok"]
        before = zombie_hp(classic)
        for _ in range(6):
            classic.keys("l", delay=1)
            if zombie_hp(classic) != before:
                break
        assert zombie_hp(classic) != before, "walking into a zombie attacks it in classic"
    finally:
        classic.close()


def test_old_full_keybindings_file(g):
    """Older versions saved every binding; such a file must not undo the modern scheme."""
    import json, tempfile
    # What upstream's save() wrote: every action of every context, with id, category and bindings.
    dump = [{"id": e["id"], "category": e.get("category", "default"), "bindings": e["bindings"]}
            for e in json.load(open("data/raw/keybindings/keybindings.json")) if "bindings" in e]
    path = Path(tempfile.mkdtemp()) / "keybindings.json"
    path.write_text(json.dumps(dump))
    old = Game(name="bn-e2e-oldkeys", options={"SAFEMODE": "false"}, keybindings=str(path))
    try:
        start_new_game(old)
        old.define_lua(HELPERS)
        arena(old)
        old.keys("x", delay=0.6)
        for key, (dx, dy) in {"d": (1, 0), "w": (0, -1), "e": (1, -1)}.items():
            before = bub_pos(old)
            old.keys(key, delay=0.8)
            assert bub_pos(old) == (before[0] + dx, before[1] + dy, before[2]), key
        assert "wasd move" in old.screen()
    finally:
        old.close()


def test_vehicle_screen_diagonals(g):
    """WASD/QEZC move the vehicle screen cursor too; the actions they shadowed moved to capitals."""
    arena(g)
    from vehicle_box import spawn_vehicle
    spawn_vehicle(g, "bicycle")
    action_menu(g, "Interact", "Examine Nearby Terrain")
    if "which tile?" in g.screen() or "Examine where?" in g.screen():
        g.keys("x", delay=1.5)
    if "Interact with the" in g.screen():
        choose_menu_entry(g, "examine the")
    g.keys("e", delay=2)  # "Examine vehicle"
    try:
        start = g.screen()
        g.keys("s", delay=1.5)
        moved = g.screen()
        assert "ESC-back" in moved and moved != start, "s should move the cursor, not siphon"
        g.keys("e", delay=1.5)
        diag = g.screen()
        assert "ESC-back" in diag and "new name" not in diag.lower() and diag != moved, "e should move diagonally, not rename"
    finally:
        g.keys("Escape", delay=1)


def test_hud_boxes(g):
    """Weather and weapon boxes in the map's top-left corner."""
    settle(g)
    lines = g.screen().splitlines()
    top = "\n".join(l[:40] for l in lines[:12])
    assert lines[0].startswith("╭"), top
    assert any(icon in top for icon in ("☼", "☾", "☁", "☂", "↯", "❄", "◎", "▼")), "weather icon: " + top
    assert any(icon in top for icon in ("✶", "⚔", "⌖", "➶")), "weapon icon: " + top



def test_stance_toggle(g):
    arena(g)
    g.lua("gapi.get_avatar():set_movement_mode(CharacterMoveMode.walk) out('ok')")
    settle(g)
    before = bub_pos(g)
    clock = action_clock(g)
    for mode, label in (("run", "Running"), ("crouch", "Crouching"),
                        ("prone", "Prone"), ("walk", "Walking")):
        g.keys("X", delay=0.8)
        assert label in g.screen(), f"HUD must refresh to {mode}:\n{g.screen()}"
        assert g.lua(f"out(gapi.get_avatar():get_movement_mode() == CharacterMoveMode.{mode})") == ["true"]
        assert bub_pos(g) == before, "changing stance must not move the player"
        assert action_clock(g) == clock, "changing stance must not spend moves"


def test_hud_box_options(g):
    """Each box moves to any corner or turns off; ASCII icons work everywhere."""
    other = Game(name="bn-e2e-hud", options={"SAFEMODE": "false", "HUD_WEATHER_BOX": "off",
                                             "HUD_COMBAT_BOX": "bottom_left", "HUD_ICONS": "ascii"})
    try:
        start_new_game(other)
        other.keys("x", delay=0.6)
        lines = other.screen().splitlines()
        assert not lines[0].startswith("╭"), "the weather box is off"
        bottom = [i for i, l in enumerate(lines) if l.startswith("╰")]
        assert bottom, "\n".join(lines)
        top_edge = max(i for i, l in enumerate(lines[:bottom[-1]]) if l.startswith("╭"))
        box = "\n".join(l[:40] for l in lines[top_edge:bottom[-1] + 1])
        assert "│ f " in box or "│ / " in box or "│ = " in box or "│ ) " in box, box
    finally:
        other.close()

def test_boxes_replace_sidebar_rows(g):
    """What the weather and weapon boxes show leaves the sidebar; turning the boxes off brings it back."""
    spend_mana = "local a=gapi.get_avatar() a:get_magic():set_mana(1) out('ok')"
    assert g.lua(spend_mana) == ["ok"]
    settle(g)
    s = g.screen()
    lines = s.splitlines()
    boxes = "\n".join(l[:40] for l in lines[:16])
    assert any(icon in boxes for icon in ("☼", "☾", "☁", "☂", "↯", "❄", "◎", "▼")), "weather icon: " + boxes
    for fact in ("Light:", "Wind:", "Moon:", "Mana: 1/"):
        assert fact in boxes, f"{fact} belongs in a box:\n" + boxes
    assert re.search(r"(Spring|Summer|Autumn|Winter), day \d+", boxes), "box should show date: " + boxes
    # tmux drops trailing blanks, so a short line is all map; the sidebar starts at column 96.
    sidebar = "\n".join(l[96:] for l in lines)
    assert re.search(r"Place\s*:", sidebar) and re.search(r"X,Y,Z\s*:", sidebar), s
    for label in ("Sky", "Light", "Date", "Time", "Wield", "Style", "Mana"):
        assert not re.search(label + r"\s*:", sidebar), f"{label} is in a box already:\n" + s
    off = Game(name="bn-e2e-env-off", options={"SAFEMODE": "false", "HUD_WEATHER_BOX": "off", "HUD_COMBAT_BOX": "off"})
    try:
        start_new_game(off)
        off.define_lua("")
        assert off.lua(spend_mana) == ["ok"]
        off.keys("x", delay=0.6)
        s2 = off.screen()
        assert not s2.splitlines()[0].startswith("╭"), "boxes should be off:\n" + s2
        sidebar2 = "\n".join(l[96:] for l in s2.splitlines())
        for label in ("Sky", "Light", "Date", "Time", "Wield", "Style"):
            assert re.search(label + r"\s*:", sidebar2), f"{label} should be back in the sidebar:\n" + s2
        assert re.search(r"Mana\s*: 1/\d+", sidebar2), "mana reads current/max:\n" + s2
    finally:
        off.close()


def test_body_panel(g):
    arena(g)
    settle(g)
    s = g.screen()
    assert "No wounds" in s, s
    body = next(l for l in s.splitlines() if "No wounds" in l)
    coord = next(l for l in s.splitlines() if "X,Y,Z" in l)
    # The wound list starts on the same label grid as the Location panel, with no figure beside it.
    assert body.index("No wounds") == coord.index("X,Y,Z"), body + "\n" + coord
    g.lua("gapi.get_avatar():add_effect(EffectTypeId.new('bleed'), TimeDuration.from_minutes(30), BodyPartTypeId.new('arm_l'), 1) out('ok')")
    settle(g)
    assert "bleeding" in g.screen(), g.screen()
    action_menu(g, "Info", "Body status")
    details = g.screen()
    g.keys("Escape", delay=0.8)
    g.lua("gapi.get_avatar():remove_effect(EffectTypeId.new('bleed'), BodyPartTypeId.new('arm_l')) out('ok')")
    assert "bleeding" in details and "disinfectant" in details, details
    settle(g)
    assert "No wounds" in g.screen(), g.screen()


def test_readable_map_glyphs(g):
    """Trees and saplings draw as ♣ and τ instead of digits."""
    arena(g)
    # Right next to the character, so even a dark start can see them.
    g.lua("M:set_ter_at(here(-1,-1), TerId.new('t_tree'):int_id()) M:set_ter_at(here(1,-1), TerId.new('t_tree_young'):int_id()) out('ok')")
    settle(g)
    s = g.screen()
    g.lua("M:set_ter_at(here(-1,-1), TerId.new('t_floor'):int_id()) M:set_ter_at(here(1,-1), TerId.new('t_floor'):int_id()) out('ok')")
    x, y = g.find("@")
    row = s.splitlines()[y - 1]
    assert "♣" in row and "τ" in row, "\n".join(s.splitlines()[y - 2:y + 2])


def test_rounded_frames(g):
    g.keys("i", delay=1)
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert "╭" in s and "╯" in s, "inventory window should have rounded corners"


def test_gun_loudness_in_item_info(g):
    """A gun's item info says how loud a shot is, from the same noise the game makes when firing."""
    arena(g)
    give(g, "m9")
    g.keys("i", "/", delay=1)
    g.type("Beretta")
    g.keys("Enter", "Enter", delay=1.5)
    for _ in range(25):
        if "Loudness:" in g.screen():
            break
        g.keys("PageDown", delay=0.3)
    s = g.screen()
    m = re.search(r"Loudness: (\d+) \((silent|quiet|loud|very loud|deafening)\)", s)
    assert m, f"gun loudness line not found in item info:\n{s}"
    assert int(m.group(1)) > 0, s
    g.keys("Escape", delay=0.6)
    g.keys("Escape", delay=0.6)


def test_combine_partly_used_tools(g):
    """Partly used tools that nothing refills pour into one, keeping every charge."""
    arena(g)
    g.lua("local u=gapi.get_avatar() u:create_item(ItypeId.new('matches'),1):set_charges(5) "
          "u:create_item(ItypeId.new('matches'),1):set_charges(7) out('ok')")
    assert count_carried(g, "matches") == 2
    g.keys("i", "/", delay=1)
    g.type("matchbook")
    g.keys("Enter", "Enter", delay=1.2)
    g.wait_for("Combine", timeout=10)
    g.keys("C", delay=1)
    assert wait_until(lambda: count_carried(g, "matches") == 1, 30), g.screen()
    charges = g.lua("for _,it in ipairs(gapi.get_avatar():all_items(false)) do "
                    "if it:get_type():str()=='matches' then out(it.charges) end end")
    assert charges == ["12"], charges
    assert "You combine 2 matchbooks into one." in g.screen(), g.screen()
    g.keys("Escape", "Escape", delay=0.6)


def test_sound_marker_fading(_g):
    """A genuinely heard but unseen sound persists, then fades without a new source."""
    g = Game(name="bn-e2e-sound", options={"SAFEMODE": "false", "SOUND_MARKER_TURNS": "3"})
    try:
        start_new_game(g)
        g.define_lua(HELPERS)
        arena(g)
        # Underground ambient noise is fixed; surface wind can mask the shout.
        assert g.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() "
                     "a:clear_bionics() a:clear_mutations() a:clear_morale() a:drop_all_items() "
                     "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) arena() "
                     "for dy=-9,9 do M:set_ter_at(here(1,dy), TerId.new('t_wall'):int_id()) "
                     "for dx=2,3 do M:set_ter_at(here(dx,dy), TerId.new('t_floor'):int_id()) "
                     "M:set_furn_at(here(dx,dy), FurnId.new('f_null'):int_id()) end end "
                     "SOUND_NPC=M:place_npc(here(2,0),'farmer') "
                     "SOUND_NPC:drop_all_items() "
                     "SOUND_NPC:set_attitude(NpcAttitude.NPCATT_WAIT) out('ok')") == ["ok", "ok"]
        # Apply terrain and equipment changes before generating the sound.
        settle(g)
        assert g.lua("SOUND_NPC:shout('marker lifetime check',false) out('ok')") == ["ok"]

        def map_area():
            return "\n".join(line[:90] for line in g.screen().splitlines()[4:])

        assert wait_until(lambda: (g.keys("x", delay=0.6), "?" in map_area())[1], timeout=25), \
            "a heard, unseen NPC call should create a '?' marker:\n" + g.screen()
        assert g.lua("park(SOUND_NPC) out('ok')") == ["ok"]
        g.keys("x", delay=0.6)
        assert "?" in map_area(), "the configured three-turn marker must survive the next turn:\n" + g.screen()
        for _ in range(4):
            g.keys("x", delay=0.6)
        assert "?" not in map_area(), "sound markers should have faded:\n" + g.screen()
    finally:
        g.close()


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


def test_smart_safe_mode(g):
    """A hostile you can see but that has no way to reach you does not block auto-explore."""
    smart = Game(name="bn-e2e-smart-safe", options={"SAFEMODE": "true"})
    try:
        start_new_game(smart)
        smart.define_lua(HELPERS)
        arena(smart)
        # A glass cell keeps the zombie in sight but without a route to the player.
        smart.lua("for dx=-1,1 do for dy=-1,1 do if dx ~= 0 or dy ~= 0 then "
                  "M:set_ter_at(here(6+dx,dy), TerId.new('t_reinforced_glass'):int_id()) end end end "
                  "M:set_ter_at(here(6,0), TerId.new('t_floor'):int_id()) "
                  "gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(6,0)) out('ok')")
        settle(smart)
        smart.keys("x", delay=0.6)
        start = bub_pos(smart)
        smart.keys("n", delay=0.6)
        assert wait_until(lambda: bub_pos(smart) != start, timeout=15), \
            "auto-explore should run with a zombie locked in a glass cell:\n" + smart.screen()
        smart.keys("Escape", delay=0.3)
        # A zombie with a clear route still stops it.
        arena(smart)
        smart.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(3,0)) out('ok')")
        smart.keys("x", delay=0.6)
        smart.keys("n", delay=0.6)
        assert wait_until(lambda: "enemies in sight" in smart.screen(), timeout=10), \
            "a zombie that can reach you should stop auto-explore:\n" + smart.screen()
    finally:
        smart.close()

def test_smart_safe_mode_horde(g):
    """Twelve blocked routes are harmless; an unchecked thirteenth still stops travel."""
    smart = Game(name="bn-e2e-smart-horde", options={"SAFEMODE": "false"})
    try:
        start_new_game(smart)
        smart.define_lua(HELPERS)
        arena(smart)
        assert smart.lua(
            "for _,cr in ipairs(gapi.get_all_monsters()) do cr:make_friendly() end "
            "for dx=-12,12 do for dy=-12,12 do local p=here(dx,dy) "
            "M:set_ter_at(p, TerId.new('t_floor'):int_id()) "
            "M:set_furn_at(p, FurnId.new('f_null'):int_id()) end end "
            "for dx=-2,2 do for dy=-2,2 do if math.max(math.abs(dx),math.abs(dy))==2 then "
            "M:set_ter_at(here(dx,dy), TerId.new('t_reinforced_glass'):int_id()) end end end "
            "for dx=-6,4,2 do for _,dy in ipairs({-6,6}) do "
            "gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(dx,dy)) end end out('ok')"
        ) == ["ok"]
        settle(smart)
        smart.keys("n", delay=0.6)
        assert "enemies in sight" not in smart.screen(), \
            "all twelve blocked routes should be checked:\n" + smart.screen()
        smart.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(6,6)) out('ok')")
        settle(smart)
        smart.keys("n", delay=0.6)
        assert "enemies in sight" in smart.screen(), \
            "the unchecked thirteenth hostile must block auto-explore:\n" + smart.screen()
    finally:
        smart.close()



def test_contextual_interact_single_door(g):
    arena(g)
    g.lua("M:set_ter_at(here(1,0), TerId.new('t_door_c'):int_id()) out('ok')")
    settle(g)
    x, y = g.find("@")
    g.click(x + 1, y, button=2)
    before = bub_pos(g)
    clock = action_clock(g)
    g.keys("Space", delay=0.8)
    choose_menu_entry(g, "open the")
    assert g.lua("out(M:get_ter_at(here(1,0)):str_id():str())") == ["t_door_o"]
    assert bub_pos(g) == before
    assert action_clock(g) > clock, "opening a selected door must preserve the normal cost"


def test_contextual_interact_multiple_doors(g):
    arena(g)
    g.lua("M:set_ter_at(here(1,0), TerId.new('t_door_c'):int_id()) "
          "M:set_ter_at(here(-1,0), TerId.new('t_door_c'):int_id()) out('ok')")
    settle(g)
    g.keys("Escape", delay=0.4)
    if "MAIN MENU" in g.screen():
        g.keys("Escape", delay=0.4)
    g.keys("Space", delay=0.8)
    g.wait_for("Interact with which tile?")
    g.keys("d", delay=0.8)
    choose_menu_entry(g, "open the")
    assert g.lua("out(M:get_ter_at(here(1,0)):str_id():str(),"
                 "M:get_ter_at(here(-1,0)):str_id():str())") == ["t_door_o,t_door_c"]


EDGE_ARROWS = ("\u2192", "\u2197", "\u2198")


def zombie_down_a_corridor(name, options):
    """An 80x24 game with a zombie 30 tiles east down a lit corridor: visible, but off the map window."""
    edge = Game(name=name, cols=80, rows=24, options={"SAFEMODE": "false", **options})
    start_new_game(edge)
    edge.define_lua(HELPERS + " function corridor() for dx=5,40 do for dy=-1,1 do local p=here(dx,dy) "
                    "M:set_ter_at(p, TerId.new('t_floor'):int_id()) M:set_furn_at(p, FurnId.new('f_null'):int_id()) "
                    "end end gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(30,0)) "
                    "out(gapi.get_monster_at(here(30,0)) ~= nil) end")
    arena(edge)
    assert edge.lua("corridor()") == ["true"], edge.screen()
    settle(edge)
    return edge


def test_enemy_edge_arrows(g):
    """A hostile you can see but that sits outside the map window gets an edge arrow."""
    # A short safe-mode distance keeps the zombie 30 tiles away out of "reaches you soon".
    edge = zombie_down_a_corridor("bn-e2e-edge", {"SAFEMODEPROXIMITY": "10"})
    try:
        screen = edge.screen()
        assert any(a in screen for a in EDGE_ARROWS), "no east arrow for the off-screen zombie:\n" + screen
        # Yellow, not red: it can walk to the player but not within twice the safe-mode distance.
        # Only the east arrow: arena() parks stray monsters to the south-east, which may be close.
        row = next((l for l in edge.screen_colors().splitlines() if "\u2192" in l), None)
        assert row is not None, edge.screen_colors()
        assert any(f"\x1b[{c}m\u2192" in row for c in ("33", "93")), "yellow arrow expected, got:\n" + repr(row)
    finally:
        edge.close()


def test_enemy_edge_arrows_off(g):
    """The option puts the plain map back."""
    edge = zombie_down_a_corridor("bn-e2e-edge-off", {"ENEMY_EDGE_ARROWS": "false"})
    try:
        assert not any(a in edge.screen() for a in EDGE_ARROWS), edge.screen()
    finally:
        edge.close()





def test_center_view_at_top_level(_g):
    """Upstream #10604: pressing the CENTER action at z=10 must not crash."""
    g = Game(name="bn-e2e-center-view", options={"SAFEMODE": "false"})
    try:
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)
        assert g.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() p.z=10 "
                     "gapi.get_map():set_ter_at(p,TerId.new('t_floor'):int_id()) "
                     "gapi.place_player_local_at(p) out(a:get_pos_ms().z)") == ["10"], g.screen()
        action_menu(g, "Look", "Center View")
        # The game process must still be answering Lua, i.e. it did not SIGSEGV.
        assert g.lua("out(gapi.get_avatar():get_pos_ms().z)") == ["10"], g.screen()
        g.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() p.z=0 gapi.place_player_local_at(p) out('ok')")
    finally:
        g.close()


def test_examine_empty_floor_describes_it(_g):
    """Upstream #9987: with autoselect off, examining an empty floor tile prints its description."""
    g = Game(name="bn-e2e-examine-floor", options={"SAFEMODE": "false",
             "AUTOSELECT_SINGLE_VALID_TARGET": "false"})
    try:
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)
        arena(g)
        action_menu(g, "Interact", "Examine")
        g.keys("d", delay=1.5)
        assert "That is a" in g.screen(), g.screen()
    finally:
        g.close()


def test_char_creation_overview_fits_small_terminal(_g):
    """Upstream #10427: the OVERVIEW tab must show Scenario:/Profession: on an 80x24 terminal."""
    g = Game(name="bn-e2e-cc-overview", cols=80, rows=24, options={"SAFEMODE": "false"})

    def selected(word, name):
        return any(word in line and name in line for line in g.screen().splitlines())

    try:
        for _ in range(200):
            s = g.screen()
            if "Select your language" in s:
                g.keys("1", delay=0.5)
            elif "[New Game]" in s or "Play Now" in s:
                line = next((l for l in s.splitlines() if "Custom Character" in l), "")
                if "Custom Character" in line and "»" in line:
                    g.keys("Enter", delay=1)
                    break
                g.keys("Down", delay=0.2)
            elif "Welcome to Bright Nights" in s:
                g.keys("Escape", delay=1)
            elif not s.strip():
                g.keys("F5", delay=1)
            elif "World Mods" in s or "World Options" in s:
                break
            else:
                time.sleep(0.5)
        for _ in range(160):
            s = g.screen()
            if "Are you SURE you're finished" in s:
                g.keys("Left", delay=0.5)
                g.keys("Enter", delay=1.5)
            elif "How should death work" in s:
                g.keys("r", delay=1)
            elif "SCENARIO" in s and "POINTS" in s and "World" not in s:
                break
            elif "World Mods" in s:
                g.keys("Tab", "Tab", delay=1)
            elif "World Options" in s:
                g.keys("Tab", delay=1)
            else:
                time.sleep(0.5)
        for _ in range(12):
            if "<│SCENARIO│>" in g.screen():
                break
            g.keys("Tab", delay=0.7)
        for _ in range(140):
            if selected("Scenario", "Trans-Coast"):
                break
            g.keys("Down", delay=0.12)
        g.keys("Enter", delay=1)
        for _ in range(12):
            if "<│PROFESSION│>" in g.screen():
                break
            g.keys("Tab", delay=0.7)
        for _ in range(80):
            if selected("Profession", "Augmentation"):
                break
            g.keys("Down", delay=0.12)
        g.keys("Enter", delay=1)
        for _ in range(12):
            s = g.screen()
            if "Remaining points will be discarded" in s:
                g.keys("Escape", delay=0.8)
                continue
            if "finish character creation" in s or "<│OVERVIEW│>" in s:
                break
            g.keys("Tab", delay=0.7)
        s = g.screen()
        assert "Scenario:" in s, s
        assert "Profession:" in s, s
        assert re.search(r"Scenario:\s*\S", s), s
        assert re.search(r"Profession:\s*\S", s), s
    finally:
        g.close()

TESTS = [test_welcome_card, test_death_mode_choice, test_auto_explore, test_first_time_tip, test_unified_batteries, test_black_powder_rounds_stack, test_jewelry_is_one_item_per_form, test_mixed_jewelry_stacks, test_folded_families, test_mre_unpacks_its_entree, test_wasd_movement, test_wait_keeps_position, test_blocked_step_says_why,
         test_hud_boxes, test_body_panel, test_readable_map_glyphs, test_quick_stack, test_quick_stack_not_through_windows, test_black_powder_loot_keeps_its_modifier, test_sort_pile, test_rounded_frames, test_crafting_opens_on_content, test_craft_parts_chain,
         test_aim_defaults, test_sound_marker_fading, test_smart_targeting, test_stance_toggle, test_contextual_interact_single_door, test_contextual_interact_multiple_doors,
         test_recraft_after_reload, test_black_powder_survives_reloading, test_walking_into_enemy_attacks, test_bump_attack_can_be_disabled, test_attack_command, test_action_menu_opens_character_info, test_hover_inspects_without_acting, test_left_click_attacks_adjacent_enemy, test_right_click_selects_adjacent_enemy_for_f,
         test_magnet_pull_through_monster, test_vehicle_screen_diagonals, test_classic_control_scheme, test_wasd_menu_navigation, test_old_full_keybindings_file, test_hud_box_options, test_boxes_replace_sidebar_rows, test_gun_loudness_in_item_info, test_combine_partly_used_tools,
         test_smart_safe_mode, test_smart_safe_mode_horde, test_enemy_edge_arrows, test_enemy_edge_arrows_off,
         test_modern_wield_nearby_rows_keep_their_shortcut,
         test_center_view_at_top_level, test_examine_empty_floor_describes_it, test_char_creation_overview_fits_small_terminal,
         ]
TESTS += VEHICLE_BOX_TESTS
TESTS += CURSOR_PANNING_TESTS
TESTS += NPC_PALETTE_TESTS
TESTS += HUD_SIDEBAR_TESTS
TESTS += CONSTRUCTION_TAB_TESTS
TESTS += DISPOSE_MENU_TESTS
TESTS += FIRE_FEEDBACK_TESTS
TESTS += KEYHINTS_SMALL_TESTS
TESTS += SAFE_MODE_SLEEP_TESTS
TESTS += VEHICLE_MEMORY_TESTS
TESTS += AIM_RETICLE_TESTS
TESTS += SAFE_CLICK_TESTS
TESTS += MAP_MOUSE_TESTS
TESTS += INVENTORY_MOUSE_TESTS
TESTS += PICKUP_FLOW_TESTS
TESTS += OPTIONS_MENU_TESTS
TESTS += INVENTORY_HUB_TESTS
TESTS += CONTEXTUAL_HUB_TESTS
TESTS += GROUPED_CONTROLS_TESTS
TESTS += HUD_STATUS_TESTS


def main():
    keep = "--keep" in sys.argv
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")]
    # Safe mode would stop movement whenever wildlife wanders into view.
    g = Game(options={"SAFEMODE": "false", "SOUND_MARKER_TURNS": "3"})
    failures = 0
    try:
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)
        # Lua-created inventory must not depend on the random starting outfit's pockets.
        assert g.lua("gapi.get_avatar():set_mutation(MutationBranchId.new('DEBUG_STORAGE')) out('ok')") == ["ok"]
        wanted = [a for a in sys.argv[1:] if not a.startswith("--")]
        for test in [t for t in TESTS if not wanted or any(w in t.__name__ for w in wanted)]:
            started = time.time()
            try:
                test(g)
                print(f"PASS {test.__name__} ({time.time() - started:.1f}s)")
            except Exception:
                failures += 1
                print(f"FAIL {test.__name__}")
                traceback.print_exc()
                print(g.screen())
                g.keys("Escape", delay=0.5)
    finally:
        if not keep:
            g.close()
    ran = len([t for t in TESTS if not wanted or any(w in t.__name__ for w in wanted)])
    print(f"{ran - failures}/{ran} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
