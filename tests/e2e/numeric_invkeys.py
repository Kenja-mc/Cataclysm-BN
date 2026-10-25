"""Numeric item shortcuts: Modern Reassign accepts 0-9, a digit selects its item,
letters keep working, Classic still refuses digits."""
from crafting import load_first_save
from fixtures import shared_game
from helpers import HELPERS, arena, count_at, count_carried, empty_inventory, give, save_and_quit
from inventory_mouse import row_of
from tmux_game import Game, start_new_game

MODERN = {"CONTROL_SCHEME": "modern", "SAFEMODE": "false", "AUTO_INV_ASSIGN": "enabled"}

MENU_MARKERS = ("Inventory", "Enter new letter", "Origin:", "to enter/edit command")


def to_game(g):
    """Escape until no menu is on screen; Lua calls must only run in game mode."""
    for _ in range(8):
        s = g.screen()
        if not any(marker in s for marker in MENU_MARKERS):
            return
        g.keys("Escape", delay=0.6)
    raise AssertionError("not back in game\n" + g.screen())


def open_inventory(g):
    g.keys("i", delay=0.4)
    g.wait_for("Inventory", timeout=15)


def fresh_items(g, *items):
    arena(g)
    empty_inventory(g)
    arena(g)
    for item in items:
        give(g, item)


def row_invlet(g, needle):
    """Read the shortcut before the item's optional clothing/status markers."""
    x, y = row_of(g, needle)
    line = g.screen().splitlines()[y]
    prefix = line[line.rfind("│", 0, x) + 1:x].lstrip()
    return prefix[:1]


def reassign(g, needle, key):
    """Open the item menu for the row and type the new shortcut key."""
    open_inventory(g)
    x, y = row_of(g, needle)
    g.click(x, y, button=2)
    g.wait_for("Reassign", timeout=15)
    g.keys("=", delay=0.6)
    g.wait_for("Enter new letter", timeout=15)
    g.keys(key, delay=0.6)
    # A finished reassign returns to the rebuilt inventory list.


def reopen_and_drop(g, key, item):
    """Close the menu, reopen so the cursor rests on the first row, then press the key.

    The key must open that item's item menu; dropping from it proves which item answered.
    Lua runs only after the menus closed.
    """
    to_game(g)
    open_inventory(g)
    g.keys(key, delay=1.0)
    g.wait_for("Reassign", timeout=15)
    g.keys("D", delay=1.5)
    assert count_carried(g, item) == 0, f"pressing {key!r} must open the {item}'s item menu\n" + g.screen()
    assert count_at(g, 0, 0, item) == 1, f"the dropped {item} should lie at the feet\n" + g.screen()


def test_modern_reassign_accepts_digit_and_digit_selects_item(_g):
    with shared_game("bn-e2e-numeric-invkeys", options=MODERN, define=HELPERS) as g:
        fresh_items(g, "pipe", "rock")
        reassign(g, "rock", "1")
        assert row_invlet(g, "rock") == "1", "the rock row must show shortcut 1\n" + g.screen()
        reopen_and_drop(g, "1", "rock")


def test_modern_letter_invlet_still_selects(_g):
    with shared_game("bn-e2e-numeric-invkeys", options=MODERN, define=HELPERS) as g:
        fresh_items(g, "pipe", "rock")
        reassign(g, "pipe", "p")
        assert row_invlet(g, "pipe") == "p", "the pipe row must show shortcut p\n" + g.screen()
        reopen_and_drop(g, "p", "pipe")


def test_modern_digit_survives_restack_and_digits_stay_manual(_g):
    with shared_game("bn-e2e-numeric-invkeys", options=MODERN, define=HELPERS) as g:
        fresh_items(g, "pipe", "rock")
        reassign(g, "rock", "0")
        assert row_invlet(g, "rock") == "0", "the rock row must show shortcut 0\n" + g.screen()
        to_game(g)
        # Adding an item restacks the inventory; the digit must survive it and the
        # auto-assigned shirt shortcut must stay a letter.
        give(g, "tshirt")
        open_inventory(g)
        assert row_invlet(g, "rock") == "0", "restacking must keep the digit shortcut\n" + g.screen()
        shirt_invlet = row_invlet(g, "t-shirt")
        assert shirt_invlet.isalpha(), f"auto assignment must use letters, got {shirt_invlet!r}\n" + g.screen()
        to_game(g)


def test_modern_digit_invlet_survives_save_reload(_g):
    with shared_game("bn-e2e-numeric-invkeys", options=MODERN, define=HELPERS) as g:
        fresh_items(g, "pipe", "rock")
        reassign(g, "rock", "0")
        assert row_invlet(g, "rock") == "0", "the rock row must show shortcut 0\n" + g.screen()
        to_game(g)
        save_and_quit(g)
        load_first_save(g)
        assert not g.dismiss_error_popup(), "reloading the invlet save must not leave an error popup"
        g.define_lua(HELPERS)
        open_inventory(g)
        assert row_invlet(g, "rock") == "0", "the digit shortcut must survive save and reload\n" + g.screen()
        to_game(g)
        open_inventory(g)
        g.keys("0", delay=1.0)
        g.wait_for("Reassign", timeout=15)
        g.keys("D", delay=1.5)
        assert count_carried(g, "rock") == 0, "the digit must open the rock's item menu after reload\n" + g.screen()
        assert count_carried(g, "pipe") == 1, "the pipe must stay carried\n" + g.screen()
        assert count_at(g, 0, 0, "rock") == 1, "the dropped rock should lie at the feet\n" + g.screen()


def test_classic_rejects_digits_but_letters_still_work(_g):
    g = Game(name="bn-e2e-invkeys-classic", options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false"})
    try:
        start_new_game(g)
        g.define_lua(HELPERS)
        fresh_items(g, "pipe", "rock")
        open_inventory(g)
        g.keys("Down", delay=0.4)  # select the rock row under the pipe
        g.keys("Enter", delay=1.0)
        g.wait_for("Reassign", timeout=15)
        g.keys("=", delay=0.6)
        g.wait_for("Enter new letter", timeout=15)
        g.keys("1", delay=0.6)
        assert "Enter new letter" in g.screen(), "classic must refuse a digit and keep asking\n" + g.screen()
        g.keys("r", delay=0.6)
        to_game(g)
        open_inventory(g)
        assert row_invlet(g, "rock") == "r", "the classic letter assignment must stick\n" + g.screen()
        to_game(g)
        open_inventory(g)
        g.keys("r", delay=1.0)
        g.wait_for("Reassign", timeout=15)
        g.keys("d", delay=1.5)
        assert count_carried(g, "rock") == 0, "the letter must still select the rock in classic\n" + g.screen()
        assert count_carried(g, "pipe") == 1, "the pipe must stay carried\n" + g.screen()
        assert count_at(g, 0, 0, "rock") == 1, "the dropped rock should lie at the feet\n" + g.screen()
    finally:
        g.close()


TESTS = [test_modern_reassign_accepts_digit_and_digit_selects_item,
         test_modern_letter_invlet_still_selects,
         test_modern_digit_survives_restack_and_digits_stay_manual,
         test_modern_digit_invlet_survives_save_reload,
         test_classic_rejects_digits_but_letters_still_work]
