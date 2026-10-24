"""Modern scheme mouse support in the status screens: the h body report scrolls
and closes with the mouse, and the @ character screen clicks tabs, rows and
scrollbars like the keyboard does. Classic keeps the plain popups.

The first click on a row only selects it. Clicking the same row again runs the
same action as pressing Enter, so no initially selected row can fire by accident.
"""

from helpers import arena

# Enough harmless mutations for the traits panel to need its scrollbar at a
# small window size. All are unset again after each test.
TRAITS = ("FLEET", "GOODHEARING", "INATTENTIVE", "PARKOUR", "QUICK",
          "OPTIMISTIC", "OUTDOORSMAN", "BIOLUM1", "FEYHEARING",
          "GOODCARDIO", "GOODCARDIO2", "FASTLEARNER")

# Wounds that fill the body report past one small screen.
WOUNDS = (("bleed", "arm_l"), ("bleed", "arm_r"), ("bleed", "leg_l"),
          ("bleed", "leg_r"), ("bite", "torso"), ("bandaged", "head"),
          ("infected", "foot_l"), ("bite", "hand_r"), ("disinfected", "hand_l"))


def moves(g):
    return int(g.lua("out(gapi.get_avatar():get_moves())")[0])


def stat(g, name):
    return int(g.lua(f"out(gapi.get_avatar():get_{name})")[0])


def training(g, skill):
    return g.lua("out(gapi.get_avatar():get_skill_level_object("
                 f"SkillId.new('{skill}')):is_training())")[0] == "true"


def add_wounds(g):
    for effect, part in WOUNDS:
        g.lua(f"gapi.get_avatar():add_effect(EffectTypeId.new('{effect}'), "
              f"TimeDuration.from_minutes(30), BodyPartTypeId.new('{part}'), 1) out('ok')")


def clear_wounds(g):
    for effect, part in WOUNDS:
        g.lua(f"gapi.get_avatar():remove_effect(EffectTypeId.new('{effect}'), "
              f"BodyPartTypeId.new('{part}')) out('ok')")


def set_traits(g):
    for trait in TRAITS:
        g.lua(f"gapi.get_avatar():set_mutation(MutationBranchId.new('{trait}')) out('ok')")


def clear_traits(g):
    for trait in TRAITS:
        g.lua(f"gapi.get_avatar():unset_mutation(MutationBranchId.new('{trait}')) out('ok')")


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
    """Width of the report window, measured from its left border to the
    scrollbar column just inside the right border."""
    columns = g.screen().splitlines()
    sx, _ = scrollbar_column(g)
    left = columns[0].rfind("\u250c", 0, sx)
    assert left >= 0, "no report border left of the scrollbar\n" + g.screen()
    return sx - left + 2


def open_info(g):
    g.keys("@", delay=1.5)
    g.wait_for("STATS")


def close_info(g):
    if "STATS" in g.screen():
        g.keys("Escape", delay=1.0)
        g.wait_gone("STATS")


def test_body_report_close_button(g):
    """A left click on Close leaves the report; no move is spent."""
    g.resize(100, 14)
    arena(g)
    before = moves(g)
    g.keys("h", delay=1.5)
    g.wait_for("Close")
    width = popup_width(g)
    assert width < 100, f"report should size to its text, got {width}\n{g.screen()}"
    cx, cy = find_in(g, "Close")
    assert cy == 12, f"Close belongs on the row above the bottom border\n{g.screen()}"
    g.click(cx, cy)
    g.wait_gone("Close")
    assert "ESCAPE]" not in g.screen(), g.screen()
    assert moves(g) == before, "the body report must not spend moves"
    g.resize(140, 45)


def test_body_report_wheel_and_scrollbar(g):
    """The wheel turns a long report and the scrollbar track jumps back up."""
    g.resize(100, 14)
    arena(g)
    add_wounds(g)
    before = moves(g)
    try:
        g.keys("h", delay=1.5)
        g.wait_for("bleeding")
        assert "Bandages stop bleeding" not in g.screen(), g.screen()
        first = g.screen().splitlines()[1]
        # The wheel turns three lines per notch in a text view.
        g.type(f"\x1b[<65;{popup_width(g) // 2 + 1};7M", delay=1)
        assert g.screen().splitlines()[1] != first, \
            "the wheel must turn the report\n" + g.screen()
        g.wait_for("Bandages stop bleeding")
        # The scrollbar column sits before the right border; the track above
        # its middle jumps the view back towards the first page.
        sx, sy = scrollbar_column(g)
        g.click(sx, sy + 2)
        g.wait_gone("Bandages stop bleeding")
        g.keys("Escape", delay=1.0)
        g.wait_gone("Close")
    finally:
        clear_wounds(g)
    arena(g)
    g.resize(140, 45)
    assert moves(g) == before, "the body report must not spend moves"


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
        assert "upgrade" not in g.screen().lower(), g.screen()
        assert (moves(g), stat(g, "str"), stat(g, "per")) == before, \
            "stat clicks must neither spend moves nor change stats"
    finally:
        close_info(g)
        g.resize(140, 45)
    assert (moves(g), stat(g, "str"), stat(g, "per")) == before


def test_character_info_skill_click_toggles_training(g):
    """The first click on a skill selects it; clicking the same skill again
    toggles training exactly like Enter."""
    g.resize(140, 45)
    arena(g)
    before = moves(g)
    try:
        open_info(g)
        sx, sy = find_in(g, "SKILLS", x_max=26, y_min=17, y_max=19)
        g.click(sx, sy)
        mx, my = find_in(g, "Melee:", x_max=26, y_min=19)
        g.click(mx, my)
        assert training(g, "melee") is False, "a first click must only select"
        assert "Melee:" in g.screen(), g.screen()
        # Selecting scrolls the list, so look the row up again for each click.
        mx, my = find_in(g, "Melee:", x_max=26, y_min=19)
        g.click(mx, my)
        assert training(g, "melee") is True, "the second click must toggle training"
        mx, my = find_in(g, "Melee:", x_max=26, y_min=19)
        g.click(mx, my)
        assert training(g, "melee") is False, "the third click must toggle back"
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
