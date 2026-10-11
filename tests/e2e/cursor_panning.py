"""Cursor-driven edge panning for the main map view.

Single-hover tests: ``Game.hover()`` sends one MOUSE_MOVE event and sleeps 1
second, during which the game generates TIMEOUT events that continue panning
with ``last_cursor_pan_direction``.  With ``EDGE_SCROLL=100`` (Slow) the rate
limiter gates displacement to ~10 Hz, so 1 s of hover ≈ 10–30 pan steps
depending on TIMEOUT rate.  Panning **east** moves the view east (scrollbar
rightward), which moves the player ``@`` left on screen — keeping it within
``find()``'s 95‑column search range.

The shared ``g`` fixture (from run.py) has CURSOR_PANNING off.  Dedicated Game
instances enable it where needed.
"""

import time
from helpers import arena, settle, bub_pos
from tmux_game import Game, start_new_game

_PAN_RATE = "100"  # EDGE_SCROLL=Slow: 100 ms between pan steps


def _right_edge(g):
    """Return a safe column to hover at for eastward panning.

    The player ``@`` is near the centre of the terrain window.  From its screen
    column we approximate the terrain window width, then the right-edge zone
    (1 % + 1 cell from the right boundary).  Returns a column *inside* that
    zone, clamped to avoid the sidebar.
    """
    x, _ = g.find("@")
    width = x * 2                         # approximate terrain window width
    threshold = max( 1, width // 100 + 1 )  # 1 % + 1 cell
    edge = width - 1 - threshold           # first "edge zone" column (relative)
    return min( edge + 1, 128 )


def _sidebar_col(g):
    """Return a screen column guaranteed to be in the right sidebar."""
    x, _ = g.find("@")
    return min( x * 2 + 4, 138 )


def test_cursor_panning_pans(g):
    """With CURSOR_PANNING on, holding at the map edge pans the view."""
    pan = Game( name="bn-e2e-pan-on-2",
                options={"CURSOR_PANNING": "true", "EDGE_SCROLL": _PAN_RATE} )
    try:
        start_new_game( pan )
        arena( pan )
        settle( pan )
        x_before, y_before = pan.find( "@" )
        edge = _right_edge( pan )
        pan.hover( edge, y_before )
        x_after, _ = pan.find( "@" )
        assert x_after != x_before, \
            f"view should have panned east: @ ({x_before}) -> ({x_after})"
        pan.keys( "d", delay=1.5 )
        x_recentre, _ = pan.find( "@" )
        assert abs( x_recentre - x_before ) <= 2, \
            f"view should have re-centred: ({x_before}) -> ({x_recentre})"
    finally:
        pan.close()


def test_cursor_panning_off(g):
    """With CURSOR_PANNING off, holding at the edge does nothing."""
    arena( g )
    settle( g )
    x_before, y_before = g.find( "@" )
    g.hover( _right_edge( g ), y_before )
    x_after, _ = g.find( "@" )
    assert x_after == x_before, \
        f"view should not have panned: @ ({x_before}) -> ({x_after})"


def test_cursor_panning_noturn_hover(g):
    """Hovering at the map edge to pan does not consume the player's turn."""
    pan = Game( name="bn-e2e-pan-noturn-2",
                options={"CURSOR_PANNING": "true", "EDGE_SCROLL": _PAN_RATE} )
    try:
        start_new_game( pan )
        arena( pan )
        settle( pan )
        moves_before = int( pan.lua( "out(gapi.get_avatar().moves)" )[0] )
        y = pan.find( "@" )[1]
        pan.hover( _right_edge( pan ), y )
        moves_after = int( pan.lua( "out(gapi.get_avatar().moves)" )[0] )
        assert moves_after == moves_before, \
            f"moves changed during panning: {moves_before} -> {moves_after}"
    finally:
        pan.close()


def test_cursor_panning_movement_recenter(g):
    """After panning, a turn-consuming movement key recenters the view."""
    pan = Game( name="bn-e2e-pan-recenter-2",
                options={"CURSOR_PANNING": "true", "EDGE_SCROLL": _PAN_RATE} )
    try:
        start_new_game( pan )
        arena( pan )
        settle( pan )
        pos_before = bub_pos( pan )
        x_before, y_before = pan.find( "@" )
        pan.hover( _right_edge( pan ), y_before )
        x_panned, _ = pan.find( "@" )
        assert x_panned != x_before, "view should have panned"
        pan.keys( "d", delay=1.5 )
        pos_after = bub_pos( pan )
        assert pos_after == ( pos_before[0] + 1, pos_before[1], pos_before[2] ), \
            f"player should have moved east: {pos_before} -> {pos_after}"
        x_recentre, _ = pan.find( "@" )
        assert abs( x_recentre - x_before ) <= 2, \
            f"view should have re-centred: ({x_before}) -> ({x_recentre})"
    finally:
        pan.close()


def test_cursor_panning_click_target(g):
    """Click after panning targets the tile at the panned coordinates."""
    pan = Game( name="bn-e2e-pan-click-2",
                options={"CURSOR_PANNING": "true", "EDGE_SCROLL": _PAN_RATE} )
    try:
        start_new_game( pan )
        arena( pan )
        settle( pan )
        assert pan.lua(
            "gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(1,0)) out('ok')"
        ) == ["ok"]
        settle( pan )
        x_player, y_player = pan.find( "@" )
        edge = _right_edge( pan )
        # Pan east: view shifts right, zombie slides *left* on screen.
        pan.hover( edge, y_player )
        x_panned, _ = pan.find( "@" )
        # After n pan steps east, zombie screen pos = centre + (1 - n).
        # Since @ is at centre - n, zombie appears at @_x + 1.
        pan.hover( x_panned + 1, y_player )
        s = pan.screen().lower()
        assert "attack" in s, f"hover over zombie should suggest attack:\n{s}"
        before_hp = int( pan.lua(
            "local m=gapi.get_monster_at(here(1,0)) if m then out(m:get_hp()) "
            "else out(-1) end"
        )[0] )
        pan.click( x_panned + 1, y_player )
        settle( pan )
        after_hp = int( pan.lua(
            "local m=gapi.get_monster_at(here(1,0)) if m then out(m:get_hp()) "
            "else out(-1) end"
        )[0] )
        assert after_hp < before_hp, \
            f"clicking zombie should have damaged it: HP {before_hp} -> {after_hp}"
        pan.lua(
            "local m=gapi.get_monster_at(here(1,0)) if m then park(m) end out('ok')"
        )
    finally:
        pan.close()


def test_cursor_panning_return_center(g):
    """Returning cursor to centre stops panning; direction resets."""
    pan = Game( name="bn-e2e-pan-ret-2",
                options={"CURSOR_PANNING": "true", "EDGE_SCROLL": _PAN_RATE} )
    try:
        start_new_game( pan )
        arena( pan )
        settle( pan )
        x_before, y_before = pan.find( "@" )
        pan.hover( _right_edge( pan ), y_before )
        x_panned, _ = pan.find( "@" )
        assert x_panned != x_before, "view should have panned"
        # Return to centre resets direction.
        pan.hover( x_before, y_before )
        x_after, _ = pan.find( "@" )
        assert x_after == x_panned, \
            "view should stay panned when cursor returns to centre: " \
            f"{x_panned} -> {x_after}"
        pan.keys( "d", delay=1.5 )
        x_recentre, _ = pan.find( "@" )
        assert abs( x_recentre - x_before ) <= 2, \
            f"view should have re-centred: ({x_before}) -> ({x_recentre})"
    finally:
        pan.close()


def test_cursor_panning_sidebar_stop(g):
    """Hovering in the sidebar resets direction and stops panning."""
    pan = Game( name="bn-e2e-pan-sidebar-stop",
                options={"CURSOR_PANNING": "true", "EDGE_SCROLL": _PAN_RATE} )
    try:
        start_new_game( pan )
        arena( pan )
        settle( pan )
        x_before, y_before = pan.find( "@" )
        pan.hover( _right_edge( pan ), y_before )
        x_panned, _ = pan.find( "@" )
        assert x_panned != x_before, "view should have panned"
        # Hover outside terrain window resets direction.
        pan.hover( _sidebar_col( pan ), y_before )
        x_after, _ = pan.find( "@" )
        assert x_after == x_panned, \
            "sidebar hover should stop panning: " \
            f"{x_panned} -> {x_after}"
        pan.keys( "d", delay=1.5 )
        x_recentre, _ = pan.find( "@" )
        assert abs( x_recentre - x_before ) <= 2, \
            f"view should have re-centred: ({x_before}) -> ({x_recentre})"
    finally:
        pan.close()