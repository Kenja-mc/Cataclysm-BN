
import json
import tempfile
from pathlib import Path

from helpers import HELPERS, Game, arena, start_new_game
from tmux_game import ROOT

TRAITS = {
    "FLEET": ("Fleet-Footed", "You can move more quickly than most"),
    "GOODHEARING": ("Good Hearing", "Your hearing is better than average"),
    "INATTENTIVE": ("Inattentive", "You never paid attention to your surroundings"),
    "PARKOUR": ("Parkour Expert", "You're skilled at clearing obstacles"),
    "QUICK": ("Quick", "You're just generally quick!"),
    "OPTIMISTIC": ("Optimist", "Nothing gets you down!"),
    "OUTDOORSMAN": ("Outdoorsman", "You are accustomed to being exposed to the elements"),
    "BIOLUM1": ("Weak Photophore", "A photophore has grown under the skin of your cheeks"),
    "FEYHEARING": ("Fey Hearing", "You're not sure the shape of your ears is helping you any"),
    "GOODCARDIO": ("Indefatigable", "Whether due to exercise and good diet"),
    "GOODCARDIO2": ("Hyperactive", "Your body's efficiency is like that of a tiny furnace"),
    "FASTLEARNER": ("Fast Learner", "You have a flexible mind"),
}

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
    lines = g.screen().splitlines()
    for y, line in enumerate(lines):
        if y < y_min or (y_max is not None and y > y_max):
            continue
        x = line.find(text)
        if x >= 0 and (x_max is None or x < x_max):
            return x, y
    raise AssertionError(f"no cell for {text!r} in band\n{g.screen()}")


def trait_panel(screen):
    rows = screen.splitlines()
    title_y = next(y for y, row in enumerate(rows) if "TRAITS" in row)
    title_x = rows[title_y].index("TRAITS")
    left = rows[title_y].rfind("│", 0, title_x)
    right = rows[title_y].find("│", title_x)
    assert 0 <= left < right, "no traits panel borders\n" + screen
    bottom = next(y for y in range(title_y + 1, len(rows))
                  if rows[y][left:left + 1] in ("├", "└", "╰"))
    visible = {rows[y][left + 1:right - 1].strip(): (left + 1, y)
               for y in range(title_y + 1, bottom)
               if rows[y][left + 1:right - 1].strip()}
    info_top = next(y for y, row in enumerate(rows) if row.startswith("─") and "┴" in row)
    info = " ".join(" ".join(row.split("│", 1)[0]
                            for row in rows[info_top + 1:title_y - 1]).split())
    return info, visible, (right - 1, title_y + 1, bottom - 1)


def scrollbar_column(g):
    rows = g.screen().splitlines()
    for y, line in enumerate(rows):
        for x, ch in enumerate(line):
            if ch == "^" and any(len(row) > x and row[x] == "v" for row in rows[y + 1:]):
                return x, y
    raise AssertionError("no scrollbar arrows on screen\n" + g.screen())


def popup_width(g):
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
    g = long_body_report_game()
    try:
        add_wounds(g)
        before = moves(g)
        g.keys("h", delay=1.5)
        g.wait_for("Close")
        assert "Bandages stop bleeding" not in g.screen(), g.screen()
        first = g.screen().splitlines()[1]
        g.type(f"\x1b[<65;{popup_width(g) // 2 + 1};7M", delay=1)
        assert g.screen().splitlines()[1] != first, \
            "the wheel must turn the report\n" + g.screen()
        sx, sy = scrollbar_column(g)
        rows = g.screen().splitlines()
        bottom = next(y for y in range(sy + 1, len(rows)) if rows[y][sx:sx + 1] == "v")
        g.click(sx, bottom - 1)
        g.wait_for("Bandages stop bleeding")
        g.click(sx, sy + 2)
        g.wait_gone("Bandages stop bleeding")
        cx, cy = find_in(g, "Close")
        g.click(cx, cy)
        g.wait_gone("Close")
        assert moves(g) == before, "the body report must not spend moves"
    finally:
        g.close()


def test_character_info_stat_click_selects_without_changes(g):
    g.resize(140, 45)
    arena(g)
    before = (moves(g), stat(g, "str"), stat(g, "per"))
    try:
        open_info(g)
        g.wait_for("Strength affects")
        px, py = find_in(g, "Perception:", x_max=26, y_min=2, y_max=7)
        g.click(px, py)
        g.wait_for("Perception is the most important")
        g.click(px, py)
        g.settle_screen()
        assert "Perception is the most important" in g.screen(), g.screen()
    finally:
        close_info(g)
        g.resize(140, 45)
    assert (moves(g), stat(g, "str"), stat(g, "per")) == before, \
        "stat clicks must neither spend moves nor change stats"


def test_character_info_skill_click_toggles_training(g):
    g.resize(140, 45)
    arena(g)
    before = moves(g)
    was_training = training(g, "melee")
    try:
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
    g.resize(100, 30)
    arena(g)
    before = moves(g)
    try:
        set_traits(g)
        open_info(g)
        tx, ty = find_in(g, "TRAITS", x_max=55, y_min=17, y_max=19)
        g.click(tx, ty)
        g.settle_screen()
        first_frame = g.screen()
        first_info, first_rows, (sx, top, bottom) = trait_panel(first_frame)
        assert first_info.partition(":")[0] in first_rows, first_frame
        rows = first_frame.splitlines()
        assert rows[top][sx] == "^" and rows[bottom][sx] == "v", \
            "the overflowing traits list must draw a scrollbar\n" + first_frame
        g.click(sx, bottom - 1)
        jumped_frame = g.screen()
        jumped_info, jumped_rows, _ = trait_panel(jumped_frame)
        assert jumped_info.partition(":")[0] != first_info.partition(":")[0], \
            "the track click must select another trait\n" + jumped_frame
        assert tuple(jumped_rows) != tuple(first_rows), \
            "the track click must move the visible list\n" + jumped_frame
        g.resize(120, 38)
        g.settle_screen()
        resized_frame = g.screen()
        resized_info, visible, _ = trait_panel(resized_frame)
        selected = resized_info.partition(":")[0]
        choices = [(name, description) for name, description in TRAITS.values()
                   if name in visible and name != selected]
        assert choices, "no unselected fixture trait is visible after resize\n" + resized_frame
        name, description = choices[0]
        g.click(*visible[name])
        g.wait_for(name + ":")
        clicked_frame = g.screen()
        clicked_info, _, _ = trait_panel(clicked_frame)
        assert clicked_info.startswith(name + ":"), clicked_frame
        assert description in clicked_info, clicked_frame
        close_info(g)
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
