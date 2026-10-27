"""Options menu: key guide footer, reset to default, and Modern mouse support."""
import re
import time

from tmux_game import Game, start_new_game


def open_options(g):
    """Esc opens the main menu; another Escape retries a key the game swallowed mid-action."""
    deadline = time.time() + 15
    while "MAIN MENU" not in g.screen():
        assert time.time() < deadline, "Esc should open the main menu\n" + g.screen()
        g.keys("Escape", delay=0.3)
    for y, line in enumerate(g.screen().splitlines()):
        match = re.search(r"[│ ]Options +│", line)
        if match:
            g.hover(match.start() + 1, y)
            g.click(match.start() + 1, y)
            break
    g.wait_for(" OPTIONS ", timeout=10)


def close_options(g):
    g.keys("Escape", delay=1)
    if "Save" in g.screen():
        g.keys("Escape", delay=1)
    if "MAIN MENU" in g.screen():
        g.keys("Escape", delay=1)


def bool_rows(g):
    """Screen rows that show a True/False option value, with the value's column."""
    rows = []
    for y, line in enumerate(g.screen().splitlines()):
        match = re.search(r"│ (True|False) +│", line)
        if match:
            rows.append((match.start() + 2, y))
    return rows


def value_at(g, y):
    return re.search(r"│ (True|False) +│", g.screen().splitlines()[y]).group(1)


def default_value(g):
    match = re.search(r"Default: (True|False)", g.screen())
    assert match, "the tooltip names the default\n" + g.screen()
    return match.group(1)


def test_options_footer_lists_keys(_g):
    g = Game(name="bn-e2e-options-small", cols=80, rows=25)
    try:
        start_new_game(g)
        open_options(g)
        screen = g.screen()
        for text in ("[r] default", "[R] page default", "[Reset to default]", "[?] keys", "[Esc] done"):
            assert text in screen, f"{text!r} missing from the key guide\n{screen}"
    finally:
        g.close()


def test_options_reset_to_default(g):
    open_options(g)
    try:
        rows = bool_rows(g)
        assert rows, "a True/False option is on the first page\n" + g.screen()
        x, y = rows[0]
        g.hover(x, y)
        assert ">>" in g.screen().splitlines()[y], "hovering selects the row\n" + g.screen()
        default = default_value(g)
        g.keys("d", delay=0.6)
        g.keys("r", delay=0.6)
        assert value_at(g, y) == default, "r restores the default\n" + g.screen()
        g.click(x, y, button=2)
        assert value_at(g, y) != default, "a right click changes the value\n" + g.screen()
        y_button, line = next((n, l) for n, l in enumerate(g.screen().splitlines()) if "[Reset to default]" in l)
        g.click(line.index("[Reset to default]") + 2, y_button)
        assert value_at(g, y) == default, "the footer button restores the default\n" + g.screen()
    finally:
        close_options(g)


def test_options_page_reset_can_be_cancelled(g):
    open_options(g)
    try:
        values = []
        for x, y in bool_rows(g)[:2]:
            g.hover(x, y)
            default = default_value(g)
            if value_at(g, y) == default:
                g.click(x, y)
            values.append((y, default))
        assert len(values) == 2, "two visible settings are needed to exercise page reset"
        g.keys("R", "Escape", delay=0.6)
        assert all(value_at(g, y) != default for y, default in values), g.screen()
        g.keys("R", "y", "Enter", delay=0.6)
        assert all(value_at(g, y) == default for y, default in values), g.screen()
    finally:
        close_options(g)


TESTS = [test_options_footer_lists_keys, test_options_reset_to_default,
         test_options_page_reset_can_be_cancelled]
