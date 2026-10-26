"""Modern area pickup: g confirms, local keys act, and the mouse marks rows."""
from helpers import HELPERS, arena, count_carried, empty_inventory, spawn, start_new_game
from inventory_mouse import display_name, row_of, wielded
from tmux_game import Game


def open_pickup(g, *items):
    arena(g)
    empty_inventory(g)
    arena(g)
    names = {item: display_name(g, item) for item in items}
    for item in items:
        spawn(g, 0, 0, item)
    g.keys("G", delay=0.2)
    g.wait_for("Pick up")
    g.wait_for("Weight")
    return names


def close_and_clean(g):
    g.keys("Escape", delay=0.6)
    g.lua("gapi.get_avatar():drop_all_items() out('ok')")
    arena(g)


def test_g_again_picks_up_the_highlighted_item(g):
    open_pickup(g, "rock", "stick")
    g.keys("g", delay=1.5)
    try:
        assert "Weight" not in g.screen(), "g should confirm the area pickup menu\n" + g.screen()
        assert count_carried(g, "rock") + count_carried(g, "stick") == 1, "exactly the highlighted item"
    finally:
        close_and_clean(g)


def test_h_wields_from_pickup(g):
    names = open_pickup(g, "pipe", "rock")
    try:
        x, y = row_of(g, names["pipe"])
        g.hover(x, y)
        g.keys("h", delay=1.5)
        assert wielded(g) == ["pipe"], wielded(g)
    finally:
        close_and_clean(g)


def test_mouse_marks_pickup_rows(g):
    names = open_pickup(g, "rock", "stick")
    rock = names["rock"]
    # Row layout: letter, parent marker, then '-' unmarked or '+' marked, then the name.
    mark = lambda: g.screen().splitlines()[y][2]
    try:
        x, y = row_of(g, rock)
        assert mark() == "-", g.screen()
        g.click(x, y)
        assert mark() == "+", "a left click marks the row\n" + g.screen()
        g.click(x, y)
        assert mark() == "-", "a second click unmarks it\n" + g.screen()
        g.click(x, y, button=2)
        assert "Item action" in g.screen() and "Cancel" in g.screen(), "a right click lists actions\n" + g.screen()
        g.keys("Escape", delay=0.6)
    finally:
        close_and_clean(g)


def test_pickup_context_action_takes_only_that_item(g):
    names = open_pickup(g, "rock", "stick")
    try:
        g.click(*row_of(g, names["stick"]))
        g.click(*row_of(g, names["rock"]), button=2)
        g.keys("Home", "Enter", delay=0.7)
        assert count_carried(g, "rock") == 1
        assert count_carried(g, "stick") == 0
    finally:
        close_and_clean(g)


def test_wheel_selects_pickup_row(g):
    names = open_pickup(g, "rock", "stick")
    try:
        x, y = row_of(g, names["rock"])
        g.hover(x, y)
        g.type(f"\x1b[<65;{x + 1};{y + 1}M", delay=1)
        g.keys("g", delay=1)
        assert count_carried(g, "stick") == 1
        assert count_carried(g, "rock") == 0
    finally:
        close_and_clean(g)


def test_space_confirms_like_g(g):
    open_pickup(g, "rock", "stick")
    g.keys("Space", delay=1.5)
    try:
        assert "Weight" not in g.screen(), "Space should confirm the area pickup menu\n" + g.screen()
        assert count_carried(g, "rock") + count_carried(g, "stick") == 1, "exactly the highlighted item"
    finally:
        close_and_clean(g)


def test_space_picks_marked_row_with_quantity(g):
    arena(g)
    empty_inventory(g)
    arena(g)
    spawn(g, 0, 0, "rock", 5)
    spawn(g, 0, 0, "stick")
    rock = g.lua("local it=gapi.create_item(ItypeId.new('rock'),5) out(it:display_name(1))")[0]
    g.keys("G", delay=0.2)
    g.wait_for("Pick up")
    g.wait_for("Weight")
    g.keys("3", delay=0.3)
    g.click(*row_of(g, rock))
    g.keys("Space", delay=1.5)
    try:
        assert "Weight" not in g.screen(), "Space should confirm after marking a quantity\n" + g.screen()
        assert count_carried(g, "rock") == 3, "the typed quantity must survive Space"
        assert count_carried(g, "stick") == 0
    finally:
        close_and_clean(g)


def test_escape_cancels_pickup_in_modern(g):
    open_pickup(g, "rock")
    g.keys("Right", delay=0.4)
    g.keys("Escape", delay=0.8)
    try:
        assert "Weight" not in g.screen(), "Escape should cancel the area pickup menu\n" + g.screen()
        assert count_carried(g, "rock") == 0
    finally:
        close_and_clean(g)


def test_classic_empty_pickup_confirmation_takes_nothing(_g):
    g = Game(name="bn-e2e-pickup-classic", options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false"})
    try:
        start_new_game(g)
        g.define_lua(HELPERS)
        empty_inventory(g)
        arena(g)
        spawn(g, 0, 0, "rock")
        spawn(g, 0, 0, "stick")
        g.keys("g", delay=1)
        assert "Pick up" in g.screen() and "Weight" in g.screen(), g.screen()
        g.keys("Enter", delay=1)
        assert count_carried(g, "rock") == count_carried(g, "stick") == 0
    finally:
        g.close()


def test_classic_space_still_cancels_pickup(_g):
    g = Game(name="bn-e2e-pickup-classic-space", options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false"})
    try:
        start_new_game(g)
        g.define_lua(HELPERS)
        empty_inventory(g)
        arena(g)
        spawn(g, 0, 0, "rock")
        spawn(g, 0, 0, "stick")
        g.keys("g", delay=1)
        assert "Pick up" in g.screen() and "Weight" in g.screen(), g.screen()
        g.keys("Right", delay=0.4)
        g.keys("Space", delay=1)
        assert "Weight" not in g.screen(), "Classic Space must still cancel the pickup menu\n" + g.screen()
        assert count_carried(g, "rock") == count_carried(g, "stick") == 0
    finally:
        g.close()


TESTS = [test_g_again_picks_up_the_highlighted_item, test_h_wields_from_pickup,
         test_mouse_marks_pickup_rows, test_pickup_context_action_takes_only_that_item,
         test_classic_empty_pickup_confirmation_takes_nothing, test_wheel_selects_pickup_row,
         test_space_confirms_like_g, test_space_picks_marked_row_with_quantity,
         test_escape_cancels_pickup_in_modern, test_classic_space_still_cancels_pickup]
