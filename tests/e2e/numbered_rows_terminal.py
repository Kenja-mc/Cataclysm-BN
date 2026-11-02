import re
from fixtures import shared_game
from helpers import HELPERS, arena, count_carried, empty_inventory, spawn
from pickup_flow import close_and_clean


def _terminal_numbered_option_keeps_count(scheme):
    options = {"CONTROL_SCHEME": scheme, "SAFEMODE": "false",
               "NUMBERED_LIST_ROWS": "true", "NEW_PICKUP_MENU": "false", "PICKUP_POSITION": "left"}
    with shared_game("bn-e2e-terminal-numbered-" + scheme, options=options, define=HELPERS) as g:
        arena(g)
        empty_inventory(g)
        arena(g)
        spawn(g, 0, 0, "rock", 5)
        spawn(g, 0, 0, "stick")
        spawn(g, 0, 0, "pipe")
        rock = g.lua("for _,it in ipairs(M:get_items_at(here(0,0))) do "
                     "if it:get_type():str()=='rock' then out(it:display_name(1)) break end end")[0]
        rock = re.sub(r"</?color[^>]*>", "", rock)
        g.keys("C-g" if scheme == "modern" else "g", delay=0.2)
        g.wait_for("Pick up")
        screen = g.screen()
        line = next((line for line in screen.splitlines() if rock in line[:90]), None)
        assert line is not None, f"no pickup row for the actual stack {rock!r}:\n{screen}"
        hotkey = line[0]
        assert hotkey.isalpha(), f"the rock row has no letter hotkey:\n{screen}"
        g.keys("3", delay=0.3)
        g.keys(hotkey, delay=0.3)
        g.keys("Enter", delay=1.5)
        g.wait_gone("Pick up", timeout=20)
        try:
            assert count_carried(g, "rock") == 3, \
                "terminal digits must remain a quantity even with numbered rows enabled"
            assert count_carried(g, "stick") == count_carried(g, "pipe") == 0
        finally:
            close_and_clean(g)


def test_terminal_numbered_option_keeps_modern_pickup_counts(_g):
    _terminal_numbered_option_keeps_count("modern")


def test_terminal_numbered_option_keeps_classic_pickup_counts(_g):
    _terminal_numbered_option_keeps_count("classic")


TESTS = [test_terminal_numbered_option_keeps_modern_pickup_counts,
         test_terminal_numbered_option_keeps_classic_pickup_counts]
