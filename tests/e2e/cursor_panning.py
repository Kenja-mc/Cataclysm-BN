"""Cursor-driven edge panning for the main map view.

Single-hover tests: ``Game.hover()`` sends one MOUSE_MOVE event and sleeps 1
second, during which the game generates TIMEOUT events that continue panning
with ``last_cursor_pan_direction``.  With ``EDGE_SCROLL=100`` (Slow) the rate
limiter gates displacement to ~10 Hz, so 1 s of hover ≈ 10–30 pan steps
depending on TIMEOUT rate.  Panning **east** moves the view east (scrollbar
rightward), which moves the player ``@`` left on screen — keeping it within
``find()``'s 95-column search range.

The shared ``g`` fixture (from run.py) has CURSOR_PANNING off.  The games here keep
the option on, one per option profile, and each test starts from a recentred view.
"""
from aim_reticle import action_clock
from fixtures import shared_game
from helpers import HELPERS, arena, bub_pos, empty_inventory, settle

_PAN_RATE = "100"  # EDGE_SCROLL=Slow: 100 ms between pan steps
_PAN_OPTIONS = {
    "CURSOR_PANNING": "true", "EDGE_SCROLL": _PAN_RATE, "SAFEMODE": "false",
    "ANIMATIONS": "false", "TURN_DURATION": "0",
}


def _right_edge(g):
    """Hover the right-edge zone, allowing for an odd-width terrain window."""
    x, _ = g.find("@")
    width = x * 2
    # Odd terrain widths put the centre one cell right of half-width.
    return width - 2


def pan_setup(game):
    """A menu recentres the view, so a test never inherits the previous test's pan."""
    game.keys("i", delay=0.8)
    assert "Inventory" in game.screen()
    game.keys("Escape", delay=0.8)
    arena(game)
    settle(game)


def pan_game(name, **options):
    return shared_game(name, define=HELPERS, setup=pan_setup,
                       options={**_PAN_OPTIONS, **options})


def _sidebar_col(g):
    """Return a screen column guaranteed to be in the right sidebar."""
    x, _ = g.find("@")
    return min(x * 2 + 4, 138)


def test_cursor_panning_pans(g):
    """With CURSOR_PANNING on, holding at the map edge pans the view."""
    with pan_game("bn-e2e-pan-on") as pan:
        arena(pan)
        settle(pan)
        x_before, y_before = pan.find("@")
        edge = _right_edge(pan)
        pan.hover(edge, y_before)
        x_after, _ = pan.find("@")
        assert x_after != x_before, \
            f"view should have panned east: @ ({x_before}) -> ({x_after})"


def test_cursor_panning_off(g):
    """With CURSOR_PANNING off, holding at the edge does nothing."""
    arena(g)
    settle(g)
    x_before, y_before = g.find("@")
    g.hover(_right_edge(g), y_before)
    x_after, _ = g.find("@")
    assert x_after == x_before, \
        f"view should not have panned: @ ({x_before}) -> ({x_after})"


def test_cursor_panning_noturn_hover(g):
    """Hovering at the map edge to pan does not consume the player's turn."""
    with pan_game("bn-e2e-pan-noturn") as pan:
        arena(pan)
        settle(pan)
        moves_before = int(pan.lua("out(gapi.get_avatar():get_moves())")[0])
        y = pan.find("@")[1]
        pan.hover(_right_edge(pan), y)
        moves_after = int(pan.lua("out(gapi.get_avatar():get_moves())")[0])
        assert moves_after == moves_before, \
            f"moves consumed while panning: {moves_before} -> {moves_after}"


def test_cursor_panning_movement_recenter(g):
    """After panning, a turn-consuming movement key recenters the view."""
    with pan_game("bn-e2e-pan-recenter") as pan:
        arena(pan)
        settle(pan)
        pos_before = bub_pos(pan)
        x_before, y_before = pan.find("@")
        pan.hover(_right_edge(pan), y_before)
        x_panned, _ = pan.find("@")
        assert x_panned != x_before, "view should have panned"
        pan.keys("d", delay=1.5)
        pos_after = bub_pos(pan)
        assert pos_after == (pos_before[0] + 1, pos_before[1], pos_before[2]), \
            f"player should have moved east: {pos_before} -> {pos_after}"
        x_recentre, _ = pan.find("@")
        assert abs(x_recentre - x_before) <= 2, \
            f"view should have re-centred: ({x_before}) -> ({x_recentre})"


