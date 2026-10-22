"""Shared Lua helpers and Python wrappers for e2e tests and the playtest harness."""
import re
import time

from tmux_game import Game, start_new_game  # noqa: F401  (re-exported for convenience)


def wait_until(check, timeout=30, poll=0.3):
    """Poll a predicate until it holds; returns False on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return True
        time.sleep(poll)
    return False

HELPERS = (
    "M=gapi.get_map() function here(dx,dy) local c=gapi.get_avatar():get_pos_ms() return TripointBubMs.new(c.x+dx,c.y+dy,c.z) end "
    # Far enough that a parked zombie does not wander back, but the ring must stay inside the
    # loaded map: an unbounded offset eventually parks a creature out of bounds, and its idle
    # sounds then trip a game assertion.
    "PARKED=0 function park(cr) local p for k=1,180 do PARKED=PARKED+1 "
    "p=here(45+PARKED%15,45+(PARKED//15)%12) "
    "if not gapi.get_creature_at(p) then cr:set_pos_ms(p) return end end "
    "cr:set_pos_ms(p) end "
    "function arena() local k=0 for dx=-13,13 do for dy=-13,13 do local p=here(dx,dy) "
    "if math.abs(dx)<=4 and math.abs(dy)<=4 then M:set_ter_at(p, TerId.new('t_floor'):int_id()) end "
    "M:set_furn_at(p, FurnId.new('f_null'):int_id()) M:clear_items_at(p) "
    "local cr=gapi.get_creature_at(p) if cr and not cr:is_avatar() then park(cr) end end end out('ok') end "
    "function units(it) if it:is_stackable() then return it.charges end return 1 end "
    "function count_at(dx,dy,id) local n=0 for _,it in pairs(M:get_items_at(here(dx,dy))) do "
    "if it:get_type():str()==id then n=n+units(it) end end out(n) end "
    "function carried(id) local n=0 for _,it in ipairs(gapi.get_avatar():all_items(false)) do "
    "if it:get_type():str()==id then n=n+units(it) end end out(n) end "
    "function spawn(dx,dy,id,n,furn) local p=here(dx,dy) if furn then M:set_furn_at(p, FurnId.new(furn):int_id()) end "
    "for i=1,n do M:create_item_at(p, ItypeId.new(id), -1) end out('ok') end "
    "function give(id,n) for i=1,n do gapi.get_avatar():create_item(ItypeId.new(id), -1) end out('ok') end "
    "function pos() local p=gapi.get_avatar():abs_pos() out(p.x,p.y,p.z) end"
)


def arena(g):
    assert g.lua("arena()") == ["ok"]


def exploration_arena(g):
    """Open routes to unseen ground without rolled creatures blocking auto-exploration."""
    settle(g)
    assert g.lua("for dx=-30,30 do for dy=-30,30 do local p=here(dx,dy) "
                 "if dx==0 or dy==0 then M:set_ter_at(p, TerId.new('t_floor'):int_id()) "
                 "M:set_furn_at(p, FurnId.new('f_null'):int_id()) end "
                 "local cr=gapi.get_creature_at(p) "
                 "if cr and not cr:is_avatar() then park(cr) end end end out('ok')") == ["ok"]
    settle(g)


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


def empty_inventory(g):
    """Strip random equipment and trait-dependent morale before item interaction fixtures."""
    assert g.lua("local a=gapi.get_avatar() a:clear_bionics() a:clear_mutations() "
                 "a:clear_morale() a:drop_all_items() a:clear_morale() "
                 "a:set_mutation(MutationBranchId.new('DEBUG_STORAGE')) out('ok')") == ["ok"]


def settle(g):
    # Let queued moves play out so the sidebar and map are current.
    g.keys("x", delay=0.6)


def choose_menu_entry(g, label):
    """Click one menu row.

    The message log and the sidebar repeat menu wording ("open the…", "Wield", "Debug…"), so
    only text inside a bordered row counts: the characters between the nearest `│` left of the
    match and the next `│` after it must be the row's hotkey prefix, not prose.
    """
    screen = g.screen()
    pattern = re.compile(r"(?<!\w)" + re.escape(label) + r"(?!\w)", re.IGNORECASE)
    rows = []
    for y, line in enumerate(screen.splitlines()):
        for match in pattern.finditer(line):
            left = line.rfind("│", 0, match.start())
            right = line.find("│", match.end())
            if left < 0 or right < 0 or len(line[left + 1:match.start()]) > 6:
                continue
            rows.append((match.start(), y))
    assert len(rows) == 1, f"expected one menu row for {label!r}:\n{screen}"
    g.click(*rows[0])


def save_and_quit(g):
    """Quit to the title screen. Modern leaves Save and Quit unbound, so pick the menu row."""
    g.keys("Escape", delay=0.8)
    choose_menu_entry(g, "Save and Quit")
    g.keys("y", "Enter", delay=1)


def action_menu(g, category, action):
    g.keys("Enter", delay=0.8)
    choose_menu_entry(g, category + "…")
    choose_menu_entry(g, action)


def open_crafting(g):
    g.keys("i", delay=0.8)
    g.keys("F5", delay=1.5)
