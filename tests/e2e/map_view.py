from contextual_hub import colored_cells
from helpers import HELPERS, action_menu, arena, choose_menu_entry, settle, start_new_game, wait_until
from tmux_game import Game


EDGE_ARROWS = ("\u2192", "\u2197", "\u2198")


EDGE_MAP_COLUMNS = 36


def map_only(g, columns=EDGE_MAP_COLUMNS):
    return "\n".join(line[:columns] for line in g.screen().splitlines())


def zombie_down_a_corridor(name, options):
    edge = Game(name=name, cols=80, rows=24,
                options={"SAFEMODE": "false", "HUD_WINDOWS": "false", **options})
    start_new_game(edge)
    edge.resize(80, 24)
    edge.define_lua(HELPERS + " function corridor() for dx=5,40 do for dy=-1,1 do local p=here(dx,dy) "
                    "M:set_ter_at(p, TerId.new('t_floor'):int_id()) M:set_furn_at(p, FurnId.new('f_null'):int_id()) "
                    "end end gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(30,0)) "
                    "out(gapi.get_monster_at(here(30,0)) ~= nil) end")
    arena(edge)
    assert edge.lua("corridor()") == ["true"], edge.screen()
    settle(edge)
    return edge


def _arrow_cells(edge):
    hits = []
    for y, line in enumerate(edge.screen_colors().splitlines()):
        for x, (ch, state) in enumerate(colored_cells(line)):
            if ch == "\u2192" and x < EDGE_MAP_COLUMNS:
                hits.append((x, y, state["fg"]))
    return hits


def test_enemy_edge_arrows(g):
    edge = zombie_down_a_corridor("bn-e2e-edge", {"SAFEMODEPROXIMITY": "10"})
    try:
        assert wait_until(lambda: any(fg in (33, 93) for _, _, fg in _arrow_cells(edge))), \
            "no yellow east arrow for the off-screen zombie:\n" + edge.screen_colors()
    finally:
        edge.close()


def test_enemy_edge_arrows_off(g):
    edge = zombie_down_a_corridor("bn-e2e-edge-off", {"ENEMY_EDGE_ARROWS": "false"})
    try:
        assert not any(a in map_only(edge) for a in EDGE_ARROWS), edge.screen()
    finally:
        edge.close()


def test_center_view_at_top_level(_g):
    g = Game(name="bn-e2e-center-view", options={"SAFEMODE": "false"})
    try:
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)
        assert g.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() p.z=10 "
                     "gapi.get_map():set_ter_at(p,TerId.new('t_floor'):int_id()) "
                     "gapi.place_player_local_at(p) out(a:get_pos_ms().z)") == ["10"], g.screen()
        action_menu(g, "Look", "Center View")
        assert g.lua("out(gapi.get_avatar():get_pos_ms().z)") == ["10"], g.screen()
        g.lua("local a=gapi.get_avatar() local p=a:get_pos_ms() p.z=0 gapi.place_player_local_at(p) out('ok')")
    finally:
        g.close()


def test_examine_empty_floor_describes_it(_g):
    g = Game(name="bn-e2e-examine-floor", options={"SAFEMODE": "false",
             "AUTOSELECT_SINGLE_VALID_TARGET": "false", "CONTROL_SCHEME": "classic"})
    try:
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)
        arena(g)
        g.keys("e", delay=1.0)
        g.wait_for("Examine where?")
        g.keys("l", delay=1.5)
        assert "That is a" in g.screen(), g.screen()
    finally:
        g.close()


def test_vehicle_screen_diagonals(g):
    arena(g)
    from vehicle_box import spawn_vehicle
    spawn_vehicle(g, "bicycle")
    x, y = g.find("@")
    g.click(x, y, button=2)
    if "Interact with the" in g.screen():
        g.keys("Escape", delay=0.3)
        g.wait_gone("Interact with the")
    action_menu(g, "Interact", "Examine Nearby Terrain")
    if "Examine where?" in g.screen():
        g.keys("x", delay=0.2)
    if "Interact with what?" in g.screen() or "Interact with the" in g.screen():
        choose_menu_entry(g, "examine the")
    g.wait_for("Examine vehicle")
    choose_menu_entry(g, "Examine vehicle")
    g.wait_for("Esc-back")
    try:
        start = g.screen()
        g.keys("s", delay=0.2)
        g.settle_screen()
        moved = g.screen()
        assert "Esc-back" in moved and moved != start, "s should move the cursor, not siphon"
        g.keys("e", delay=0.2)
        g.settle_screen()
        diag = g.screen()
        assert "Esc-back" in diag and "new name" not in diag.lower() and diag != moved, "e should move diagonally, not rename"
    finally:
        g.keys("Escape", delay=1)


TESTS = [
    test_enemy_edge_arrows,
    test_enemy_edge_arrows_off,
    test_center_view_at_top_level,
    test_examine_empty_floor_describes_it,
    test_vehicle_screen_diagonals,
]
