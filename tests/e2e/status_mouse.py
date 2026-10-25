"""Modern scheme mouse support in the status screens: the h body report scrolls
and closes with the mouse, and the @ character screen clicks tabs, rows and
scrollbars like the keyboard does. Classic keeps the plain popups.

The first click on a row only selects it. Clicking the same row again runs the
same action as pressing Enter, so no initially selected row can fire by accident.
"""

import json
import tempfile
from pathlib import Path

from helpers import HELPERS, Game, arena, start_new_game
from tmux_game import ROOT

# Enough mutations to overflow the traits panel; preserve any the character already has.
TRAITS = ("FLEET", "GOODHEARING", "INATTENTIVE", "PARKOUR", "QUICK",
          "OPTIMISTIC", "OUTDOORSMAN", "BIOLUM1", "FEYHEARING",
          "GOODCARDIO", "GOODCARDIO2", "FASTLEARNER")

# Wounds used by the body report fixture.
WOUNDS = (("bleed", "arm_l"), ("bleed", "arm_r"), ("bleed", "leg_l"),
          ("bleed", "leg_r"), ("bite", "torso"), ("bandaged", "head"),
          ("infected", "foot_l"), ("bite", "hand_r"), ("disinfected", "hand_l"))


def moves(g):
    return int(g.lua("out(gapi.get_avatar():get_moves())")[0])


def stat(g, name):
    return int(g.lua(f"out(gapi.get_avatar():get_{name}())")[0])


def training(g, skill):
    return g.lua("out(gapi.get_avatar():get_skill_level_object("
                 f"SkillId.new('{skill}')):is_training())")[0] == "true"


def add_wounds(g):
    assert g.lua("local a=gapi.get_avatar() " + " ".join(
        f"a:add_effect(EffectTypeId.new('{effect}'), TimeDuration.from_minutes(30), "
        f"BodyPartTypeId.new('{part}'), 1)" for effect, part in WOUNDS) + " out('ok')") == ["ok"]


def set_traits(g):
    ids = ", ".join(f"'{trait}'" for trait in TRAITS)
    assert g.lua(
        f"local a=gapi.get_avatar() STATUS_MOUSE_ADDED_TRAITS={{}} for _,id in ipairs({{{ids}}}) do "
        "local trait=MutationBranchId.new(id) if not a:has_trait(trait) then "
        "a:set_mutation(trait) STATUS_MOUSE_ADDED_TRAITS[#STATUS_MOUSE_ADDED_TRAITS+1]=id "
        "end end out('ok')"
    ) == ["ok"]


def clear_traits(g):
    assert g.lua(
        "local a=gapi.get_avatar() for _,id in ipairs(STATUS_MOUSE_ADDED_TRAITS) do "
        "a:unset_mutation(MutationBranchId.new(id)) end STATUS_MOUSE_ADDED_TRAITS={} out('ok')"
    ) == ["ok"]


def find_in(g, text, x_max=None, y_min=0, y_max=None):
    """First cell holding `text`, searched only in a screen band so sidebar or
    info-panel copies of the same word cannot win."""
    lines = g.screen().splitlines()
    for y, line in enumerate(lines):
        if y < y_min or (y_max is not None and y > y_max):
            continue
        x = line.find(text)
        if x >= 0 and (x_max is None or x < x_max):
            return x, y
    raise AssertionError(f"no cell for {text!r} in band\n{g.screen()}")


def scrollbar_column(g):
    """Screen column and row of the top scrollbar arrow, found from the '^' that
    has its paired 'v' below it in the same column."""
    rows = g.screen().splitlines()
    for y, line in enumerate(rows):
        for x, ch in enumerate(line):
            if ch == "^" and any(len(row) > x and row[x] == "v" for row in rows[y + 1:]):
                return x, y
    raise AssertionError("no scrollbar arrows on screen\n" + g.screen())


def popup_width(g):
    """Width of the report measured from the borders beside its Close button."""
    cx, cy = find_in(g, "Close")
    row = g.screen().splitlines()[cy]
    left = row.rfind("│", 0, cx)
    right = row.find("│", cx)
    assert 0 <= left < right, "no report borders beside Close\n" + g.screen()
    return right - left + 1


def open_info(g):
    g.keys("@", delay=1.5)
    g.wait_for("STATS")


def close_info(g):
    if "STATS" in g.screen():
        g.keys("Escape", delay=1.0)
        g.wait_gone("STATS")


def test_body_report_close_button(g):
    """A left click on Close leaves the report; no move is spent."""
    g.resize(100, 25)
    arena(g)
    before = moves(g)
    g.keys("h", delay=1.5)
    g.wait_for("Close")
    width = popup_width(g)
    assert width < 100, f"report should size to its text, got {width}\n{g.screen()}"
    cx, cy = find_in(g, "Close")
    assert any(ch in g.screen().splitlines()[cy + 1] for ch in "╰└"), \
        "Close belongs on the row above the bottom border\n" + g.screen()
    g.click(cx, cy)
    g.wait_gone("Close")
    assert "ESCAPE]" not in g.screen(), g.screen()
    assert moves(g) == before, "the body report must not spend moves"
    g.resize(140, 45)


