#!/usr/bin/env python3
"""End-to-end checks for the overhaul, played through the real curses binary in tmux."""
import re
import sys
import time
import traceback

from tmux_game import Game, start_new_game

HELPERS = (
    "M=gapi.get_map() function here(dx,dy) local c=gapi.get_avatar():get_pos_ms() return TripointBubMs.new(c.x+dx,c.y+dy,c.z) end "
    "function arena() local k=0 for dx=-13,13 do for dy=-13,13 do local p=here(dx,dy) "
    "if math.abs(dx)<=4 and math.abs(dy)<=4 then M:set_ter_at(p, TerId.new('t_floor'):int_id()) end "
    "M:set_furn_at(p, FurnId.new('f_null'):int_id()) M:clear_items_at(p) "
    "local cr=gapi.get_creature_at(p) if cr and not cr:is_avatar() then k=k+1 cr:set_pos_ms(here(30+k,30)) end end end out('ok') end "
    "function units(it) if it:is_stackable() then return it.charges end return 1 end "
    "function count_at(dx,dy,id) local n=0 for _,it in pairs(M:get_items_at(here(dx,dy))) do "
    "if it:get_type():str()==id then n=n+units(it) end end out(n) end "
    "function carried(id) local n=0 for _,it in ipairs(gapi.get_avatar():all_items(false)) do "
    "if it:get_type():str()==id then n=n+units(it) end end out(n) end "
    "function spawn(dx,dy,id,n,furn) local p=here(dx,dy) if furn then M:set_furn_at(p, FurnId.new(furn):int_id()) end "
    "for i=1,n do M:create_item_at(p, ItypeId.new(id), -1) end out('ok') end "
    "function give(id,n) for i=1,n do gapi.get_avatar():create_item(ItypeId.new(id), -1) end out('ok') end "
    "function pos() local p=gapi.get_avatar():abs_pos() out(p.x,p.y,p.z) end"
)


def arena(g):
    assert g.lua("arena()") == ["ok"]


def bub_pos(g):
    return tuple(int(v) for v in g.lua("pos()")[0].split(","))


def count_at(g, dx, dy, item):
    return int(g.lua(f"count_at({dx},{dy},'{item}')")[0])


def count_carried(g, item):
    return int(g.lua(f"carried('{item}')")[0])


def spawn(g, dx, dy, item, n=1, furn=None):
    furn = f"'{furn}'" if furn else "nil"
    assert g.lua(f"spawn({dx},{dy},'{item}',{n},{furn})") == ["ok"]


def give(g, item, n=1):
    assert g.lua(f"give('{item}',{n})") == ["ok"]


def settle(g):
    # Let queued moves play out so the sidebar and map are current.
    g.keys("x", delay=0.6)


def test_welcome_card(g):
    assert getattr(g, "saw_welcome", False), "first new game should show the welcome card"


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
    g.lua("local m=gapi.get_monster_at(here(4,0)) if m then m:set_pos_ms(here(40,40)) end out('ok')")


def test_controls_strip(g):
    s = g.screen()
    for hint in ("wasd move", "qezc diag", "Q stash", "Z sort pile"):
        assert hint in s, f"missing {hint!r} in sidebar"


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
    g.keys("Q", delay=1.5)
    settle(g)
    assert count_at(g, 2, 0, "usb_drive") == 4, "drives should join the rack"
    assert count_carried(g, "usb_drive") == 0
    assert count_carried(g, "plastic_six_dice") == 1, "nothing nearby holds dice, so they stay"
    assert "Stashed 3 items into 1 spot" in g.screen()


def test_quick_stack_not_through_windows(g):
    arena(g)
    assert g.lua("M:set_ter_at(here(1,0), TerId.new('t_window'):int_id()) out('ok')") == ["ok"]
    spawn(g, 2, 0, "usb_drive", furn="f_rack")
    give(g, "usb_drive", 2)
    g.keys("Q", delay=1.5)
    settle(g)
    assert count_carried(g, "usb_drive") == 2, "a shelf behind a window is out of reach"
    assert count_at(g, 2, 0, "usb_drive") == 1
    g.lua("M:set_ter_at(here(1,0), TerId.new('t_floor'):int_id()) out('ok')")


