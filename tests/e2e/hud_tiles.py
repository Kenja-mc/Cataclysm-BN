#!/usr/bin/env python3
"""Verify native HUD overlay placement, full weather facts and the driving dashboard."""
import argparse
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import tiles
import tmux_game
from helpers import HELPERS, arena, settle
from tiles import ROOT, Session, capture, frame_rgb, require
from tmux_game import Game, start_new_game
from vehicle_box import spawn_vehicle


def changed_bounds(before, after, left, right):
    width, height, off = frame_rgb(before)
    w, h, on = frame_rgb(after)
    require((w, h) == (width, height), "HUD option changed the screen dimensions")
    points = [(x, y) for y in range(height) for x in range(left, right)
              if off[3 * (y * width + x):3 * (y * width + x) + 3]
              != on[3 * (y * width + x):3 * (y * width + x) + 3]]
    require(points, "enabled HUD was overwritten by the terrain refresh")
    return (min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points), max(y for _, y in points))


def check_hud(session):
    options = {"FONT_WIDTH": "8", "FONT_HEIGHT": "16", "FONT_SIZE": "16",
               "SCALING_FACTOR": "1", "HUD_ICONS": "ascii", "HUD_COMBAT_BOX": "off",
               "HUD_VEHICLE_BOX": "off", "HUD_WEATHER_BOX": "off"}
    # The classic layout reserves 44 font cells, regardless of the map's tile dimensions.
    config = session.curses_userdir / "config" / "panel_options.json"
    config.write_text(json.dumps([{"current_layout_id": "classic", "layouts": []}]))
    observations = {}
    for side in ("right", "left"):
        origin = 0 if side == "right" else 44 * 8
        edge = origin + (132 - 44) * 8
        opts = {**options, "SIDEBAR_POSITION": side}
        off = session.launch(f"{side}-off", opts)
        for corner in ("top_left", "bottom_right"):
            label = f"{side}-{corner}"
            on = session.launch(label, {**opts, "HUD_WEATHER_BOX": corner})
            x0, y0, x1, y1 = changed_bounds(off, on, origin, edge)
            # HUD uses UI cells, not map tiles.
            require(y1 - y0 + 1 == 6 * 16,
                    f"{label}: weather facts were clipped or laid out in map tiles: {(x0, y0, x1, y1)}")
            if corner == "top_left":
                require((x0, y0) == (origin, 0), f"{label}: wrong terrain origin: {(x0, y0)}")
            else:
                require((x1, y1) == (edge - 1, 60 * 16 - 1),
                        f"{label}: wrong bottom-right position: {(x1, y1)}")
            require(x1 - x0 < (edge - origin) // 2 + 32, f"{label}: HUD covered too much map")
            observations[label] = [x0, y0, x1, y1]
    return observations


class DashboardSession(Session):
    """A saved world with the avatar seated in a spawned car, so the vehicle window has readings."""

    def build_world(self):
        tmux_game.ROOT = self.root
        game = Game(name="bn-hud-dashboard-fixture", userdir=self.curses_userdir,
                    options={"SAFEMODE": "false", "INITIAL_TIME": "12"})
        try:
            start_new_game(game)
            game.define_lua(HELPERS)
            arena(game)
            spawn_vehicle(game)
            settle(game)
            require(game.lua("out(gdebug.save_game())") == ["true"],
                    "saving the dashboard fixture failed:\n" + game.screen())
        finally:
            subprocess.run(["tmux", "kill-session", "-t", game.name], check=False,
                           stderr=subprocess.DEVNULL)
        saves = [p for p in (self.curses_userdir / "save").iterdir() if p.is_dir()]
        require(len(saves) == 1, f"expected one saved world, found {saves}")
        self.world = saves[0].name
        hide_floating_windows(self.curses_userdir, self.world)


# Every floating window except the vehicle one is hidden for the dashboard check.  Otherwise the
# log and the movement window re-place when the vehicle window shrinks, and their pixels would be
# indistinguishable from the dashboard's.
HIDDEN_WINDOWS = ("weather", "combat", "needs", "limbs", "stats", "movement",
                  "weight", "compass", "log")


def hide_floating_windows(userdir: Path, world: str) -> None:
    saves = list((userdir / "save" / world).glob("*.sav"))
    require(len(saves) == 1, f"expected one game save, found {saves}")
    save = saves[0]
    text = save.read_text()
    header, sep, body = text.partition("\n")
    require(header.startswith("# version ") and sep, f"unexpected save header: {header!r}")
    data = json.loads(body)
    player = data.get("player")
    require(isinstance(player, dict), "the game save has no player object")
    player["hud_windows"] = [{"id": window_id, "collapsed": False, "visible": False}
                             for window_id in HIDDEN_WINDOWS]
    save.write_text(header + "\n" + json.dumps(data, separators=(",", ":"),
                                               allow_nan=False) + "\n")


def changed_region(before, after, left, top, right, bottom):
    """Bounding box of changed pixels inside one rectangle, which must not be empty."""
    width, height, off = frame_rgb(before)
    w, h, on = frame_rgb(after)
    require((w, h) == (width, height), "the collapse click changed the screen dimensions")
    points = [(x, y) for y in range(top, bottom) for x in range(left, right)
              if off[3 * (y * width + x):3 * (y * width + x) + 3]
              != on[3 * (y * width + x):3 * (y * width + x) + 3]]
    require(points, "clicking the collapse control did not redraw the dashboard")
    return (min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points), max(y for _, y in points))


