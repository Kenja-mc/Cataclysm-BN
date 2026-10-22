"""First-run welcome card, the death-mode choice and the onboarding tips.

These run first on the runner's main game: they read what its first start recorded.
"""
from helpers import arena, settle


def test_welcome_card(g):
    assert getattr(g, "saw_welcome", False), "first new game should show the welcome card"
    card = g.welcome_screen
    assert "Unsupported" not in card and "%" not in card, "the card text must be formatted:\n" + card


def test_death_mode_choice(g):
    """Caves of Qud style: the first game asks Permadeath or Roleplay; the harness picks Roleplay."""
    import json
    assert getattr(g, "saw_death_choice", False), "welcome should ask how death works"
    opts = {o["name"]: o["value"] for o in json.loads((g.userdir / "config" / "options.json").read_text())}
    assert opts.get("PROMPT_ON_CHARACTER_DEATH") == "true", opts.get("PROMPT_ON_CHARACTER_DEATH")


def test_first_time_tip(g):
    arena(g)
    g.lua("gapi.get_avatar():set_value('tip_seen_hostile','') out('ok')")
    assert g.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(4,0)) out('ok')") == ["ok"]
    settle(g)
    assert "Tip: Something hostile" in g.screen(), g.screen()
    assert g.lua("out(gapi.get_avatar():get_value('tip_seen_hostile'))") == ["1"]
    g.lua("local m=gapi.get_monster_at(here(4,0)) if m then park(m) end out('ok')")


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


TESTS = [
    test_welcome_card,
    test_death_mode_choice,
    test_first_time_tip,
    test_first_time_tips_stairs_and_save,
]
