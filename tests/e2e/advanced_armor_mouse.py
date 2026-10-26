"""Modern scheme mouse support in the two-pane advanced inventory and the armor layers menu.

Clicks only focus panes, select rows or switch tabs: moving items and reordering armor stay
keyboard actions, and the wheel scrolls whichever pane the cursor is over.
"""
from contextlib import contextmanager

from fixtures import shared_game
from helpers import (HELPERS, action_menu, arena, count_at, count_carried, empty_inventory,
                     give, settle, spawn)
from inventory_mouse import row_of

# The armor window spans 125 columns centered on the 140-column terminal: the worn list lives
# in x 9..48, the clicked item's details in x 50..90 and the read-only body part list in
# x 92..131.
LEFT_LIST = (9, 49)
DETAILS = (50, 91)
PART_LIST = (92, 132)


def region(game, lo, hi):
    return "\n".join(line[lo:hi] for line in game.screen().splitlines())


def region_row(game, name, lo, hi):
    for y, line in enumerate(game.screen().splitlines()):
        segment = line[lo:hi]
        if name in segment:
            return lo + segment.index(name), y
    raise AssertionError(f"no row for {name!r} in x {lo}..{hi}:\n{game.screen()}")


def part_heading_rows(game):
    """Body part names in the read-only list: headings start one column in and end with ':'."""
    rows = []
    start = PART_LIST[0] + 1
    for y, line in enumerate(game.screen().splitlines()):
        if len(line) <= start or line[start - 1] != " " or line[start] == " ":
            continue
        label = line[start:PART_LIST[1]].split("  ")[0].strip()
        if label.endswith(":"):
            rows.append((start, y, label[:-1]))
    return rows


def worn_types(game):
    out = game.lua("local a=gapi.get_avatar() local w={} "
                   "for _,it in ipairs(a:get_worn_items()) do w[#w+1]=it:get_type():str() end "
                   "out(table.concat(w,','))")
    assert len(out) == 1, out
    return out[0]


def top_bar(game):
    for y, line in enumerate(game.screen().splitlines()):
        if "Sort Armor" in line and "<<" in line:
            return y, line
    raise AssertionError(f"no armor menu title bar:\n{game.screen()}")


def bar_heading(game):
    _, line = top_bar(game)
    return line[line.index("<<") + 3:line.index(">>")].strip()


def click_tab_arrow(game, arrow):
    y, line = top_bar(game)
    game.click(line.index(arrow), y)


