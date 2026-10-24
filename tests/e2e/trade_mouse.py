"""A real NPC trade smoke against the modern trade screen's click rules.

A neutral farmer buys and sells at real prices, so the header tag is the
observable: with nothing marked it reads Credit, marking their jerky flips
it to Debt, and unmarking flips it back. Row clicks must only select and
mark - no click closes the screen or confirms the deal; even Enter on an
empty deal just asks for more, and Escape leaves.
"""
from helpers import HELPERS, action_menu, arena, settle
from tmux_game import Game, start_new_game

# A neutral farmer two tiles east, holding one priced snack.  No attitude or
# faction overrides: an ally (NPCATT_WAIT or your_followers) exchanges items
# freely and the header tag never leaves "Exchange".
TRADER = ("TRADER=M:place_npc(here(2,0),'farmer') "
          "TRADER:create_item(ItypeId.new('jerky'), -1) out('ok')")


def their_row(g, label):
    """First cell holding `label` in the left half of the screen, their pane."""
    lines = g.screen().splitlines()
    half = len(lines[0]) // 2
    for y, line in enumerate(lines):
        x = line.find(label)
        if 0 <= x < half:
            return x, y
    raise AssertionError(f"no their-pane row for {label!r}\n" + g.screen())


def test_trade_clicks_pair_and_never_confirm_the_deal(_g):
    g = Game(name="bn-e2e-trade-mouse", options={"SAFEMODE": "false"})
    try:
        start_new_game(g)
        g.define_lua(HELPERS)
        arena(g)
        # Random spawns must not add a second chat target.
        assert g.lua("for _,n in ipairs(gapi.get_all_npcs()) do park(n) end out('ok')") == ["ok"]
        assert g.lua(TRADER) == ["ok"]
        settle(g)

        action_menu(g, "Interact", "Chat with NPC")
        g.wait_for("Let's trade items")
        # The dialogue window is keyboard-driven; the trade response is the
        # farmer's third reply.
        g.keys("Down", "Down", "Enter", delay=0.5)
        g.wait_for("Inventory:")
        assert "Credit" in g.screen(), \
            "the farmer must trade at prices, not exchange freely\n" + g.screen()

        jerky = their_row(g, "jerky")
        # The first click only selects the row; the second marks their jerky.
        g.click(*jerky)
        g.click(*jerky)
        g.wait_for("Debt")
        assert "Inventory:" in g.screen(), \
            "a row click must not close or confirm the trade\n" + g.screen()
        # A third click on the same row unmarks it.
        g.click(*jerky)
        g.wait_gone("Debt")

        # Enter is the deal path, and even it refuses an empty deal.
        g.keys("Enter", delay=0.8)
        g.wait_for("offer me more than that")
        g.keys("Escape", delay=0.5)
        assert "Inventory:" in g.screen(), g.screen()
        g.keys("Escape", delay=1.0)
        g.wait_gone("Inventory:")
    finally:
        g.close()


TESTS = [test_trade_clicks_pair_and_never_confirm_the_deal]
