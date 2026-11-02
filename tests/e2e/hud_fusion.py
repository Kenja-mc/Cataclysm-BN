"""The fusion HUD: ribbon and key bar over the map, ruled sections beside it."""
import re

from fixtures import shared_game
from helpers import HELPERS, arena, bub_pos, empty_inventory, give, wait_until
from hud_status import healthy
from tmux_game import Game, start_new_game

OPTIONS = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false", "SHOW_WELCOME": "false",
           "SHOW_TIPS": "false", "ANIMATIONS": "false", "INITIAL_TIME": "12"}


def fusion_setup(game):
    game.resize(160, 45)
    empty_inventory(game)
    arena(game)
    healthy(game)
    assert game.lua("local a=gapi.get_avatar() "
                    "a:add_effect(EffectTypeId.new('bleed'),TimeDuration.from_minutes(30),"
                    "BodyPartTypeId.new('arm_l'),1) out('ok')") == ["ok"]


def rule_rows(screen, title):
    return [line for line in screen.splitlines() if re.search(r"├─* *" + title + r"\b", line)]


def assert_fusion(screen):
    for title in ("STATUS", "AROUND", "LOADOUT", "LOG"):
        assert len(rule_rows(screen, title)) == 1, f"one {title} rule expected:\n{screen}"
    first = screen.splitlines()[0]
    assert re.search(r"(Spring|Summer|Autumn|Winter) \d+", first), \
        f"the date and time belong at the top left:\n{screen}"
    # The limbs panel's own grid stands in for an aggregate health bar and the BODY section.
    for limb in ("L ARM", "HEAD", "R ARM", "L LEG", "TORSO", "R LEG"):
        assert limb in screen, f"the {limb} bar is missing:\n{screen}"
    assert "Stamina" in screen, f"the stamina bar is missing:\n{screen}"
    assert "Health " not in screen, "there is no aggregate health bar:\n" + screen
    assert not rule_rows(screen, "BODY"), "the limbs live in STATUS now:\n" + screen
    # The shared character may carry a wound, so the needs row's met state is covered on a fresh
    # character by test_needs_collapse_to_one_needs_met_line.
    # The floating windows and the old sidebar panels are gone.
    for old in ("Compass", "Movement", "Stats ", "Weight"):
        assert old not in screen, f"{old!r} belongs to another layout:\n{screen}"


