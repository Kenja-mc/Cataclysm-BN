"""Safe mode repeats a short hint while it blocks, and the wait menu offers Sleep and 6 hours."""
import os
import re
import time

from helpers import HELPERS, arena, empty_inventory, give, settle
from tmux_game import Game, start_new_game

# Modern wait-menu choices differ from Classic.
BASE_OPTIONS = {"SHOW_WELCOME": "false", "HUD_WEATHER_BOX": "off", "CONTROL_SCHEME": "modern"}

TIME_OF_DAY = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})\s*([AP]M)")


def minutes_of_day(game):
    """The clock on the sidebar, in minutes since midnight, or None if it is not drawn."""
    found = TIME_OF_DAY.findall(game.screen())
    if len(found) != 1:
        return None
    hour, minute, _second, half = found[0]
    return (int(hour) % 12 + (12 if half == "PM" else 0)) * 60 + int(minute)


def safe_mode_messages(game):
    """(full warning seen, short repeat seen) among the recent log entries."""
    found = game.lua("local t=gapi.get_messages(12); local long,short=0,0 "
                     "for i,v in ipairs(t) do "
                     "if v.text:find('safe mode is on') then long=1 end "
                     "if v.text:find('^Safe mode:') then short=1 end end "
                     "out(long,short)")
    return tuple(int(v) for v in found[0].split(","))


def open_wait_menu(game):
    """Ctrl+X waits; a character carrying an alarm clock is asked about it first."""
    game.keys("C-x", delay=1.0)
    if "What do you want to do?" in game.screen():
        game.keys("W", delay=1.0)
    game.wait_for("Wait for how long?")


def test_safe_mode_repeats_hint_while_movement_is_blocked(_g):
    options = dict(BASE_OPTIONS, SAFEMODE="true", SAFEMODEPROXIMITY="30",
                   SMART_SAFEMODE="false", AUTOSAFEMODE="false")
    game = Game(name=f"bn-e2e-safemode-{os.getpid()}", cols=140, rows=45, options=options)
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        give(game, "diving_watch")
        assert game.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(3,0)); "
                        "out(gapi.get_monster_at(here(3,0)) ~= nil)") == ["true"]
        # A zombie placed from Lua is only noticed when a turn passes, so the first key may still
        # run; keep pausing until the full warning is logged, then block one more action.
        for _ in range(4):
            if safe_mode_messages(game)[0]:
                break
            game.keys("x", delay=1.0)
        warning, repeat_hint = safe_mode_messages(game)
        assert warning and not repeat_hint, "the first blocked action must give the full warning:\n" \
            + game.screen()
        blocked_at = minutes_of_day(game)
        assert blocked_at is not None, game.screen()
        game.keys("w", delay=1.5)
        assert minutes_of_day(game) == blocked_at, "safe mode must keep blocking the move"
        # The hint is drawn while the blocked key is processed, which lands later on a loaded
        # runner than the fixed key delay allows for.
        try:
            game.wait_for("Safe mode:", timeout=20)
        except AssertionError:
            pass
        assert "Safe mode:" in game.screen(), "the repeat hint is not on screen:\n" + game.screen()
        warning, repeat_hint = safe_mode_messages(game)
        assert warning, "the spotted warning is gone:\n" + game.screen()
        assert repeat_hint, "no safe-mode hint after the second blocked key:\n" + game.screen()

        game.keys("'", delay=1.0)
        game.keys("x", delay=1.0)
        assert game.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(4,0)); "
                        "out(gapi.get_monster_at(here(4,0)) ~= nil)") == ["true"]
        game.keys("w", delay=1.5)
        last = game.lua("local t=gapi.get_messages(1); out(t[#t].text)")
        assert last and "safe mode is on" in last[0], (
            "a newly spotted enemy must start a fresh full warning:\n" + game.screen())
    finally:
        game.close()


