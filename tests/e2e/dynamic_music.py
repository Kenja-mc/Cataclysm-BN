from fixtures import shared_game
from helpers import HELPERS, arena, settle, wait_until


def context(game):
    settle(game)
    return game.lua("out(gapi.music_context())")[0]


def clear_hostiles(game):
    assert game.lua("for _,c in ipairs(gapi.get_all_creatures()) do "
                    "if c:is_monster() then park(c) end end out('ok')") == ["ok"]


def test_dynamic_music_danger_enters_and_clears(_g):
    with shared_game("bn-e2e-dynamic-music",
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false",
                              "DYNAMIC_MUSIC": "true"},
                     define=HELPERS) as game:
        arena(game)
        clear_hostiles(game)
        assert wait_until(lambda: context(game) != "danger", timeout=60), \
            "the baseline should settle outside danger:\n" + game.screen()
        baseline = context(game)
        assert baseline in {"explore", "night", "shelter"}, \
            f"unexpected baseline context {baseline!r}:\n" + game.screen()

        assert game.lua("DANGER_MON=gapi.place_monster_at("
                        "MonsterTypeId.new('mon_zombie'),here(2,0)) "
                        "out(DANGER_MON ~= nil)") == ["true"]
        assert wait_until(lambda: context(game) == "danger", timeout=15), \
            "a hostile in view should enter danger immediately:\n" + game.screen()

        assert game.lua("park(DANGER_MON) out('ok')") == ["ok"]
        assert context(game) == "danger", \
            "danger cleared before the hysteresis delay:\n" + game.screen()

        assert wait_until(lambda: context(game) == baseline, timeout=60), \
            "music should return to the baseline playlist after danger clears:\n" + game.screen()


def test_dynamic_music_single_playlist_option(_g):
    with shared_game("bn-e2e-dynamic-music-off",
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false",
                              "DYNAMIC_MUSIC": "false"},
                     define=HELPERS) as game:
        arena(game)
        clear_hostiles(game)
        assert wait_until(lambda: context(game) == "title", timeout=15), \
            "single-playlist mode should request the title playlist:\n" + game.screen()
        assert game.lua("SINGLE_MON=gapi.place_monster_at("
                        "MonsterTypeId.new('mon_zombie'),here(2,0)) "
                        "out(SINGLE_MON ~= nil)") == ["true"]
        for _ in range(3):
            assert context(game) == "title", \
                "single-playlist mode must ignore the game state:\n" + game.screen()
        assert game.lua("park(SINGLE_MON) out('ok')") == ["ok"]


TESTS = [
    test_dynamic_music_danger_enters_and_clears,
    test_dynamic_music_single_playlist_option,
]
