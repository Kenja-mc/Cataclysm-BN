#!/usr/bin/env python3
"""End-to-end checks for the overhaul, played through the real curses binary in tmux."""
import sys
import time
import traceback

from tmux_game import Game, start_new_game

HELPERS = (
    "M=gapi.get_map() function here(dx,dy) local c=gapi.get_avatar():get_pos_ms() return TripointBubMs.new(c.x+dx,c.y+dy,c.z) end "
    "function arena() for dx=-13,13 do for dy=-13,13 do local p=here(dx,dy) "
    "if math.abs(dx)<=4 and math.abs(dy)<=4 then M:set_ter_at(p, TerId.new('t_floor'):int_id()) end "
    "M:set_furn_at(p, FurnId.new('f_null'):int_id()) M:clear_items_at(p) "
    "local cr=gapi.get_creature_at(p) if cr and not cr:is_avatar() then cr:set_pos_ms(here(30,30)) end end end out('ok') end "
    "function count_at(dx,dy,id) local n=0 for _,it in pairs(M:get_items_at(here(dx,dy))) do "
    "if it:get_type():str()==id then n=n+1 end end out(n) end "
    "function carried(id) local n=0 for _,it in ipairs(gapi.get_avatar():all_items(false)) do "
    "if it:get_type():str()==id then n=n+1 end end out(n) end "
    "function spawn(dx,dy,id,n,furn) local p=here(dx,dy) if furn then M:set_furn_at(p, FurnId.new(furn):int_id()) end "
    "for i=1,n do M:create_item_at(p, ItypeId.new(id), -1) end out('ok') end "
    "function give(id,n) for i=1,n do gapi.get_avatar():create_item(ItypeId.new(id), -1) end out('ok') end "
    "function pos() local p=gapi.get_avatar():abs_pos() out(p.x,p.y,p.z) end"
)


def arena(g):
    assert g.lua("arena()") == ["ok"]


def bub_pos(g):
    return tuple(int(v) for v in g.lua("pos()")[0].split(","))


def count_at(g, dx, dy, item):
    return int(g.lua(f"count_at({dx},{dy},'{item}')")[0])


def count_carried(g, item):
    return int(g.lua(f"carried('{item}')")[0])


def spawn(g, dx, dy, item, n=1, furn=None):
    furn = f"'{furn}'" if furn else "nil"
    assert g.lua(f"spawn({dx},{dy},'{item}',{n},{furn})") == ["ok"]


def give(g, item, n=1):
    assert g.lua(f"give('{item}',{n})") == ["ok"]


def settle(g):
    # Let queued moves play out so the sidebar and map are current.
    g.keys("x", delay=0.6)


def test_controls_strip(g):
    s = g.screen()
    for hint in ("wasd move", "qezc diag", "Q stash", "Z sort pile"):
        assert hint in s, f"missing {hint!r} in sidebar"


def test_wasd_movement(g):
    arena(g)
    steps = {"d": (1, 0), "a": (-1, 0), "s": (0, 1), "w": (0, -1),
             "e": (1, -1), "z": (-1, 1), "c": (1, 1), "q": (-1, -1)}
    for key, (dx, dy) in steps.items():
        before = bub_pos(g)
        g.keys(key, delay=0.8)
        after = bub_pos(g)
        assert after == (before[0] + dx, before[1] + dy, before[2]), f"{key}: {before} -> {after}"


def test_wait_keeps_position(g):
    before = bub_pos(g)
    g.keys("x", delay=0.8)
    assert bub_pos(g) == before


def test_quick_stack(g):
    arena(g)
    spawn(g, 2, 0, "usb_drive", furn="f_rack")
    give(g, "usb_drive", 3)
    give(g, "plastic_six_dice", 1)
    assert count_carried(g, "usb_drive") == 3
    g.keys("Q", delay=1.5)
    settle(g)
    assert count_at(g, 2, 0, "usb_drive") == 4, "drives should join the rack"
    assert count_carried(g, "usb_drive") == 0
    assert count_carried(g, "plastic_six_dice") == 1, "nothing nearby holds dice, so they stay"
    assert "Stashed 3 items into 1 spot" in g.screen()


def test_sort_pile(g):
    arena(g)
    spawn(g, 3, 0, "usb_drive", furn="f_rack")
    spawn(g, -3, 0, "flyer", furn="f_rack")
    spawn(g, 0, 0, "usb_drive", 2)
    spawn(g, 0, 0, "character_sheet", 1)
    spawn(g, 0, 0, "plastic_six_dice", 1)
    g.keys("Z", delay=1.5)
    settle(g)
    assert count_at(g, 3, 0, "usb_drive") == 3, "same item goes to the same shelf"
    assert count_at(g, -3, 0, "character_sheet") == 1, "books follow books"
    assert count_at(g, 0, 0, "plastic_six_dice") == 1, "unmatched items stay in the pile"


def test_rounded_frames(g):
    g.keys("i", delay=1)
    s = g.screen()
    g.keys("Escape", delay=0.6)
    assert "╭" in s and "╯" in s, "inventory window should have rounded corners"


TESTS = [test_controls_strip, test_wasd_movement, test_wait_keeps_position,
         test_quick_stack, test_sort_pile, test_rounded_frames]


def main():
    keep = "--keep" in sys.argv
    g = Game()
    failures = 0
    try:
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)
        for test in TESTS:
            started = time.time()
            try:
                test(g)
                print(f"PASS {test.__name__} ({time.time() - started:.1f}s)")
            except Exception:
                failures += 1
                print(f"FAIL {test.__name__}")
                traceback.print_exc()
                print(g.screen())
                g.keys("Escape", delay=0.5)
    finally:
        if not keep:
            g.close()
    print(f"{len(TESTS) - failures}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