def test_black_powder_loot_keeps_its_modifier(g):
    arena(g)
    g.lua("for i=1,5 do M:place_items('ammo_rifle_blackpowder_handloads', 100, here(2,0), here(2,0), false) end out('ok')")
    rows = g.lua("for _,it in pairs(M:get_items_at(here(2,0))) do out(it.charges, it:get_var_num('stack_mod:black_powder', 0)) end")
    assert rows, "the group should spawn something"
    for row in rows:
        charges, bp = (int(float(v)) for v in row.split(","))
        assert bp == charges, f"every spawned round is black powder: {rows}"


def test_sort_pile(g):
    arena(g)
    spawn(g, 3, 0, "usb_drive", furn="f_rack")
    spawn(g, -3, 0, "flyer", furn="f_rack")
    spawn(g, 0, 0, "usb_drive", 2)
    spawn(g, 0, 0, "character_sheet", 1)
    spawn(g, 0, 0, "plastic_six_dice", 1)
    g.keys("Z", delay=1.5)
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
    g.keys("k", delay=1.5)
    g.keys("f", delay=0.8)
    g.type(name)
    g.keys("Enter", delay=1.5)
    for _ in range(3):
        if "Searched" not in g.screen():
            break
        g.keys("Enter", delay=1.5)


def test_crafting_opens_on_content(g):
    g.keys("k", delay=1.5)
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
    assert wait_until(lambda: count_carried(g, "glass_shard_trap") == 1), g.screen()
    g.keys("Escape", delay=1)
    g.keys("S", delay=1)
    g.keys("y", "Enter", delay=1)
    g.wait_for("[Load]", timeout=60)
    load_first_save(g)
    g.define_lua(HELPERS)
    g.keys("-", delay=1)
    assert wait_until(lambda: count_carried(g, "glass_shard_trap") == 2), g.screen()


