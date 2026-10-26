"""Default Smash keys pulp the chosen corpse without moving or damaging the floor."""
from aim_reticle import action_clock
from contextual_hub import contextual_game, contextual_setup, select_tile
from fixtures import shared_game
from helpers import HELPERS, bub_pos, wait_until


def finish_smash(game):
    """Answer the distraction prompt a wandering monster can raise mid-smash."""
    if wait_until(lambda: "Stop smashing?" in game.screen(), 3):
        game.keys("I", delay=0.5)


def pulp_selected_direction(game, key, direction):
    # The default no-revival mod makes zombie corpses ineligible; bears still zombify.
    assert game.lua(
        "M:create_corpse_at(here(1,0),MonsterTypeId.new('mon_bear')) "
        "M:create_corpse_at(here(-1,0),MonsterTypeId.new('mon_bear')) out('ok')") == ["ok"]
    position, clock = bub_pos(game), action_clock(game)
    floor = game.lua("out(M:get_ter_at(here(1,0)):str_id():str())")
    game.keys(key, delay=0.2)
    game.wait_for("Smash where?")
    game.keys(direction, delay=0.2)
    finish_smash(game)
    game.wait_for("thoroughly pulped", timeout=30)
    assert game.lua(
        "local east=M:get_items_at(here(1,0))[1] "
        "local west=M:get_items_at(here(-1,0))[1] "
        "out(east:is_corpse(),east:get_damage()==east:get_max_damage(),west:get_damage()==0)") == [
            "true,true,true"], "only the chosen corpse must be pulped"
    assert game.lua("out(M:get_ter_at(here(1,0)):str_id():str())") == floor, (
        "pulping a corpse must not also smash its floor")
    assert bub_pos(game) == position, "pulping must not walk the avatar"
    assert action_clock(game) > clock, "the shortcut must retain the normal pulping cost"


def test_modern_attack_pulps_the_chosen_corpse(_g):
    with contextual_game("bn-e2e-modern-pulp-key") as game:
        assert game.lua(
            "M:create_corpse_at(here(1,0),MonsterTypeId.new('mon_bear')) "
            "M:create_corpse_at(here(-1,0),MonsterTypeId.new('mon_bear')) out('ok')") == ["ok"]
        position, clock = bub_pos(game), action_clock(game)
        floor = game.lua("out(M:get_ter_at(here(1,0)):str_id():str())")
        select_tile(game, 1, 0)
        game.keys("f", delay=0.4)
        finish_smash(game)
        game.wait_for("thoroughly pulped", timeout=30)
        assert game.lua(
            "local east=M:get_items_at(here(1,0))[1] "
            "local west=M:get_items_at(here(-1,0))[1] "
            "out(east:is_corpse(),east:get_damage()==east:get_max_damage(),west:get_damage()==0)") == [
                "true,true,true"], "only the aimed corpse must be pulped"
        assert game.lua("out(M:get_ter_at(here(1,0)):str_id():str())") == floor, (
            "pulping a corpse must not also smash its floor")
        assert bub_pos(game) == position, "pulping must not walk the avatar"
        assert action_clock(game) > clock, "the attack key must retain the normal pulping cost"


def test_classic_s_still_pulps_the_chosen_corpse(_g):
    with shared_game("bn-e2e-classic-pulp-key", define=HELPERS, setup=contextual_setup,
                     options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false",
                              "AUTOSELECT_SINGLE_VALID_TARGET": "false"}) as game:
        pulp_selected_direction(game, "s", "l")


TESTS = [test_modern_attack_pulps_the_chosen_corpse,
         test_classic_s_still_pulps_the_chosen_corpse]
