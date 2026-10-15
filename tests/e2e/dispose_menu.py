"""Dispose choices remain usable with holstered weapons; empty Modern filters explain themselves."""
import os
import re

from helpers import HELPERS, arena, count_at, count_carried
from tmux_game import Game, start_new_game


def _fixture(game):
    assert game.lua(
        "local u=gapi.get_avatar() u:clear_bionics() u:clear_mutations() "
        "u:clear_morale() u:drop_all_items() out('ok')"
    ) == ["ok"]
    arena(game)
    assert game.lua(
        "local u=gapi.get_avatar() "
        "local pack=u:create_item(ItypeId.new('backpack'),-1) "
        "local h=u:create_item(ItypeId.new('holster'),-1) "
        "h:add_item_with_id(ItypeId.new('hptjcp'),-1) "
        "local p=u:create_item(ItypeId.new('legpouch_large'),-1) "
        "local b=u:create_item(ItypeId.new('bat'),-1) "
        "out(u:wear(pack,false),u:wear(h,false),u:wear(p,false),u:wield(b))"
    ) == ["true,true,true,true"], game.screen()


def _open_dispose(game, scheme):
    game.keys("h" if scheme == "modern" else "w", delay=1)
    game.wait_for("Wield item")
    game.keys("/", delay=0.6)
    game.type("Hi-Point", delay=0.3)
    game.keys("Enter", delay=1)
    assert "Wield item" in game.screen(), game.screen()
    game.keys("Enter", delay=1)
    game.wait_for("Stop wielding baseball bat?")
    screen = game.screen()
    assert "Store in inventory" in screen, screen
    assert "Drop item" in screen, screen
    assert "< Hi-Point >" not in screen, "inventory filter must not leak into dispose:\n" + screen


def _dispose_with_shown_hotkey(game, choice):
    screen = game.screen()
    match = re.search(r"│\s*(\S)\s+" + re.escape(choice) + r"\s+\|", screen)
    assert match, "dispose choice must have a visible hotkey:\n" + screen
    game.keys(match.group(1), delay=1)
    game.wait_for("Draw Hi-Point Model JCP")
    game.keys("Left", "Enter", delay=1)
    screen = game.screen()
    assert "Draw Hi-Point Model JCP" not in screen, screen
    assert "Stop wielding" not in screen, screen
    assert game.lua(
        "local u=gapi.get_avatar() local w={} for _,it in ipairs(u:all_items(false)) do "
        "if u:is_wielding(it) then w[#w+1]=it:get_type():str() end end out(table.concat(w,','))"
    ) == ["hptjcp"], screen
    stored = choice == "Store in inventory"
    assert count_carried(game, "bat") == int(stored), game.screen()
    assert count_at(game, 0, 0, "bat") == int(not stored), game.screen()


def test_modern_dispose_holstered_weapon_hotkeys(_g):
    game = Game(name=f"bn-e2e-dispose-modern-{os.getpid()}",
                options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        for choice in ("Store in inventory", "Drop item"):
            _fixture(game)
            _open_dispose(game, "modern")
            _dispose_with_shown_hotkey(game, choice)
    finally:
        game.close()


def test_classic_dispose_holstered_weapon_hotkeys(_g):
    game = Game(name=f"bn-e2e-dispose-classic-{os.getpid()}",
                options={"CONTROL_SCHEME": "classic", "SAFEMODE": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        for choice in ("Store in inventory", "Drop item"):
            _fixture(game)
            _open_dispose(game, "classic")
            _dispose_with_shown_hotkey(game, choice)
    finally:
        game.close()


def test_modern_dispose_empty_filter_explains_and_recovers(_g):
    game = Game(name=f"bn-e2e-dispose-filter-{os.getpid()}",
                options={"CONTROL_SCHEME": "modern", "SAFEMODE": "false"})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        _fixture(game)
        _open_dispose(game, "modern")
        game.keys("/", delay=0.6)
        game.type("Hi-Point", delay=0.3)
        game.keys("Enter", delay=1)
        screen = game.screen()
        assert "< Hi-Point >" in screen, screen
        assert "--NO MATCHES--" in screen, "an unmatched filter must not leave an unexplained blank body:\n" + screen
        assert "Store in inventory" not in screen, screen
        assert "Drop item" not in screen, screen
        game.keys("/", "C-u", "Enter", delay=0.6)
        screen = game.screen()
        assert "--NO MATCHES--" not in screen, screen
        assert "Store in inventory" in screen, screen
        assert "Drop item" in screen, screen
        _dispose_with_shown_hotkey(game, "Drop item")
    finally:
        game.close()


TESTS = [test_modern_dispose_holstered_weapon_hotkeys,
         test_classic_dispose_holstered_weapon_hotkeys,
         test_modern_dispose_empty_filter_explains_and_recovers]