def long_body_report_game():
    """Exercise mod-provided headings through the real body report renderer."""
    userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-body-report-"))
    mod_id = "e2e_body_report_headings"
    mod_dir = userdir / "mods" / mod_id
    mod_dir.mkdir(parents=True)
    (mod_dir / "modinfo.json").write_text(json.dumps([{
        "type": "MOD_INFO", "id": mod_id, "name": "E2E body report headings",
        "description": "Long anatomical headings exercise report scrolling at a valid terminal size.",
        "category": "content", "dependencies": ["bn"],
    }]))
    labels = {"head": "Head", "torso": "Torso", "arm_l": "Left arm",
              "arm_r": "Right arm", "leg_l": "Left leg", "leg_r": "Right leg"}
    heading_detail = (
        "Skin and underlying soft tissues, connective tissue and supporting structures; "
        "the regional bones and joints, muscles and tendons, blood vessels and nerves; "
        "the outer surface and deeper structures that protect the body, permit movement "
        "and carry sensation, including their current injuries and ongoing treatment")
    (mod_dir / "body_parts.json").write_text(json.dumps([
        {"type": "body_part", "id": part, "copy-from": part,
         "heading": f"{label}: {heading_detail}"} for part, label in labels.items()
    ]))
    defaults = json.loads((ROOT / "data/mods/default.json").read_text())
    (userdir / "config").mkdir()
    (userdir / "config/default_mods.json").write_text(json.dumps([*defaults, mod_id]))
    game = Game(name="bn-e2e-body-report", userdir=userdir, cols=80, rows=25,
                options={"SAFEMODE": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
    except Exception:
        game.close()
        raise
    return game


def test_body_report_wheel_and_scrollbar(_g):
    """The wheel turns a long report and the scrollbar track jumps back up."""
    g = long_body_report_game()
    try:
        add_wounds(g)
        before = moves(g)
        g.keys("h", delay=1.5)
        g.wait_for("Close")
        assert "Bandages stop bleeding" not in g.screen(), g.screen()
        first = g.screen().splitlines()[1]
        # The wheel turns three lines per notch in a text view.
        g.type(f"\x1b[<65;{popup_width(g) // 2 + 1};7M", delay=1)
        assert g.screen().splitlines()[1] != first, \
            "the wheel must turn the report\n" + g.screen()
        sx, sy = scrollbar_column(g)
        rows = g.screen().splitlines()
        bottom = next(y for y in range(sy + 1, len(rows)) if rows[y][sx:sx + 1] == "v")
        g.click(sx, bottom - 1)
        g.wait_for("Bandages stop bleeding")
        # A track cell above the slider returns to the first part of the report.
        g.click(sx, sy + 2)
        g.wait_gone("Bandages stop bleeding")
        cx, cy = find_in(g, "Close")
        g.click(cx, cy)
        g.wait_gone("Close")
        assert moves(g) == before, "the body report must not spend moves"
    finally:
        g.close()


def test_character_info_stat_click_selects_without_changes(g):
    """Clicking a stat row shows its info. Clicking it again runs the same code
    as Enter, which without stats-through-kills changes nothing."""
    g.resize(140, 45)
    arena(g)
    before = (moves(g), stat(g, "str"), stat(g, "per"))
    try:
        open_info(g)
        g.wait_for("Strength affects")
        px, py = find_in(g, "Perception:", x_max=26, y_min=2, y_max=7)
        g.click(px, py)
        g.wait_for("Perception is the most important")
        # Same row again: the Enter action, a no-op while the upgrade option is off.
        g.click(px, py)
        g.settle_screen()
        assert "Perception is the most important" in g.screen(), g.screen()
    finally:
        close_info(g)
        g.resize(140, 45)
    assert (moves(g), stat(g, "str"), stat(g, "per")) == before, \
        "stat clicks must neither spend moves nor change stats"


def test_character_info_skill_click_toggles_training(g):
    """The first click on a skill selects it; clicking the same skill again
    toggles training exactly like Enter."""
    g.resize(140, 45)
    arena(g)
    before = moves(g)
    was_training = training(g, "melee")
    try:
        # Opening Lua from this screen dismisses it, so query only after closing.
        for clicks, expected in ((1, was_training), (2, not was_training), (2, was_training)):
            open_info(g)
            sx, sy = find_in(g, "SKILLS", x_max=26, y_min=17, y_max=19)
            g.click(sx, sy)
            for _ in range(clicks):
                mx, my = find_in(g, "Melee:", x_max=26, y_min=19)
                g.click(mx, my)
                assert "Melee:" in g.screen(), g.screen()
            close_info(g)
            assert training(g, "melee") is expected, \
                "one click selects a skill; a second click toggles its training"
        assert moves(g) == before, "the info screen must not spend moves"
    finally:
        close_info(g)


def test_character_info_trait_scrollbar_jump_and_resize_click(g):
    """The traits scrollbar track jumps, and a click after a resize hits the row
    at its new drawn position."""
    g.resize(100, 30)
    arena(g)
    before = moves(g)
    set_traits(g)
    try:
        open_info(g)
        tx, ty = find_in(g, "TRAITS", x_max=55, y_min=17, y_max=19)
        g.click(tx, ty)
        g.wait_for("Fleet")
        # The traits scrollbar column is the one before the panel's right border.
        first_info = g.screen()
        g.click(52, 25)
        assert g.screen() != first_info, "the track click must move the selection"
        g.resize(120, 38)
        g.settle_screen()
        # After the resize the list is drawn at new positions; click a trait
        # that only became visible through the track jump.
        gx, gy = find_in(g, "Good Hearing", x_max=53, y_min=19)
        g.click(gx, gy)
        g.wait_for("Good Hearing:")
        assert moves(g) == before, "the info screen must not spend moves"
    finally:
        close_info(g)
        clear_traits(g)
    arena(g)
    g.resize(140, 45)


TESTS = [test_body_report_close_button, test_body_report_wheel_and_scrollbar,
         test_character_info_stat_click_selects_without_changes,
         test_character_info_skill_click_toggles_training,
         test_character_info_trait_scrollbar_jump_and_resize_click]
