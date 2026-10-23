"""Folded item families, black powder, jewelry and item interaction.

Tests that take `g` run on the runner's main game; each sets up the items it needs.
"""
import re

from helpers import action_menu, arena, count_carried, empty_inventory, give, spawn, wait_until


def test_unified_batteries(g):
    """Battery variants merged into light/medium/heavy cells plus atomic ones."""
    out = g.lua("out(ItypeId.new('light_minus_battery_cell'):is_valid(), ItypeId.new('heavy_disposable_cell'):is_valid(), "
                "ItypeId.new('light_battery_cell'):is_valid(), ItypeId.new('light_atomic_battery_cell'):is_valid())")
    assert out == ["false,false,true,true"], out


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


def test_jewelry_is_one_item_per_form(g):
    """Rings, bracelets and the like are one item each; metal and gem are a variant the item remembers."""
    empty_inventory(g)
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
    # The YIELD preview menu disassembles without a query; the entree lands on the floor.
    assert wait_until(lambda: g.lua("count_at(0,0,'mre_lemontuna')") == ["1"], 60), g.screen()
    assert count_carried(g, "mre_ration") == 0


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
    empty_inventory(g)
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


def test_black_powder_survives_reloading(g):
    empty_inventory(g)
    arena(g)
    # Earlier fixtures can leave wounds that interrupt reloading.
    assert g.lua("local u=gapi.get_avatar() u:clear_effects() u:set_all_parts_hp_to_max() "
                 "local w=u:create_item(ItypeId.new('model_10_revolver'), -1) "
                 "local a=u:create_item(ItypeId.new('38_special'), 6) a:set_var_str('stack_mod:black_powder','3') "
                 "out(u:wield(w))") == ["true"]

    def round_loaded(loaded):
        screen = g.screen()
        if "Stop reloading?" in screen:
            g.keys("I", delay=0)
        return re.search(rf"\({loaded}\)\s*\[[^\]]+\]", screen) is not None

    for loaded in range(1, 7):
        g.keys("r", delay=0)
        g.wait_for("Reload item")
        g.keys("r", delay=0)
        g.wait_gone("Reload item")
        assert wait_until(lambda: round_loaded(loaded)), g.screen()
    out = g.lua(REVOLVER + "out(w.charges, w:get_var_str('stack_mod:black_powder','0'), w:display_name(1))")
    charges, black_powder, name = out[0].split(",", 2)
    assert int(charges) == 6, out
    assert int(black_powder) == 3, "the three black powder rounds move into the cylinder"
    assert "3 black powder" in name, name


REVOLVER = ("local w=nil for _,it in ipairs(gapi.get_avatar():all_items(false)) do "
            "if it:get_type():str()=='model_10_revolver' then w=it end end ")


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


TESTS = [
    test_unified_batteries,
    test_black_powder_rounds_stack,
    test_black_powder_loot_keeps_its_modifier,
    test_jewelry_is_one_item_per_form,
    test_mixed_jewelry_stacks,
    test_folded_families,
    test_mre_unpacks_its_entree,
    test_gun_loudness_in_item_info,
    test_combine_partly_used_tools,
    test_black_powder_survives_reloading,
    test_modern_wield_nearby_rows_keep_their_shortcut,
]