def test_cursor_panning_click_target(g):
    with pan_game("bn-e2e-pan-click", CONTROL_SCHEME="modern", MOUSE_MOVE="false",
                  MOUSE_TILE_SELECTION="true") as pan:
        empty_inventory(pan)
        arena(pan)
        settle(pan)
        assert pan.lua(
            "gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) out('ok')"
        ) == ["ok"]
        before_hp = int(pan.lua(
            "local m=gapi.get_monster_at(here(1,0)) if m then out(m:get_hp()) "
            "else out(-1) end"
        )[0])
        before_pos = bub_pos(pan)
        before_clock = action_clock(pan)
        x_player, y_player = pan.find("@")
        edge = _right_edge(pan)
        # Pan east: view shifts right, zombie slides *left* on screen.
        pan.hover(edge, y_player)
        x_panned, _ = pan.find("@")
        # After n pan steps east, zombie screen pos = centre + (1 - n).
        # Since @ is at centre - n, zombie appears at @_x + 1.
        pan.hover(x_panned + 1, y_player)
        pan.click(x_panned + 1, y_player, button=2)
        assert bub_pos(pan) == before_pos, "selecting after panning must not move the avatar"
        assert action_clock(pan) == before_clock, "selecting after panning must be free"
        after_hp = int(pan.lua(
            "local m=gapi.get_monster_at(here(1,0)) if m then out(m:get_hp()) "
            "else out(-1) end"
        )[0])
        assert after_hp == before_hp, "RMB selects the zombie without attacking it"
        pan.keys("f", delay=1)
        assert action_clock(pan) > before_clock, \
            "f must attack the tile selected at the panned coordinates"
        assert bub_pos(pan) == before_pos, "f must attack the selected world tile without moving"
        pan.lua(
            "local m=gapi.get_monster_at(here(1,0)) if m then park(m) end out('ok')"
        )


def test_cursor_panning_return_center(g):
    """Returning cursor to centre stops panning; direction resets."""
    with pan_game("bn-e2e-pan-return") as pan:
        arena(pan)
        settle(pan)
        x_before, y_before = pan.find("@")
        pan.hover(_right_edge(pan), y_before)
        x_panned, _ = pan.find("@")
        assert x_panned != x_before, "view should have panned"
        # Return to centre resets direction.
        pan.hover(x_before, y_before)
        x_after, _ = pan.find("@")
        assert x_after == x_panned, \
            "view should stay panned when cursor returns to centre: " \
            f"{x_panned} -> {x_after}"
        pan.keys("d", delay=1.5)
        x_recentre, _ = pan.find("@")
        assert abs(x_recentre - x_before) <= 2, \
            f"view should have re-centred: ({x_before}) -> ({x_recentre})"


def test_cursor_panning_sidebar_stop(g):
    """Hovering in the sidebar resets direction and stops panning."""
    with pan_game("bn-e2e-pan-sidebar-stop") as pan:
        arena(pan)
        settle(pan)
        x_before, y_before = pan.find("@")
        sidebar = _sidebar_col(pan)
        pan.hover(_right_edge(pan), y_before)
        x_panned, _ = pan.find("@")
        assert x_panned != x_before, "view should have panned"
        # Hover outside terrain window resets direction.
        pan.hover(sidebar, y_before)
        x_after, _ = pan.find("@")
        assert x_after == x_panned, \
            "sidebar hover should stop panning: " \
            f"{x_panned} -> {x_after}"
        pan.keys("d", delay=1.5)
        x_recentre, _ = pan.find("@")
        assert abs(x_recentre - x_before) <= 2, \
            f"view should have re-centred: ({x_before}) -> ({x_recentre})"


def test_cursor_panning_keyboard_recenter(g):
    """Opening a non-turn menu recentres the view and stops edge scrolling."""
    with pan_game("bn-e2e-pan-keyboard") as pan:
        arena(pan)
        settle(pan)
        x_player, y_player = pan.find("@")
        pan.hover(_right_edge(pan), y_player)
        x_panned, _ = pan.find("@")
        assert x_panned < x_player, (x_player, x_panned)
        pan.keys("i", delay=0.5)
        assert "Inventory" in pan.screen(), pan.screen()
        pan.keys("Escape", delay=0.8)
        assert pan.find("@") == (x_player, y_player), pan.screen()


def test_cursor_panning_disabled_rate(g):
    """The existing Disabled scroll setting stops panning even when its option is enabled."""
    with pan_game("bn-e2e-pan-disabled-rate", EDGE_SCROLL="-1") as pan:
        arena(pan)
        settle(pan)
        original = pan.find("@")
        pan.hover(_right_edge(pan), original[1])
        assert pan.find("@") == original, pan.screen()


TESTS = [
    test_cursor_panning_pans,
    test_cursor_panning_off,
    test_cursor_panning_noturn_hover,
    test_cursor_panning_movement_recenter,
    test_cursor_panning_click_target,
    test_cursor_panning_return_center,
    test_cursor_panning_sidebar_stop,
    test_cursor_panning_keyboard_recenter,
    test_cursor_panning_disabled_rate,
]
