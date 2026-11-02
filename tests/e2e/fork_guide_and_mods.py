"""The fork's Hitchhiker's Guide URL and the Limited_Reviving_Zombies mod, as the game shows them.

Opening the guide ends in a browser, which curses cannot draw; `Game` already replaces `xdg-open`
with a no-op, so these games replace it with a recorder and assert the exact URL handed over.
Modern leaves `open_hhg` without a key, so the action menu is the route in, and the item action
menu keeps the per-item page. The revival mod is a mod, not an option, so its world is started
with it in the default mod list, and `no_reviving_zombies` is dropped: that one removes the
`REVIVES` flag the mod limits.
"""
import json
import re
import tempfile
from pathlib import Path

from helpers import HELPERS, choose_menu_entry, give, menu_rows, wait_until
from inventory_mouse import row_of
from options_menu import close_options, open_options
from tmux_game import ROOT, Game, start_new_game

GUIDE_URL = "https://kenja-mc.github.io/Cataclysm-BN/guide"
REVIVAL_MOD = "limited_reviving_zombies"


def default_mods():
    return json.loads((ROOT / "data/mods/default.json").read_text())


def recording_game(name, mods=None):
    """A private game whose browser stub appends every URL it is asked to open."""
    userdir = Path(tempfile.mkdtemp(prefix=f"bn-e2e-{name}-"))
    if mods is not None:
        (userdir / "config").mkdir()
        (userdir / "config/default_mods.json").write_text(json.dumps(mods))
    game = Game(name=f"bn-e2e-{name}", userdir=userdir)
    opened = userdir / "opened_urls.log"
    opener = userdir / "bin/xdg-open"
    opener.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$1\" >> '{opened}'\nexit 0\n")
    opener.chmod(0o755)
    start_new_game(game)
    game.define_lua(HELPERS)
    return game, opened


def opened_urls(path):
    try:
        return path.read_text().splitlines()
    except OSError:
        return []


def wait_for_opened(path, url):
    assert wait_until(lambda: url in opened_urls(path), timeout=15), \
        f"the browser must be handed {url!r}, not {opened_urls(path)!r}"


def wait_for_row(game, label, timeout=15):
    assert wait_until(lambda: menu_rows(game.screen(), label), timeout=timeout), \
        f"no menu row for {label!r}:\n" + game.screen()


def selected_option(game, name, tries=200):
    """Moves the options cursor onto a row, expanding a collapsed group the way a player would."""
    for _ in range(tries):
        screen = game.screen()
        if re.search(r">>\s*" + re.escape(name), screen):
            return screen
        if re.search(r">>\s*\+", next((line for line in screen.splitlines() if ">>" in line), "")):
            game.keys("Right", delay=0.1)
        game.keys("Down", delay=0.05)
    raise AssertionError(f"no options row for {name!r}:\n{game.screen()}")


def test_guide_url_and_menus_come_from_the_fork(_g):
    game, opened = recording_game("fork-guide")
    try:
        game.keys("Enter", delay=1)
        wait_for_row(game, "Open Hitchhiker's Guide")
        choose_menu_entry(game, "Open Hitchhiker's Guide")
        wait_for_opened(opened, GUIDE_URL + "/?t=UNDEAD_PEOPLE")

        give(game, "rock")
        game.keys("i", delay=1.5)
        game.wait_for("rock", timeout=15)
        x, y = row_of(game, "rock")
        game.click(x, y, button=2)
        wait_for_row(game, "Hitchhiker's Guide")
        game.keys("J", delay=1)
        wait_for_opened(opened, GUIDE_URL + "/item/rock?t=UNDEAD_PEOPLE")
        game.keys("Escape", "Escape", delay=0.8)

        open_options(game)
        try:
            tab = next(((line.index("[Interface]") + 2, y) for y, line in
                        enumerate(game.screen().splitlines()) if "[Interface]" in line), None)
            assert tab is not None, game.screen()
            game.click(*tab)
            tooltip = " ".join(line.strip("│ ") for line in
                               selected_option(game, "Hitchhiker's Guide URL").splitlines()[1:5])
            assert "Default:" in tooltip, "the row tooltip names the default:\n" + tooltip
            assert GUIDE_URL in tooltip, "the shipped default is the fork URL:\n" + tooltip
        finally:
            close_options(game)
    finally:
        game.close()


def test_limited_reviving_mod_limits_revival(_g):
    mods = [mod for mod in default_mods() if mod != "no_reviving_zombies"] + [REVIVAL_MOD]
    game, _opened = recording_game("fork-revival-mod", mods)
    try:
        assert game.lua("out(game.mod_runtime['limited_reviving_zombies'] ~= nil)") == ["true"], \
            "the world must load the revival mod"
        assert game.lua("local cfg=game.mod_runtime['limited_reviving_zombies'].cfg "
                        "out(cfg.max_revivals, cfg.hp_ratio[3], cfg.rigor_mins[0])") == \
            ["1,0.25,2"], "the mod's own settings must be live"
        assert game.lua("out(EffectTypeId.new('lrz_rigor'):is_valid())") == ["true"], \
            "the rigor mortis effect must exist"
        assert game.lua(
            "local p=gapi.get_avatar():get_pos_ms() "
            "local m=gapi.place_monster_around(MonsterTypeId.new('mon_zombie_child_scorched'), p, 3) "
            "assert(m ~= nil, 'no free tile for the test zombie') "
            "out(m:has_flag(MonsterFlag.REVIVES), m:has_flag(MonsterFlag.REVIVES_HEALTHY))"
        ) == ["true,false"], "zombies must still rise, but no longer at full strength"
    finally:
        game.close()


TESTS = [test_guide_url_and_menus_come_from_the_fork,
         test_limited_reviving_mod_limits_revival]