def test_wait_menu_offers_sleep_and_six_hour_hotkey(_g):
    options = dict(BASE_OPTIONS, SAFEMODE="false")
    game = Game(name=f"bn-e2e-waitsleep-{os.getpid()}", cols=140, rows=45, options=options)
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        empty_inventory(game)
        arena(game)
        give(game, "diving_watch")

        open_wait_menu(game)
        screen = game.screen()
        sleep_lines = [l for l in screen.splitlines() if "Sleep" in l]
        assert sleep_lines, "the wait menu has no Sleep entry:\n" + screen
        assert any("$ Sleep" in l for l in sleep_lines), sleep_lines
        game.keys("$", delay=0)
        game.wait_for("Are you sure you want to sleep?")
        game.keys("Escape", delay=0)
        game.wait_gone("Are you sure you want to sleep?", timeout=10)
        # Isolate the fixture from rolled world state so wildlife or NPC chatter cannot interrupt
        # the six-hour wait (sealed underground arena, monsters banished, avatar deafened).
        assert game.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() "
                        "a:set_pos_ms(TripointBubMs.new(p.x,p.y,p.z-1)) arena() "
                        "a:add_effect(EffectTypeId.new('deaf'), TimeDuration.from_hours(12)) "
                        "for dx=-4,4 do for dy=-4,4 do "
                        "if math.abs(dx)==4 or math.abs(dy)==4 then "
                        "M:set_ter_at(here(dx,dy), TerId.new('t_wall'):int_id()) "
                        "else M:set_ter_at(here(dx,dy), TerId.new('t_floor'):int_id()) end "
                        "M:set_furn_at(here(dx,dy), FurnId.new('f_null'):int_id()) "
                        "M:clear_items_at(here(dx,dy)) end end "
                        "for dx=-13,13 do for dy=-13,13 do "
                        "local m=gapi.get_monster_at(here(dx,dy)) "
                        "if m and not m:is_avatar() then park(m) end end end out('ok')") == ["ok", "ok"], game.screen()
        settle(game)
        # 6 is bound to menu-right in the modern scheme, but must still pick "6 hours".
        # If a 'Stop waiting?' prompt still appears, the test must fail rather than answer it.
        assert "Stop waiting?" not in game.screen(), game.screen()
        # The clock row redraws a moment after the move and the arena edits; wait for it
        # rather than sampling once.
        deadline = time.time() + 10
        before = minutes_of_day(game)
        while before is None and time.time() < deadline:
            time.sleep(0.1)
            before = minutes_of_day(game)
        assert before is not None, game.screen()
        open_wait_menu(game)
        game.keys("6", delay=0)
        # The entry firing closes the menu; the wait itself then runs in a few seconds.
        deadline = time.time() + 20
        while time.time() < deadline and "Wait for how long?" in game.screen():
            time.sleep(1)
        assert "Wait for how long?" not in game.screen(), "6 did nothing:\n" + game.screen()
        deadline = time.time() + 120
        while time.time() < deadline:
            if "Stop waiting?" in game.screen():
                break
            now = minutes_of_day(game)
            if now is not None and now - before >= 5 * 60:
                break
            time.sleep(2)
        now = minutes_of_day(game)
        assert now is not None and now - before >= 5 * 60, (
            f"6 did not wait six hours ({before} -> {now}):\n" + game.screen())
        assert "Stop waiting?" not in game.screen(), "wait was interrupted:\n" + game.screen()
    finally:
        game.close()


def test_classic_wait_and_safe_mode_keep_upstream_interface(_g):
    options = dict(BASE_OPTIONS, CONTROL_SCHEME="classic", SAFEMODE="false",
                   SMART_SAFEMODE="false", AUTOSAFEMODE="false", SAFEMODEPROXIMITY="30")
    game = Game(name=f"bn-e2e-classic-waitsleep-{os.getpid()}", options=options)
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        game.keys("|", delay=1.0)
        if "What do you want to do?" in game.screen():
            game.keys("w", delay=1.0)
        game.wait_for("Wait for how long?")
        assert "$ Sleep" not in game.screen(), "Classic wait entries changed:\n" + game.screen()
        game.keys("Escape", delay=1.0)

        game.keys("!", delay=1.0)
        assert game.lua("gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(3,0)); "
                        "out(gapi.get_monster_at(here(3,0)) ~= nil)") == ["true"]
        game.keys(".", delay=1.5)
        game.keys("k", delay=1.5)
        warning, repeat_hint = safe_mode_messages(game)
        assert warning, "Classic must retain the full safe-mode warning:\n" + game.screen()
        assert not repeat_hint, "Modern short hint leaked into Classic:\n" + game.screen()
    finally:
        game.close()


TESTS = [test_safe_mode_repeats_hint_while_movement_is_blocked,
         test_wait_menu_offers_sleep_and_six_hour_hotkey,
         test_classic_wait_and_safe_mode_keep_upstream_interface]
