import re
from helpers import HELPERS, action_menu, arena, settle
from tmux_game import Game, start_new_game

TRADER = ("TRADER=M:place_npc(here(2,0),'farmer') "
          "TRADER:create_item(ItypeId.new('jerky'), -1) out('ok')")


def their_row(g, label):
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
        assert g.lua("for _,n in ipairs(gapi.get_all_npcs()) do park(n) end out('ok')") == ["ok"]
        assert g.lua(TRADER) == ["ok"]
        settle(g)
        ownership_query = (
            "carried('jerky') local n=0 for _,it in ipairs(TRADER:all_items(false)) do "
            "if it:get_type():str()=='jerky' then n=n+units(it) end end out(n)")
        before = g.lua(ownership_query)

        action_menu(g, "Interact", "Chat with NPC")
        g.wait_for("Talk to ")
        g.keys("t", delay=0.5)
        g.wait_for("Let's trade")
        reply = re.search(r"│ (\d) [^\n]*Let's trade", g.screen()) or re.search(r"│ (\d) A daring trader", g.screen())
        assert reply, g.screen()
        g.keys(reply.group(1), delay=0.5)
        g.wait_for("Inventory:")
        assert "Credit" in g.screen(), \
            "the farmer must trade at prices, not exchange freely\n" + g.screen()

        jerky = their_row(g, "jerky")
        g.click(*jerky)
        g.click(*jerky)
        g.wait_for("Debt")
        assert "Inventory:" in g.screen(), \
            "a row click must not close or confirm the trade\n" + g.screen()
        g.click(*jerky)
        g.wait_gone("Debt")

        g.keys("Escape", delay=1.0)
        g.wait_gone("Inventory:")
        assert g.lua(ownership_query) == before, "cancelled row clicks must not transfer either side's jerky"
    finally:
        g.close()


TESTS = [test_trade_clicks_pair_and_never_confirm_the_deal]
