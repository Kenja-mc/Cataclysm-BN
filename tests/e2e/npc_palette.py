"""Follower command palette: chat menu entry, rule changes that stick, and the NPC_UI option."""
from helpers import HELPERS, arena, settle
from tmux_game import Game, start_new_game

# A new farmer follower, placed within hearing range of the player.
FOLLOWER = ("FOLLOWER=M:place_npc(here(2,0),'farmer') "
            "FOLLOWER:set_attitude(NpcAttitude.NPCATT_WAIT) "
            "FOLLOWER:set_faction_id(FactionId.new('your_followers')) out('ok')")
SECOND_FOLLOWER = ("SECOND=M:place_npc(here(-2,0),'farmer') "
                   "SECOND:set_attitude(NpcAttitude.NPCATT_WAIT) "
                   "SECOND:set_faction_id(FactionId.new('your_followers')) out('ok')")


def open_palette(g):
    g.keys("y", delay=1)
    assert "Follower command palette" in g.screen(), "palette entry missing from chat menu:\n" + g.screen()
    g.keys("P", delay=1)
    assert "Follower commands:" in g.screen(), "palette did not open:\n" + g.screen()
    return g.screen()


def test_follower_palette_changes_the_follower_rules(g):
    """Palette changes are stored in the follower's rules, so they show again when the palette reopens."""
    palette = Game(name="bn-e2e-npc-palette", options={"SAFEMODE": "false"})
    try:
        start_new_game(palette)
        palette.define_lua(HELPERS)
        arena(palette)
        settle(palette)
        # Without a follower the chat menu has no palette entry.
        palette.keys("y", delay=1)
        assert "Follower command palette" not in palette.screen(), palette.screen()
        palette.keys("Escape", delay=0.5)

        assert palette.lua(FOLLOWER) == ["ok"]
        assert palette.lua("FOLLOWER:add_bionic(BionicDataId.new('bio_power_storage')) out('ok')") == ["ok"]
        settle(palette)

        screen = open_palette(palette)
        for label in ("Combat engagement: Close", "Use guns: ON", "Aim rule: When convenient",
                      "CBM reserve: Some (50%)", "CBM recharge: Some (50%)"):
            assert label in screen, "default missing: " + label + "\n" + screen

        palette.keys("e", delay=0.5)
        assert "Combat engagement: Weak" in palette.screen(), palette.screen()
        palette.keys("g", delay=0.5)
        assert "Use guns: OFF" in palette.screen(), palette.screen()
        palette.keys("a", delay=0.5)
        assert "Aim rule: Spray" in palette.screen(), palette.screen()
        palette.keys("c", delay=0.5)
        assert "CBM recharge: Little (25%)" in palette.screen(), palette.screen()
        # Reserve steps All, Most, Some, Little, None, so three steps from Some arrive back at All.
        for label in ("CBM reserve: Little (25%)", "CBM reserve: None", "CBM reserve: All (100%)"):
            palette.keys("r", delay=0.5)
            assert label in palette.screen(), palette.screen()
        palette.keys("d", delay=0.5)

        screen = open_palette(palette)
        for label in ("Combat engagement: Weak", "Use guns: OFF", "Aim rule: Spray",
                      "CBM reserve: All (100%)", "CBM recharge: Little (25%)"):
            assert label in screen, "change did not stick: " + label + "\n" + screen
        palette.keys("d", delay=0.5)

        # A temporary order from the team menu holds the rule; flipping it in the palette takes effect.
        palette.keys("y", delay=1)
        palette.keys("o", delay=1)
        assert "Hold off on pulping zombies for a while" in palette.screen(), palette.screen()
        palette.keys("p", delay=0.5)
        palette.keys("d", delay=0.5)
        screen = open_palette(palette)
        assert "Allow pulp: OFF" in screen, "temporary order missing from palette:\n" + screen
        palette.keys("p", delay=0.5)
        assert "Allow pulp: ON" in palette.screen(), "flip hidden by temporary order:\n" + palette.screen()
        palette.keys("d", delay=0.5)

        # With two followers the palette first asks whose rules to show.
        assert palette.lua(SECOND_FOLLOWER) == ["ok"]
        palette.keys("y", delay=1)
        palette.keys("P", delay=1)
        assert "Whose rules?" in palette.screen(), "two followers must pick one:\n" + palette.screen()
        palette.keys("Escape", delay=0.5)
        assert "Follower commands:" not in palette.screen(), palette.screen()
    finally:
        palette.close()


def test_follower_palette_option_off_keeps_the_old_menu(g):
    """With NPC_UI off the chat menu has no palette entry but keeps the team commands."""
    legacy = Game(name="bn-e2e-npc-palette-off", options={"SAFEMODE": "false", "NPC_UI": "false"})
    try:
        start_new_game(legacy)
        legacy.define_lua(HELPERS)
        arena(legacy)
        assert legacy.lua(FOLLOWER) == ["ok"]
        settle(legacy)
        legacy.keys("y", delay=1)
        screen = legacy.screen()
        assert "Tell everyone on your team to wake up" in screen, "team commands missing:\n" + screen
        assert "Follower command palette" not in screen, screen
    finally:
        legacy.close()


TESTS = [test_follower_palette_changes_the_follower_rules, test_follower_palette_option_off_keeps_the_old_menu]
