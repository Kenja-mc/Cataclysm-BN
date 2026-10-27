"""First-run welcome card, the death-mode choice and the onboarding tips.

These run first on the runner's main game: they read what its first start recorded.
"""
from helpers import arena, settle


def test_welcome_card(g):
    assert getattr(g, "saw_welcome", False), "first new game should show the welcome card"
    card = g.welcome_screen
    assert "Unsupported" not in card and "%" not in card, "the card text must be formatted:\n" + card
    # Modern unbinds many classic keys; the card must name a real key or route for every command.
    assert "(unbound)" not in card and "Unbound" not in card, "the card names an unbound key:\n" + card
    assert "RETURN" not in card and "BACKTAB" not in card, "keys must use readable names:\n" + card


def test_death_mode_choice(g):
    """Caves of Qud style: the first game asks Permadeath or Roleplay; the harness picks Roleplay."""
    import json
    assert getattr(g, "saw_death_choice", False), "welcome should ask how death works"
    opts = {o["name"]: o["value"] for o in json.loads((g.userdir / "config" / "options.json").read_text())}
    assert opts.get("PROMPT_ON_CHARACTER_DEATH") == "true", opts.get("PROMPT_ON_CHARACTER_DEATH")


def test_first_time_tip(g):
    arena(g)
    nightvision = g.lua("out(gapi.get_avatar():has_trait(MutationBranchId.new('DEBUG_NIGHTVISION')))") == ["true"]
    try:
        # The shelter can be very dark even at 08:00. Pin sight, not the rolled weather.
        assert g.lua("TIP_HOSTILE=nil "
                     "gapi.get_avatar():set_mutation(MutationBranchId.new('DEBUG_NIGHTVISION')) "
                     "out('ok')") == ["ok"]
        settle(g)
        assert g.lua("gapi.get_avatar():set_value('tip_seen_hostile','') "
                     "TIP_HOSTILE=gapi.place_monster_at(MonsterTypeId.new('mon_zombie'),here(4,0)) "
                     "out(TIP_HOSTILE ~= nil)") == ["true"]
        settle(g)
        assert g.lua("out(gapi.get_avatar():sees(TIP_HOSTILE:get_pos_ms()))") == ["true"], \
            "the hostile-tip fixture must put its zombie in sight:\n" + g.screen()
        assert "Tip: Something hostile" in g.screen(), g.screen()
        assert g.lua("out(gapi.get_avatar():get_value('tip_seen_hostile'))") == ["1"]
    finally:
        assert g.lua("if TIP_HOSTILE then park(TIP_HOSTILE) TIP_HOSTILE=nil end out('ok')") == ["ok"]
        if not nightvision:
            assert g.lua("gapi.get_avatar():unset_mutation(MutationBranchId.new('DEBUG_NIGHTVISION')) "
                         "out('ok')") == ["ok"]


def test_first_time_tips_stairs_and_save(g):
    """The two onboarding gaps a new player hits: how stairs work and whether progress is safe."""
    arena(g)
    for tip in ("hostile", "hungry", "thirsty", "tired", "hurt", "heavy", "night", "goal"):
        assert g.lua(f"gapi.get_avatar():set_value('tip_seen_{tip}','1') out('ok')") == ["ok"]
    assert g.lua("gapi.get_avatar():set_value('tip_seen_stairs','') "
                 "M:set_ter_at(here(0,0), TerId.new('t_stairs_down'):int_id()) out('ok')") == ["ok"]
    settle(g)
    assert "Tip: You are standing on stairs" in g.screen(), g.screen()
    assert g.lua("out(gapi.get_avatar():get_value('tip_seen_stairs'))") == ["1"]
    assert g.lua("gapi.get_avatar():set_value('tip_seen_save','') out('ok')") == ["ok"]
    for _ in range(8):
        settle(g)
        if "Tip: The game saves for you" in g.screen():
            break
    assert "Tip: The game saves for you" in g.screen(), g.screen()
    assert g.lua("out(gapi.get_avatar():get_value('tip_seen_save'))") == ["1"]
    assert g.lua("M:set_ter_at(here(0,0), TerId.new('t_floor'):int_id()) out('ok')") == ["ok"]


def test_help_opens_with_a_quickstart(_g):
    """The in-game manual must start with the commands a first hour needs, in the player's keys."""
    from fixtures import shared_game
    from helpers import HELPERS

    with shared_game("bn-e2e-quickstart", define=HELPERS, setup=arena,
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"}) as game:
        settle(game)
        game.keys("F1", delay=0.8)
        game.wait_for("Please press one of the following")
        game.keys("a", delay=0.8)
        game.wait_for("FIRST TEN MINUTES")
        screen = game.screen()
        assert "press_" not in screen, "key tags must expand to the bound keys:\n" + screen
        assert "F1 opens these help topics" in screen, "the help key must name itself:\n" + screen
        assert "x waits a turn" in screen, "waiting one turn is the pause key, not the wait menu:\n" + screen
        assert "? shows every key" in screen, "the keybindings key must name itself:\n" + screen
        game.keys("Escape", delay=0.6)
        game.wait_gone("FIRST TEN MINUTES")


TESTS = [
    test_welcome_card,
    test_death_mode_choice,
    test_first_time_tip,
    test_first_time_tips_stairs_and_save,
    test_help_opens_with_a_quickstart,
]
