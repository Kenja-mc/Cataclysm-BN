"""Shared Lua helpers and Python wrappers for e2e tests and the playtest harness."""
from tmux_game import Game, start_new_game  # noqa: F401  (re-exported for convenience)

HELPERS = (
    "M=gapi.get_map() function here(dx,dy) local c=gapi.get_avatar():get_pos_ms() return TripointBubMs.new(c.x+dx,c.y+dy,c.z) end "
    # Far enough that a parked zombie does not wander back and interrupt a later test's activity.
    "PARKED=0 function park(cr) repeat PARKED=PARKED+1 until not gapi.get_creature_at(here(45+PARKED%15,45+PARKED//15)) "
    "cr:set_pos_ms(here(45+PARKED%15,45+PARKED//15)) end "
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