def load_first_save(g, timeout=120):
    """After save-and-quit the main menu reopens on Load; Enter picks the world, then the character."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = g.screen()
        if "X,Y,Z:" in s and " move " in s:
            return
        if "»" in s:
            g.keys("Enter", delay=2)
        else:
            time.sleep(0.5)
    raise AssertionError("could not load the save\n" + g.screen())


def test_aim_defaults(g):
    g.keys("/", delay=1.5)
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
    g.lua("for dx=-6,6 do for dy=-6,6 do local m=gapi.get_monster_at(here(dx,dy)) if m then m:set_pos_ms(here(40,40)) end end end out('ok')")


def test_unified_batteries(g):
    """Battery variants merged into light/medium/heavy cells plus atomic ones."""
    out = g.lua("out(ItypeId.new('light_minus_battery_cell'):is_valid(), ItypeId.new('heavy_disposable_cell'):is_valid(), "
                "ItypeId.new('light_battery_cell'):is_valid(), ItypeId.new('light_atomic_battery_cell'):is_valid())")
    assert out == ["false,false,true,true"], out


def zombie_hp(g):
    out = g.lua("local m=gapi.get_monster_at(here(1,0)) if m then out(m:get_hp()) else out(-1) end")
    return int(out[0])


def test_walking_into_enemy_does_not_attack(g):
    arena(g)
    assert g.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) out('ok')") == ["ok"]
    before = zombie_hp(g)
    assert before > 0
    g.keys("d", delay=1)
    assert "in the way" in g.screen(), g.screen()
    assert zombie_hp(g) == before, "a plain step must not swing at the zombie"


def test_attack_command(g):
    """Sword of the Stars: The Pit style: F attacks the nearest enemy; Tab and a direction picks one."""
    for keys, why in ((("F",), "F should attack the nearest enemy"), (("Tab", "d"), "Tab then a direction should attack")):
        before = zombie_hp(g)
        for _ in range(6):
            for k in keys:
                g.keys(k, delay=1)
            if zombie_hp(g) != before:
                break
        assert zombie_hp(g) != before, why
    g.lua("local m=gapi.get_monster_at(here(1,0)) if m then m:set_pos_ms(here(40,40)) end out('ok')")


def test_click_to_travel(g):
    arena(g)
    settle(g)
    start = bub_pos(g)
    x, y = g.find("@")
    g.click(x + 3, y)
    assert wait_until(lambda: bub_pos(g) == (start[0] + 3, start[1], start[2]), timeout=15), (start, bub_pos(g))


def test_hover_says_what_a_click_does(g):
    """Sword of the Stars: The Pit style: hovering a tile highlights it and names the click action."""
    arena(g)
    settle(g)
    x, y = g.find("@")
    g.hover(x + 3, y)
    assert "click: walk here (3 steps)" in g.screen(), g.screen()


def test_click_attacks_an_adjacent_enemy(g):
    arena(g)
    assert g.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) out('ok')") == ["ok"]
    settle(g)
    before = zombie_hp(g)
    x, y = g.find("@")
    g.hover(x + 1, y)
    assert re.search(r"click: attack[^\n]*\[\S+\]", g.screen()), "hover hint should name the key: " + g.screen()
    for _ in range(6):
        g.click(x + 1, y)
        if zombie_hp(g) != before:
            break
    assert zombie_hp(g) != before, "clicking an adjacent enemy attacks it"


def test_right_click_lists_actions(g):
    x, y = g.find("@")
    g.click(x + 1, y, button=2)
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert "attack" in s, s
    g.lua("local m=gapi.get_monster_at(here(1,0)) if m then m:set_pos_ms(here(40,40)) end out('ok')")


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
    assert g.lua("local u=gapi.get_avatar() u:add_item(gapi.create_item(ItypeId.new('model_10_revolver'), -1)) "
                 "local a=gapi.create_item(ItypeId.new('38_special'), 6) a:set_var_str('stack_mod:black_powder','3') u:add_item(a) "
                 + REVOLVER + "out(u:wield(w))") == ["true"]
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
        g.keys("(", delay=1)
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
    g.keys("u", delay=1)
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
    old = Game(name="bn-e2e-oldkeys", options={"SAFEMODE": "false"},
               keybindings="data/raw/keybindings/keybindings.json")
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
    g.keys("F12", "s", "v", delay=1)
    g.keys("p", delay=1.5)  # Bicycle, spawned under the player
    g.keys("Enter", delay=1.5)
    g.keys("Enter", delay=1.5)
    g.keys("Space", delay=1.5)
    g.keys("x", delay=1.5)
    g.keys("e", delay=2)  # "Examine vehicle"
    try:
        start = g.screen()
        assert "Siphon" in start and "rEname" in start and "creW" in start, start
        g.keys("s", delay=1.5)
        moved = g.screen()
        assert "ESC-back" in moved and moved != start, "s should move the cursor, not siphon"
        g.keys("e", delay=1.5)
        diag = g.screen()
        assert "ESC-back" in diag and "new name" not in diag.lower() and diag != moved, "e should move diagonally, not rename"
    finally:
        g.keys("Escape", delay=1)


def test_rounded_frames(g):
    g.keys("i", delay=1)
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert "╭" in s and "╯" in s, "inventory window should have rounded corners"


TESTS = [test_welcome_card, test_death_mode_choice, test_first_time_tip, test_controls_strip, test_unified_batteries, test_black_powder_rounds_stack, test_jewelry_is_one_item_per_form, test_mixed_jewelry_stacks, test_folded_families, test_mre_unpacks_its_entree, test_wasd_movement, test_wait_keeps_position, test_blocked_step_says_why,
         test_quick_stack, test_quick_stack_not_through_windows, test_black_powder_loot_keeps_its_modifier, test_sort_pile, test_rounded_frames, test_crafting_opens_on_content,
         test_aim_defaults, test_recraft_after_reload, test_black_powder_survives_reloading, test_walking_into_enemy_does_not_attack, test_attack_command, test_click_to_travel, test_hover_says_what_a_click_does, test_click_attacks_an_adjacent_enemy, test_right_click_lists_actions,
         test_magnet_pull_through_monster, test_vehicle_screen_diagonals, test_classic_control_scheme, test_old_full_keybindings_file]


def main():
    keep = "--keep" in sys.argv
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")]
    # Safe mode would stop movement whenever wildlife wanders into view.
    g = Game(options={"SAFEMODE": "false"})
    failures = 0
    try:
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)
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
