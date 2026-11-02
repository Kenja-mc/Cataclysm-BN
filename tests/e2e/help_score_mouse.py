import re

from fixtures import shared_game
from helpers import HELPERS, action_menu, arena, empty_inventory, give, option_value, wait_until


def find_scrollbar(screen):
    lines = screen.splitlines()
    best = None
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char != "^" or y + 1 >= len(lines):
                continue
            below = lines[y + 1]
            if x >= len(below) or below[x] not in "│|":
                continue
            for bottom in range(y + 2, len(lines)):
                row = lines[bottom]
                if x < len(row) and row[x] == "v":
                    if best is None or bottom - y > best[1] - best[0]:
                        best = (y, bottom, x)
                    break
    return best


def row_of(screen, text):
    for y, line in enumerate(screen.splitlines()):
        x = line.find(text)
        if x >= 0:
            return x, y
    raise AssertionError(f"no {text!r} on screen\n{screen}")


def has_row(screen, text):
    try:
        row_of(screen, text)
    except AssertionError:
        return False
    return True


def pane_rows(screen, top, bottom):
    return screen.splitlines()[top + 1:bottom]


def open_help(g):
    g.keys("0" if option_value(g, "CONTROL_SCHEME") == "classic" else "F1", delay=1.0)
    assert g.wait_for("Please press one of the following", timeout=15), g.screen()


def open_scores(g):
    if option_value(g, "CONTROL_SCHEME") == "classic":
        g.keys(")", delay=1.0)
    else:
        action_menu(g, "Info", "View Achievements, Scores, and Kills")
    assert g.wait_for("ACHIEVEMENTS", timeout=15), g.screen()


def leave_screen(g):
    g.keys("Escape", delay=0.8)
    g.settle_screen(minimum=0.4, timeout=3)


def display_name(g, item):
    out = g.lua(
        "for _,it in ipairs(gapi.get_avatar():all_items(false)) do "
        f"if it:get_type():str() == '{item}' then out(it:display_name(1)) end end")
    assert len(out) == 1, out
    return re.sub(r"</?color[^>]*>", "", out[0])


def test_help_topic_opens_by_click(g):
    with shared_game("bn-e2e-help-score-help", define=HELPERS) as game:
        arena(game)
        open_help(game)

        header = row_of(game.screen(), "Please press one of the following")
        game.click(*header)
        assert "survival roguelike" not in game.screen(), \
            "a click on the header text must not open a topic\n" + game.screen()

        x, y = row_of(game.screen(), "Introduction")
        game.click(x, y)
        assert "survival roguelike" not in game.screen(), \
            "one click must only select a topic\n" + game.screen()
        game.double_click(x, y)
        screen = game.screen()
        assert "survival roguelike" in screen, "the double clicked topic should open\n" + screen

        game.keys("Escape", delay=0.8)
        x, y = row_of(game.screen(), "Items overview")
        game.click(x, y)
        assert "Please press one of the following" in game.screen(), \
            "one click must keep the topic list open\n" + game.screen()
        game.double_click(x, y)
        screen = game.screen()
        assert "wide variety of items" in screen, screen
        bar = find_scrollbar(screen)
        assert bar, "the long topic should draw a scrollbar\n" + screen
        top, bottom, bx = bar
        before = pane_rows(screen, top, bottom)
        game.click(bx, bottom - 1)
        screen = game.screen()
        assert " HELP " in screen, "a scrollbar click must keep the topic viewer open\n" + screen
        assert pane_rows(screen, top, bottom) != before, \
            "the scrollbar track must scroll the topic text\n" + screen

        game.keys("Escape", delay=0.8)
        assert "Please press one of the following" in game.screen(), game.screen()
        game.keys("b", delay=0.8)
        assert "Move with" in game.screen(), "the movement hotkey must still open its topic\n" + \
            game.screen()
        game.keys("Escape", delay=0.8)
        leave_screen(game)


def test_help_wheel_moves_cursor_and_confirm_opens(g):
    with shared_game("bn-e2e-help-score-wheel", define=HELPERS) as game:
        arena(game)
        open_help(game)
        x, y = row_of(game.screen(), "Introduction")
        game.type(f"\x1b[<65;{x + 1};{y + 1}M", delay=1)
        game.keys("Enter", delay=0.8)
        assert "Move with" in game.screen(), \
            "the wheel must move the cursor before Enter\n" + game.screen()
        game.keys("Escape", delay=0.6)
        leave_screen(game)