@contextmanager
def advanced_game(name):
    with shared_game(f"bn-e2e-adv-click-{name}", define=HELPERS,
                     setup=lambda g: (empty_inventory(g), arena(g)),
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"}) as game:
        yield game


@contextmanager
def armor_game(name):
    def setup(g):
        empty_inventory(g)
        arena(g)
        assert g.lua("local a=gapi.get_avatar() "
                     "local t=a:create_item(ItypeId.new('tshirt'),-1) assert(a:wear(t,false)) "
                     "local l=a:create_item(ItypeId.new('chainmail_vest'),-1) "
                     "assert(a:wear(l,false)) out('ok')") == ["ok"]
    with shared_game(f"bn-e2e-armor-click-{name}", define=HELPERS, setup=setup,
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"}) as game:
        yield game


def test_click_focuses_inactive_pane_and_selects_row(_game):
    with advanced_game("focus") as game:
        spawn(game, 0, 0, "pipe")
        give(game, "rock", 2)
        game.keys("I", delay=1.5)
        game.wait_for("Name (charges)")
        screen = game.screen()
        assert "rock (2)" in screen and "pipe (1)" in screen, (
            "the default layout must show ground items left and the inventory right:\n" + screen)
        # Defaults put the carried inventory in the right, inactive pane.
        rock_x, rock_y = row_of(game, "rock")
        pipe_x, _ = row_of(game, "pipe")
        assert rock_x > pipe_x, f"expected carried rocks in the right pane:\n{screen}"
        # A concrete destination pane keeps the keyboard move free of prompts.
        game.keys("2", delay=1)
        rock_x, rock_y = row_of(game, "rock")
        game.click(rock_x, rock_y)
        # A second click on the same row must not be taken as a transfer, either.
        game.click(rock_x, rock_y)
        assert "rock (2)" in game.screen(), "clicks must not move items:\n" + game.screen()
        assert game.screen().count("rock") == 1, game.screen()
        # The keyboard transfer acts on the pane and row the click focused.
        game.keys("Enter", delay=1)
        # The move runs as an activity and the menu reopens on the same panes.
        for _ in range(3):
            if "Name (charges)" in game.screen():
                break
            settle(game)
        game.wait_for("Name (charges)")
        game.keys("Escape", delay=1)
        assert "Name (charges)" not in game.screen(), game.screen()
        assert count_carried(game, "rock") == 0, (
            "Enter must move the clicked rock stack, not act on the other pane:\n" + game.screen())
        assert count_at(game, 0, 1, "rock") == 2
        assert count_carried(game, "pipe") == 0 and count_at(game, 0, 0, "pipe") == 1


def test_wheel_scrolls_the_pane_under_cursor(_game):
    with advanced_game("wheel") as game:
        spawn(game, 0, 0, "pipe")
        spawn(game, 0, 0, "rock")
        game.keys("I", delay=1.5)
        game.wait_for("Name (charges)")
        named = [("pipe", row_of(game, "pipe")), ("rock", row_of(game, "rock"))]
        named.sort(key=lambda row: row[1][1])
        (top, top_at), (bottom, bottom_at) = named
        assert top_at[1] < bottom_at[1], game.screen()
        # A wheel notch emits a press only, not a button-release packet.
        game.type(f"\x1b[<65;{bottom_at[0] + 1};{bottom_at[1] + 1}M", delay=1)
        game.keys("Enter", delay=1)
        assert count_carried(game, bottom) == 1, (
            "the wheel must move the selection to the row under it:\n" + game.screen())
        assert count_carried(game, top) == 0
        assert count_at(game, 0, 0, top) == 1 and count_at(game, 0, 0, bottom) == 0
        game.keys("Escape", delay=1)
        assert "Name (charges)" not in game.screen(), game.screen()


def test_armor_layers_clicks_switch_tabs_and_select_rows(_game):
    with armor_game("layers") as game:
        before = worn_types(game)
        action_menu(game, "Inventory", "Re-layer armor/clothing")
        game.wait_for("Sort Armor")
        first = bar_heading(game)
        click_tab_arrow(game, ">>")
        assert bar_heading(game) != first, (
            "clicking the header arrow must switch tabs:\n" + game.screen())
        # Clicking a body part name shows that part: the heading takes the row's own name.
        matched = None
        for x, y, label in part_heading_rows(game):
            previous = bar_heading(game)
            game.click(x, y)
            heading = bar_heading(game)
            if heading != label:
                continue
            if heading == previous:
                # Already showing that part: move away, then prove the row switches back.
                click_tab_arrow(game, ">>")
                assert bar_heading(game) != label, game.screen()
                game.click(x, y)
                heading = bar_heading(game)
            assert heading == label, (
                f"clicking the {label!r} row must select that part:\n" + game.screen())
            matched = label
            break
        assert matched is not None, (
            "no body part row selects its own tab:\n" + game.screen())
        left = region(game, *LEFT_LIST)
        assert "t-shirt" in left and "chainmail vest" in left, (
            f"the {matched} tab must list both worn items:\n" + game.screen())
        # Clicking a worn row shows its details without reordering or taking anything off.
        worn_at = region_row(game, "chainmail vest", *LEFT_LIST)
        game.click(*worn_at)
        details = region(game, *DETAILS)
        assert "chainmail vest" in details and "Coverage:" in details and "[Protection]" in details, (
            "the clicked row's details must show:\n" + details)
        assert "t-shirt" not in details, details
        assert "t-shirt" in region(game, *LEFT_LIST), game.screen()
        # A second click on the same worn row is a no-op: no confirm, removal or reorder.
        game.click(*worn_at)
        assert "Remove selected armor" not in game.screen(), game.screen()
        assert bar_heading(game) == matched, game.screen()
        details = region(game, *DETAILS)
        assert "chainmail vest" in details and "Coverage:" in details and "[Protection]" in details, (
            "the second click must keep showing the same details:\n" + details)
        assert "t-shirt" not in details, details
        assert "t-shirt" in region(game, *LEFT_LIST), game.screen()
        click_tab_arrow(game, ">>")
        assert bar_heading(game) != matched, game.screen()
        game.keys("Escape", delay=1)
        assert "Sort Armor" not in game.screen(), game.screen()
        # The Lua console quits an open menu, so check the worn order after closing it.
        assert worn_types(game) == before, "clicks must not take off or reorder worn items"


TESTS = [test_click_focuses_inactive_pane_and_selects_row,
         test_wheel_scrolls_the_pane_under_cursor,
         test_armor_layers_clicks_switch_tabs_and_select_rows]