def test_fusion_layout_draws_overlays_and_ruled_sidebar(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        game.settle_screen()
        assert_fusion(game.screen())


def test_fusion_is_the_fresh_default_and_small_screens_fall_back(_g):
    # No panel_options.json is seeded: this is the real first-run layout.
    game = Game("bn-e2e-fusion-default", options=OPTIONS, layout=None, cols=160, rows=45)
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        fusion_setup(game)
        game.settle_screen()
        assert_fusion(game.screen())
        game.resize(100, 30)
        game.settle_screen()
        small = game.screen()
        assert "LOADOUT" not in small and not rule_rows(small, "STATUS"), \
            "below 140x36 the grouped layout must replace fusion:\n" + small
        game.resize(160, 45)
        game.settle_screen()
        assert_fusion(game.screen())
    finally:
        game.close()


def wielded(game):
    return game.lua("local n='' for _,w in ipairs(gapi.get_avatar():wielded_items()) do n=n..w:get_type():str() end out(n)")[0]


def test_hotbar_slot_wields_its_item_and_empty_slot_is_inert(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        give(game, "knife_combat", 1)
        before = bub_pos(game)
        game.keys("1", delay=0.6)
        assert bub_pos(game) == before, "an empty slot must not move the character"
        assert "Hotbar slot 1 is empty" in game.screen(), game.screen()
        assert game.lua("gapi.get_avatar():set_value('hotbar_2','knife_combat') out('ok')") == ["ok"]
        game.settle_screen()
        game.keys("2", delay=0.8)
        game.settle_screen()
        assert "knife" in wielded(game), "slot 2 should wield the combat knife"
        assert bub_pos(game) == before


def test_hotbar_assign_menu_stores_the_chosen_item(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        give(game, "knife_combat", 1)
        game.keys("C-t", delay=0.6)
        game.wait_for("Assign which hotbar slot", timeout=15)
        game.keys("3", delay=0.8)
        game.wait_for("Put which item", timeout=15)
        game.keys("Enter", delay=0.8)
        game.settle_screen()
        assert game.lua("out(gapi.get_avatar():get_value('hotbar_3'))") == ["knife_combat"], game.screen()


def test_clicking_a_hotbar_slot_uses_it_and_overlay_clicks_stay_off_the_map(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        give(game, "knife_combat", 1)
        assert game.lua("gapi.get_avatar():set_value('hotbar_2','knife_combat') out('ok')") == ["ok"]
        game.settle_screen()
        before = bub_pos(game)
        for y, line in enumerate(game.screen().splitlines()):
            if "combat" in line:
                x = line.index("combat")
                break
        else:
            raise AssertionError("hotbar slot 2 missing:\n" + game.screen())
        game.click(x, y)
        game.settle_screen()
        assert "knife" in wielded(game), "a click on the slot should use it:\n" + game.screen()
        assert bub_pos(game) == before
        # A click on the column is swallowed, never walked to or selected on the map.
        game.click(120, 2)
        assert bub_pos(game) == before


def test_vehicle_card_replaces_the_floating_vehicle_window_while_aboard(_g):
    from vehicle_box import spawn_vehicle
    game = Game(name="bn-e2e-fusion-vehicle", layout="fusion", cols=160, rows=45,
                options={**OPTIONS, "USE_METRIC_SPEEDS": "mph"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        game.settle_screen()
        assert "VEHICLE" not in game.screen(), game.screen()
        spawn_vehicle(game)
        screen = game.screen()
        assert re.search(r"╭[^\n]*\bVEHICLE\b", screen), screen
        assert "Azimuth" in screen and "Speed: 0 mph" in screen, screen
    finally:
        game.close()


def test_around_names_who_is_in_sight(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        assert game.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(4,-3)) out('ok')") == ["ok"]
        game.keys("x", delay=0.8)
        game.settle_screen()
        # The load race can dim a noon world (the light-cache bug); AROUND then sees nothing and
        # this test would look like a layout failure. Say which one it is.
        top = game.screen().splitlines()[0]
        assert "very dark" not in top, f"the world loaded dim, the light-cache bug:\n{top}"
        game.wait_for("hostile", timeout=15)
        game.settle_screen()
        screen = game.screen()
        assert re.search(r"├─* *AROUND \d+ hostile", screen), screen
        assert re.search(r"zombie +[NSEW]{1,2} \d", screen), "AROUND names the creature and where it is:\n" + screen
        assert game.lua("for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end out('ok')") == ["ok"]
        game.keys("x", delay=0.8)


def last_line(screen):
    return screen.splitlines()[-1]


def test_status_draws_the_limb_grid_above_stamina_and_no_body_rule(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        game.settle_screen()
        screen = game.screen()
        lines = screen.splitlines()
        top = next(line for line in lines if all(n in line for n in ("L ARM", "HEAD", "R ARM")))
        bottom = next(line for line in lines if all(n in line for n in ("L LEG", "TORSO", "R LEG")))
        rule_row = next(i for i, line in enumerate(lines) if "STATUS" in line)
        stamina_row = next(i for i, line in enumerate(lines) if "Stamina" in line)
        assert rule_row < lines.index(top) < lines.index(bottom) < stamina_row, screen
        assert re.search(r"L ARM\s+\S{2,}", top), "every limb keeps its own bar:\n" + top
        assert not rule_rows(screen, "BODY"), "the body section is gone:\n" + screen
        assert "Health " not in screen, "no aggregate health bar:\n" + screen


def test_key_bar_switches_to_combat_keys_with_a_hostile_in_sight(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        game.settle_screen()
        calm = last_line(game.screen())
        assert "interact" in calm and "inventory" in calm, "the calm key bar:\n" + calm
        assert "next target" not in calm, calm
        assert game.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(4,-3)) out('ok')") == ["ok"]
        game.keys("x", delay=0.8)
        game.settle_screen()
        assert wait_until(lambda: "next target" in last_line(game.screen()), timeout=15), \
            "a hostile in sight switches the bar to combat keys:\n" + game.screen()
        combat = last_line(game.screen())
        assert re.search(r"attack|fire", combat), "the combat bar offers fire/attack:\n" + combat
        assert "interact" not in combat, combat
        assert game.lua("for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) park(m) end out('ok')") == ["ok"]
        game.keys("x", delay=0.8)
        game.keys("x", delay=0.8)
        assert wait_until(lambda: "interact" in last_line(game.screen()), timeout=15), \
            "the bar returns to the calm keys:\n" + game.screen()


def status_region(screen):
    """The drawn rows of the STATUS section, from its rule down to the next section's rule."""
    lines = screen.splitlines()
    start = next(y for y, line in enumerate(lines) if re.search(r"├─* *STATUS\b", line))
    end = next(y for y in range(start + 1, len(lines))
               if re.search(r"├─* *[A-Z]+\b", lines[y]))
    return lines[start:end]


def test_status_names_a_bleeding_limb_in_the_needs_line(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        assert game.lua("local a=gapi.get_avatar() a:clear_effects() a:set_pain(0) "
                        "a:add_effect(EffectTypeId.new('bleed'),TimeDuration.from_minutes(30),"
                        "BodyPartTypeId.new('arm_l'),1) out('ok')") == ["ok"]
        game.settle_screen()
        screen = game.screen()
        needs = next((line for line in status_region(screen) if "Bleeding" in line), None)
        assert needs is not None, "the STATUS needs line names the wound:\n" + screen
        assert "L ARM" in needs, "the wound names the limb it sits on:\n" + needs
        assert "Needs met" not in "\n".join(status_region(screen)), \
            "a wounded character cannot collapse its needs:\n" + screen


def test_needs_collapse_to_one_needs_met_line(_g):
    with shared_game("bn-e2e-fusion", options=OPTIONS, layout="fusion", cols=160, rows=45,
                     define=HELPERS, setup=fusion_setup) as game:
        # The fixture carries a bleeding arm; a character with nothing wrong collapses its needs.
        assert game.lua("local a=gapi.get_avatar() a:clear_effects() a:set_pain(0) out('ok')") == ["ok"]
        game.settle_screen()
        screen = game.screen()
        assert "Needs met" in screen, "a character with nothing wrong collapses its needs:\n" + screen
        assert re.search(r"Focus \d+", screen), "focus joins the needs line:\n" + screen
        assert re.search(r"Mood [+-]\d+", screen), "mood joins the needs line:\n" + screen
        for old in ("Str ", "Dex ", "Int ", "Per ", "Noise", "Speed 100"):
            assert old not in screen, f"{old!r} is on the @ sheet or is the normal state:\n" + screen


TESTS = [test_around_names_who_is_in_sight,
         test_vehicle_card_replaces_the_floating_vehicle_window_while_aboard,
         test_clicking_a_hotbar_slot_uses_it_and_overlay_clicks_stay_off_the_map,
         test_hotbar_slot_wields_its_item_and_empty_slot_is_inert,
         test_hotbar_assign_menu_stores_the_chosen_item,
         test_fusion_layout_draws_overlays_and_ruled_sidebar,
         test_status_draws_the_limb_grid_above_stamina_and_no_body_rule,
         test_key_bar_switches_to_combat_keys_with_a_hostile_in_sight,
         test_status_names_a_bleeding_limb_in_the_needs_line,
         test_needs_collapse_to_one_needs_met_line,
         test_fusion_is_the_fresh_default_and_small_screens_fall_back]

