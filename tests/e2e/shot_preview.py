import re
import tempfile
from pathlib import Path

from aim_reticle import action_clock
from fixtures import shared_game
from helpers import HELPERS, arena, choose_menu_entry, settle, wait_until
from map_mouse import firing_target_panel, mouse_view

BASE = {
    "SAFEMODE": "false",
    "CONTROL_SCHEME": "modern",
    "ARROW_KEY_AIM": "true",
    "SHOT_PREVIEW": "true",
    "ACCURACY_DISPLAY": "numbers",
}
GUN = ("GUN=gapi.get_avatar():create_item(ItypeId.new('model_10_revolver'),-1) "
       "GUN:ammo_set(ItypeId.new('38_special'),6) out(gapi.get_avatar():wield(GUN))")
WIPE = ("for _,m in ipairs(gapi.get_all_monsters()) do m:set_hp(0) end out('ok')")
NIGHTVISION = ("gapi.get_avatar():set_mutation(MutationBranchId.new('DEBUG_NIGHTVISION')) "
               "out('ok')")
LANE = ("for dx=0,7 do for dy=-2,2 do local p=here(dx,dy) "
        "M:set_ter_at(p,TerId.new('t_floor'):int_id()) "
        "M:set_furn_at(p,FurnId.new('f_null'):int_id()) M:clear_items_at(p) end end out('ok')")


def profile(**extra):
    return {**BASE, **extra}


def scene(game):
    arena(game)
    assert game.lua(WIPE) == ["ok"]
    settle(game)
    assert game.lua(NIGHTVISION) == ["ok"]
    assert game.lua(LANE) == ["ok"]
    settle(game)
    assert game.lua(GUN) == ["true"]
    settle(game)


def furniture(game, dx, dy, furn):
    assert game.lua(f"M:set_furn_at(here({dx},{dy}),FurnId.new('{furn}'):int_id()) out('ok')") == ["ok"]


def clear_furniture(game):
    assert game.lua("for dx=-5,5 do for dy=-5,5 do "
                    "M:set_furn_at(here(dx,dy),FurnId.new('f_null'):int_id()) end end out('ok')") == ["ok"]


def spawn(game, name, dx, dy, monster="mon_zombie"):
    assert game.lua(
        f"{name}=gapi.place_monster_at(MonsterTypeId.new('{monster}'),here({dx},{dy})) "
        f"{name}:set_hp(1000) {name}:set_moves(-1000000) out({name} ~= nil)") == ["true"]
    settle(game)


def pin(game, *placements):
    code = " ".join(f"{name}:set_pos_ms(here({dx},{dy})) {name}:set_moves(-1000000)"
                    for name, dx, dy in placements)
    assert game.lua(code + " out('ok')") == ["ok"]


def overlays(game, kind):
    try:
        state = game.state()
    except (OSError, ValueError):
        return []
    return [entry for entry in state.get("map_overlays", []) if entry.get("kind") == kind]


def panel_until(game, pattern, timeout=20):
    last = {"panel": ""}

    def check():
        try:
            last["panel"] = firing_target_panel(game)
        except AssertionError:
            return False
        return re.search(pattern, last["panel"]) is not None

    if not wait_until(check, timeout=timeout):
        raise AssertionError(f"the firing window never showed {pattern!r}:\n"
                             + last["panel"] + "\n" + game.screen())
    return last["panel"]


def panel_gone(game, pattern, timeout=20):
    def check():
        try:
            return re.search(pattern, firing_target_panel(game)) is None
        except AssertionError:
            return True

    assert wait_until(check, timeout=timeout), \
        f"the firing window kept showing {pattern!r}\n" + game.screen()


def mouse_view_until(game, pattern, timeout=20):
    last = {"view": ""}

    def check():
        try:
            last["view"] = mouse_view(game)
        except AssertionError:
            return False
        return re.search(pattern, last["view"]) is not None

    if not wait_until(check, timeout=timeout):
        raise AssertionError(f"the Mouse View box never showed {pattern!r}:\n"
                             + last["view"] + "\n" + game.screen())
    return last["view"]


def open_aim_on_empty(game, dx):
    game.keys("Right", delay=0.5)
    for _ in range(dx):
        game.keys("Right", delay=0.2)
    game.keys("f", delay=1.0)
    game.wait_for("< Firing ", timeout=30)


def open_aim_on_nearest(game):
    game.keys("Right", delay=0.6)
    game.keys("f", delay=1.0)
    game.wait_for("< Firing ", timeout=30)
    panel_until(game, r"Targets: [1-9]")