def check_dashboard(session):
    """The dashboard draws in the map at 80x25, at both scaling factors and both icon widths.

    Only the vehicle window is floating in this fixture, so every changed map pixel belongs to
    it.  Its cells are known from the provider's text: 24 wide text-only and 27 with the bundled
    icon font, by 9 tall (six readings, title, two borders).  Clicking the collapse control must
    redraw the map where the old top border, title and body were; the bottom border is shared with
    the collapsed window and does not change, so 8 cell rows change.  A built-in reading has four
    body rows (its title carries the speed), so it could not pass.  The fixture never drags the
    window: a placed window would collapse from its saved top-left, moving the bottom border and
    changing the expected span.
    """
    options = {"FONT_WIDTH": "8", "FONT_HEIGHT": "16", "FONT_SIZE": "16",
               "USE_METRIC_SPEEDS": "mph", "HUD_WINDOWS": "true",
               "HUD_VEHICLE_BOX": "bottom_right", "HUD_WEATHER_BOX": "off",
               "HUD_COMBAT_BOX": "off", "SIDEBAR_POSITION": "right"}
    cols, rows = 80, 25
    map_cells = cols - 44
    cases = (("scale-1-text", 1, "ascii", 24),
             ("scale-2-text", 2, "ascii", 24),
             ("scale-1-icons", 1, "nerd", 27))
    observations = {}
    for label, scale, icons, window_cells in cases:
        # TERMINAL_X/Y count physical font cells, so a scaled run asks for more of them to keep
        # the same 80x25 logical grid.
        launch = {**options, "SCALING_FACTOR": str(scale), "HUD_ICONS": icons,
                  "TERMINAL_X": str(cols * scale), "TERMINAL_Y": str(rows * scale)}
        with session.running_game(label, launch) as live:
            expanded = live.frame
            width, height, _ = frame_rgb(expanded)
            require(width % cols == 0 and height % rows == 0,
                    f"{label}: unexpected terminal size: {width}x{height}")
            cell_w, cell_h = width // cols, height // rows
            x11 = tiles.X11(session.display)
            try:
                window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
                require(window is not None, f"{label}: game window disappeared before the click")
                # The control sits on the title row, five cells in from the map's right edge.
                x11.focus_local(window, (map_cells - 5) * cell_w + cell_w // 2,
                                (rows - 9 + 1) * cell_h + cell_h // 2)
                x11.click(1, delay=1.2)
                time.sleep(1.2)
                collapsed = capture(session.display, window,
                                    session.artifacts / f"dashboard-collapsed-{label}.png")
            finally:
                x11.close()
        # Nothing else floats, so read the whole map: the window's true left edge must show.
        x0, y0, x1, y1 = changed_region(expanded, collapsed, 0, 0, map_cells * cell_w, height)
        require(x1 // cell_w == map_cells - 1, f"{label}: window does not reach the map edge")
        require(x0 // cell_w == map_cells - window_cells,
                f"{label}: wrong window width: {(x1 - x0 + 1) / cell_w:.1f} cells")
        require(y1 // cell_h == rows - 2, f"{label}: bottom border must stay put")
        require(y0 // cell_h == rows - 9, f"{label}: wrong window top: {y0 // cell_h}")
        require(y1 // cell_h - y0 // cell_h + 1 == 8,
                f"{label}: collapsing must hide the six-reading body")
        observations[label] = {
            "icons": icons, "cells": [cols, rows], "cell_pixels": [cell_w, cell_h],
            "window_cells": [x1 // cell_w - x0 // cell_w + 1, y1 // cell_h - y0 // cell_h + 1],
            "bounds": [x0, y0, x1, y1],
            "expanded": str(expanded),
            "collapsed": str(session.artifacts / f"dashboard-collapsed-{label}.png"),
        }
    return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--binary")
    parser.add_argument("--vk-icd")
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--out", default="/tmp/bn-hud-tiles-proof")
    args = parser.parse_args()
    artifacts = Path(args.out)
    artifacts.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="bn-hud-tiles-"))
    session = Session(args, work, artifacts)
    dashboard = DashboardSession(args, work / "dashboard", artifacts / "dashboard")
    dashboard.artifacts.mkdir(parents=True, exist_ok=True)
    try:
        session.start()
        session.build_world()
        observations = check_hud(session)
        # Close the first session before the second replaces TMUX_TMPDIR, so each tmux server is
        # stopped from its own environment.  The saved world stays on disk.
        session.close()
        # A second fixture starts with the avatar in a spawned car; its world is separate so the
        # weather captures keep their clear map.
        dashboard.start()
        dashboard.build_world()
        observations["dashboard"] = check_dashboard(dashboard)
        (artifacts / "result.json").write_text(json.dumps(observations, indent=2))
        print(f"PASS tiles HUD corners, weather facts and driving dashboard: {artifacts}")
    finally:
        dashboard.close()
        session.close()
        shutil.rmtree(work)


if __name__ == "__main__":
    main()