def test_help_click_after_resize_hits_right_columns(g):
    with shared_game("bn-e2e-help-score-resize", define=HELPERS) as game:
        arena(game)
        open_help(game)
        try:
            game.resize(100, 30)
            screen = ""
            def resized_menu():
                nonlocal screen
                screen = game.screen()
                return len(screen.splitlines()) == 30 and has_row(screen, "Items overview")
            assert wait_until(resized_menu, timeout=10), \
                "the resized help menu should redraw both columns\n" + screen
            x, y = row_of(screen, "Items overview")
            game.double_click(x, y)
            screen = game.screen()
            assert "wide variety of items" in screen, \
                "a second-column topic must open by its own label after resize\n" + screen
            assert "Move with" not in screen, \
                "the first-column topic must not open instead\n" + screen
            game.keys("Escape", delay=0.6)
        finally:
            game.resize(140, 45)
        leave_screen(game)


def test_scores_tab_click_and_text_scroll(g):
    with shared_game("bn-e2e-help-score-scores", define=HELPERS) as game:
        arena(game)
        open_scores(game)
        first_tab = game.screen()

        tx, ty = row_of(first_tab, "SCORES")
        game.click(tx, ty)
        screen = game.screen()
        assert screen != first_tab, "clicking the SCORES tab should switch tabs\n" + screen

        game.type(f"\x1b[<65;{tx + 1};{ty + 10}M", delay=1)
        screen = game.screen()
        assert "KILLS" in screen, "the wheel must keep the scores screen open\n" + screen

        bar = find_scrollbar(screen)
        if bar:
            top, bottom, bx = bar
            before = pane_rows(screen, top, bottom)
            game.click(bx, bottom - 1)
            screen = game.screen()
            assert pane_rows(screen, top, bottom) != before, \
                "the scores scrollbar track must scroll the text\n" + screen
        leave_screen(game)


def test_examine_action_click_selects_then_runs(g):
    with shared_game("bn-e2e-help-score-examine", define=HELPERS) as game:
        arena(game)
        empty_inventory(game)
        arena(game)
        give(game, "rock")
        give(game, "pipe")
        rock = display_name(game, "rock")
        pipe = display_name(game, "pipe")

        game.keys("i", delay=1.2)
        x, y = row_of(game.screen(), rock)
        game.click(x, y, button=2)
        screen = game.screen()
        assert "Drop" in screen and "Wield" in screen, \
            "a right click should open the item's action list\n" + screen
        fx, fy = row_of(screen, "Favorite")
        game.click(fx, fy)
        screen = game.screen()
        assert "Favorite" in screen, "the first click must only select, not run\n" + screen
        game.click(fx, fy)
        assert wait_until(lambda: "Drop" not in game.screen(), timeout=10), \
            "the second click on the same row must run the action\n" + game.screen()

        game.keys("Escape", delay=0.8)
        rock = display_name(game, "rock")
        game.keys("i", delay=1.2)
        x, y = row_of(game.screen(), rock)
        game.click(x, y, button=2)
        assert "Unfavorite" in game.screen(), \
            "the favorite action must have toggled the flag\n" + game.screen()
        game.keys("Escape", delay=0.8)
        game.keys("Escape", delay=0.8)

        game.keys("i", delay=1.2)
        x, y = row_of(game.screen(), pipe)
        game.click(x, y, button=2)
        assert "Drop" in game.screen(), game.screen()
        px, py = row_of(game.screen(), "Favorite")
        game.click(px, py)
        assert "Drop" in game.screen(), "the menu must stay open after one click\n" + game.screen()
        game.keys("Enter", delay=0.8)
        assert wait_until(lambda: "Drop" not in game.screen(), timeout=10), \
            "Enter must run the row the click selected\n" + game.screen()
        game.keys("Escape", delay=0.8)
        pipe = display_name(game, "pipe")
        game.keys("i", delay=1.2)
        x, y = row_of(game.screen(), pipe)
        game.click(x, y, button=2)
        assert "Unfavorite" in game.screen(), \
            "Enter must have run the clicked favorite action\n" + game.screen()
        game.keys("Escape", delay=0.8)
        leave_screen(game)


def test_classic_screens_ignore_clicks(g):
    with shared_game("bn-e2e-help-score-classic", define=HELPERS,
                     options={"CONTROL_SCHEME": "classic"}) as game:
        arena(game)
        open_help(game)
        x, y = row_of(game.screen(), "Introduction")
        game.click(x, y)
        screen = game.screen()
        assert "survival roguelike" not in screen, \
            "classic must ignore help menu clicks\n" + screen
        assert "Please press one of the following" in screen, game.screen()
        game.keys("Escape", delay=0.8)

        open_scores(game)
        first_tab = game.screen()
        tx, ty = row_of(first_tab, "SCORES")
        game.click(tx, ty)
        assert game.screen() == first_tab, \
            "classic must ignore scores tab clicks\n" + game.screen()
        leave_screen(game)


TESTS = [test_help_topic_opens_by_click, test_help_wheel_moves_cursor_and_confirm_opens,
         test_help_click_after_resize_hits_right_columns, test_scores_tab_click_and_text_scroll,
         test_examine_action_click_selects_then_runs, test_classic_screens_ignore_clicks]
