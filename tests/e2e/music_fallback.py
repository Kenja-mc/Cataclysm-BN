import json
import shutil
import tempfile
from pathlib import Path

from fixtures import shared_game
from helpers import HELPERS, arena, settle, wait_until
from tmux_game import ROOT


def install_title_only_soundpack(userdir):
    pack = Path(userdir) / "sound" / "title-only"
    pack.mkdir(parents=True)
    (pack / "soundpack.txt").write_text("NAME: title-only\nVIEW: Title Only\n")
    (pack / "soundset.json").write_text("[]\n")
    (pack / "musicset.json").write_text(json.dumps([{
        "type": "playlist",
        "playlists": [{
            "id": "title",
            "shuffle": True,
            "files": [{"file": "music.ogg", "volume": 100}],
        }],
    }]))
    shutil.copyfile(ROOT / "data" / "sound" / "Basic" / "menu_move.ogg", pack / "music.ogg")


def resolution(game):
    settle(game)
    return game.lua("out(gapi.music_context()) out(gapi.music_playlist())")


def clear_hostiles(game):
    assert game.lua("for _,c in ipairs(gapi.get_all_creatures()) do "
                    "if c:is_monster() then park(c) end end out('ok')") == ["ok"]


def test_missing_context_playlist_falls_back_to_title(_g):
    userdir = tempfile.mkdtemp(prefix="bn-e2e-music-fallback-")
    install_title_only_soundpack(userdir)
    with shared_game("bn-e2e-music-fallback",
                     options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false",
                              "SOUND_ENABLED": "true", "MUSIC_ENABLED": "true",
                              "SOUNDPACKS": "title-only", "DYNAMIC_MUSIC": "true"},
                     userdir=userdir, define=HELPERS) as game:
        arena(game)
        clear_hostiles(game)
        assert wait_until(lambda: resolution(game)[0] != "danger", timeout=60), \
            "the baseline should settle outside danger:\n" + game.screen()

        assert game.lua("FALLBACK_MON=gapi.place_monster_at("
                        "MonsterTypeId.new('mon_zombie'),here(2,0)) "
                        "out(FALLBACK_MON ~= nil)") == ["true"]
        assert wait_until(lambda: resolution(game) == ["danger", "title"], timeout=15), \
            "a pack without a danger playlist must resolve danger to title:\n" + game.screen()
        observed = resolution(game)
        assert observed == ["danger", "title"], \
            f"danger playlist should resolve to title, got {observed!r}:\n" + game.screen()

        assert game.lua("park(FALLBACK_MON) out('ok')") == ["ok"]


TESTS = [
    test_missing_context_playlist_falls_back_to_title,
]