def aim_rows(panel):
    lines = panel.splitlines()
    rows = {}
    for index, line in enumerate(lines):
        match = re.search(r"\b(Current|Regular|Careful|Precise) Aim: Moves to fire: (\d+)", line)
        if not match:
            continue
        total = 0
        for following in lines[index + 1:index + 4]:
            percentages = [int(value) for value in re.findall(r"(\d+)%", following)]
            if percentages:
                total = sum(percentages)
                break
        rows[match.group(1)] = (int(match.group(2)), total)
    return rows


def test_cover_on_the_line_and_point_blank(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-shot-cover-"))
    with shared_game("bn-e2e-shot-cover", options=profile(), define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        scene(game)
        furniture(game, 2, 0, "f_counter")
        open_aim_on_empty(game, 4)
        panel = firing_target_panel(game)
        assert "Cover: counter, may block 50%" in panel, \
            "partial cover two tiles away must be named with its chance:\n" + panel
        assert wait_until(
            lambda: any(entry["label"] == "counter" and entry["severity"] == 50
                        for entry in overlays(game, "shot_blocker")), timeout=20), \
            "the state file never listed the cover tile\n" + game.screen()
        game.keys("Escape", delay=0.6)

        clear_furniture(game)
        furniture(game, 1, 0, "f_counter")
        open_aim_on_empty(game, 4)
        panel = firing_target_panel(game)
        assert "You shoot over counter" in panel, \
            "adjacent cover below 100% must be shot over:\n" + panel
        assert "may block" not in panel, "point-blank cover must not roll to block:\n" + panel
        game.keys("Escape", delay=0.6)


def test_creatures_in_the_way_and_behind(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-shot-line-"))
    with shared_game("bn-e2e-shot-line", options=profile(), define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        scene(game)
        spawn(game, "A", 4, 0)
        spawn(game, "B", 5, 0)
        pin(game, ("A", 4, 0), ("B", 5, 0))
        open_aim_on_nearest(game)
        panel = panel_until(game, r"Behind: (?:the |a )?zombie")

        game.keys("Right", delay=0.6)
        panel = panel_until(game, r"In the way: (?:the |a )?zombie")
        panel_gone(game, r"Behind:")
        game.keys("Escape", delay=0.6)


def test_stray_cone_narrows_with_the_aim_mode(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-shot-strays-"))
    with shared_game("bn-e2e-shot-strays", options=profile(), define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        scene(game)
        spawn(game, "A", 5, 0)
        spawn(game, "B", 5, 2)
        pin(game, ("A", 5, 0), ("B", 5, 2))
        open_aim_on_nearest(game)
        panel_until(game, r"Strays may hit:.*(?:the |a )?zombie")
        assert overlays(game, "stray_tile"), "the stray cone left no map tiles\n" + game.screen()

        game.keys("m", delay=0.8)
        game.wait_for("Select preferences", timeout=20)
        choose_menu_entry(game, "Precise")
        panel = panel_until(game, r"Precise Aim:")
        panel_gone(game, r"Strays may hit")
        game.keys("Escape", delay=0.6)


def test_advance_estimate_on_the_aim_rows(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-shot-advance-"))
    with shared_game("bn-e2e-shot-advance", options=profile(), define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        scene(game)
        spawn(game, "A", 5, 0, "mon_zeer")
        pin(game, ("A", 5, 0))
        open_aim_on_nearest(game)
        panel = panel_until(game, r"Precise Aim:")
        precise = next((line for line in panel.splitlines() if "Precise Aim:" in line), None)
        current = next((line for line in panel.splitlines() if "Current Aim:" in line), None)
        assert precise, "the aim window has no Precise row:\n" + panel
        assert current, "the aim window has no Immediate row:\n" + panel
        advance = re.search(r"\(~(\d+) tiles?\)", precise)
        assert advance and int(advance.group(1)) >= 1, \
            "the fast target must cross at least a tile while aiming precisely:\n" + panel
        assert not re.search(r"\(~\d+ tiles?\)", current), \
            "an Immediate shot takes no aiming time to advance during:\n" + panel
        game.keys("Escape", delay=0.6)


def test_hit_label_matches_the_selected_row(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-shot-label-"))
    with shared_game("bn-e2e-shot-label", options=profile(), define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        scene(game)
        spawn(game, "A", 4, 0)
        pin(game, ("A", 4, 0))
        open_aim_on_nearest(game)
        panel = panel_until(game, r"Current Aim: Moves to fire: \d+")
        rows = aim_rows(panel)
        assert "Current" in rows, "the selected Immediate row is missing:\n" + panel
        moves, chance = rows["Current"]

        view = mouse_view_until(game, r"Immediate: \d+% hit, \d+ moves")
        label = re.search(r"Immediate: (\d+)% hit, (\d+) moves", view)
        assert label, "the Mouse View box lacks the aim label:\n" + view
        assert int(label.group(1)) == chance, \
            f"the label's {label.group(1)}% must equal the row's {chance}%\n{view}"
        assert int(label.group(2)) == moves, \
            f"the label's {label.group(2)} moves must equal the row's {moves}\n{view}"

        labelled = overlays(game, "aim_label")
        assert labelled and re.search(rf"\b{chance}% hit", labelled[0]["label"]), \
            "the state file does not carry the aim label\n" + game.screen()
        game.keys("Escape", delay=0.6)


def test_click_retargets_then_fires(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-shot-click-"))
    with shared_game("bn-e2e-shot-click", options=profile(), define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        scene(game)
        spawn(game, "A", 4, 0)
        spawn(game, "B", 5, 0)
        pin(game, ("A", 4, 0), ("B", 5, 0))
        clock = action_clock(game)
        open_aim_on_nearest(game)
        panel_until(game, r"Range: 4/")

        before = game.state()
        origin = game.find("@")
        assert origin, game.screen()
        game.click(origin[0] + 5, origin[1], button=2)
        panel_until(game, r"Range: 5/")
        after = game.state()
        assert after["player"]["pos"] == before["player"]["pos"], \
            "retargeting must not move the player"
        assert after["turn"] == before["turn"], "retargeting must not pass a turn"

        game.click(origin[0] + 5, origin[1])
        panel_until(game, r"Ammo: [^\n]*\(5/6\)")
        game.keys("Escape", delay=0.6)
        assert action_clock(game) > clock, "the shot must spend moves"
        assert game.lua("out(GUN:ammo_remaining())") == ["5"], "the shot did not spend ammo"


def test_damage_and_ap_match_the_item_info(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-shot-damage-"))
    with shared_game("bn-e2e-shot-damage", options=profile(), define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        scene(game)
        spawn(game, "A", 4, 0)
        pin(game, ("A", 4, 0))
        open_aim_on_nearest(game)
        panel = firing_target_panel(game)
        shown = re.search(r"Damage: (\d+)\s+Armor-pierce: (\d+)", panel)
        assert shown, "the gun panel lacks damage and armor-pierce:\n" + panel
        game.keys("Escape", delay=0.6)

        game.keys("i", "/", delay=1)
        game.type("Model 10")
        game.keys("Enter", "Enter", delay=1.5)
        for _ in range(20):
            if "Ranged damage" in game.screen() and "Armor-pierce" in game.screen():
                break
            game.keys("PageDown", delay=0.3)
        info = game.screen()
        damage = re.search(r"Ranged damage:.*?=\s*(\d+)", info)
        pierce = re.search(r"Armor-pierce:.*?=\s*(\d+)", info)
        assert damage and pierce, "the item info lacks the ranged damage line:\n" + info
        assert int(shown.group(1)) == int(damage.group(1)), \
            f"gun panel damage {shown.group(1)} != item info {damage.group(1)}\n{info}"
        assert int(shown.group(2)) == int(pierce.group(1)), \
            f"gun panel AP {shown.group(2)} != item info {pierce.group(1)}\n{info}"
        game.keys("Escape", "Escape", delay=0.6)


def test_option_off_leaves_the_aim_window_unchanged(_g):
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-shot-off-"))
    with shared_game("bn-e2e-shot-off", options=profile(SHOT_PREVIEW="false"), define=HELPERS,
                     userdir=userdir, state_path=userdir / "state.json") as game:
        scene(game)
        furniture(game, 2, 0, "f_counter")
        open_aim_on_empty(game, 4)
        panel = firing_target_panel(game)
        for text in ("Cover:", "may block", "You shoot over", "In the way", "Behind:",
                     "Strays may hit", "tiles)"):
            assert text not in panel, f"option off still shows {text!r}:\n" + panel
        for kind in ("shot_blocker", "stray_tile", "aim_label"):
            assert not overlays(game, kind), \
                f"option off still publishes a {kind} overlay\n" + game.screen()
        game.keys("Escape", delay=0.6)


TESTS = [
    test_cover_on_the_line_and_point_blank,
    test_creatures_in_the_way_and_behind,
    test_stray_cone_narrows_with_the_aim_mode,
    test_advance_estimate_on_the_aim_rows,
    test_hit_label_matches_the_selected_row,
    test_click_retargets_then_fires,
    test_damage_and_ap_match_the_item_info,
    test_option_off_leaves_the_aim_window_unchanged,
]
