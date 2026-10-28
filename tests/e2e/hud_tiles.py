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
        opts = {**options, "SIDEBAR_POSITION": side}
        off = session.launch(f"{side}-off", opts)
        # Read the terminal size from the capture: TERMINAL_X/Y are physical font cells and the
        # window size has changed before (60-row runs made a hardcoded height lie).
        width, height, _ = frame_rgb(off)
        require(width % 8 == 0 and height % 16 == 0,
                f"{side}: unexpected capture size {width}x{height}")
        cols = width // 8
        origin = 0 if side == "right" else 44 * 8
        edge = origin + (cols - 44) * 8
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
                require((x1, y1) == (edge - 1, height - 1),
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


def mismatched_pixels(before, after, left, top, right, bottom):
    """Pixels that differ inside one rectangle."""
    width, height, off = frame_rgb(before)
    w, h, on = frame_rgb(after)
    require((w, h) == (width, height), "the compared captures differ in size")
    return [(x, y) for y in range(top, bottom) for x in range(left, right)
            if off[3 * (y * width + x):3 * (y * width + x) + 3]
            != on[3 * (y * width + x):3 * (y * width + x) + 3]]


def changed_region(before, after, left, top, right, bottom, message):
    points = mismatched_pixels(before, after, left, top, right, bottom)
    require(points, message)
    return (min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points), max(y for _, y in points))


def capture_parked(session, live, label: str):
    """Capture the live window with the pointer parked over the sidebar."""
    width, height, _ = frame_rgb(live.frame)
    x11 = tiles.X11(session.display)
    try:
        window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
        require(window is not None, f"{label}: game window disappeared")
        x11.focus_local(window, width - 10, height // 2)
        time.sleep(0.5)
        return capture(session.display, window, session.artifacts / f"{label}.png")
    finally:
        x11.close()


def click_cell(x11, window, cell, cell_w, cell_h, delay=0.5):
    """Click the centre of one UI cell in the game window."""
    x11.focus_local(window, cell[0] * cell_w + cell_w // 2,
                    cell[1] * cell_h + cell_h // 2)
    x11.click(1, delay=delay)


def check_dashboard(session):
    """The dashboard renders at 80x25, and its collapse control really collapses and restores.

    Geometry: compare the same fixture with the vehicle window hidden and shown; nothing else
    floats, so the changed rectangle is the dashboard (24 cells text-only, 27 with bundled icons,
    nine rows tall).  Then, in the shown run, click the centre of the title's collapse control:
    the eight rows above the shared bottom border must change (top border, title, six readings),
    the body gone.  Click the collapsed control and require the expanded window's cells to come
    back byte for byte.
    """
    options = {"FONT_WIDTH": "8", "FONT_HEIGHT": "16", "FONT_SIZE": "16",
               "USE_METRIC_SPEEDS": "mph", "HUD_WINDOWS": "true",
               "HUD_WEATHER_BOX": "off", "HUD_COMBAT_BOX": "off",
               "SIDEBAR_POSITION": "right"}
    cols, rows = 80, 25
    map_cells = cols - 44
    cases = (("scale-1-text", 1, "ascii", 24),
             ("scale-2-text", 2, "ascii", 24),
             ("scale-1-icons", 1, "nerd", 27))
    observations = {}
    for label, scale, icons, window_cells in cases:
        # TERMINAL_X/Y count physical font cells, so a scaled run asks for more of them to keep
        # the same 80x25 logical grid.
        base = {**options, "SCALING_FACTOR": str(scale), "HUD_ICONS": icons,
                "TERMINAL_X": str(cols * scale), "TERMINAL_Y": str(rows * scale)}
        with session.running_game(f"{label}-off", {**base, "HUD_VEHICLE_BOX": "off"}) as live:
            off = capture_parked(session, live, f"dashboard-{label}-off")
        width, height, _ = frame_rgb(off)
        require(width % cols == 0 and height % rows == 0,
                f"{label}: unexpected terminal size: {width}x{height}")
        cell_w, cell_h = width // cols, height // rows
        require((cell_w, cell_h) == (8 * scale, 16 * scale),
                f"{label}: scaling was not applied as configured: "
                f"{cell_w}x{cell_h} px cells at {scale}x")
        map_right = map_cells * cell_w
        with session.running_game(label, {**base, "HUD_VEHICLE_BOX": "bottom_right"}) as live:
            x11 = tiles.X11(session.display)
            try:
                window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
                require(window is not None, f"{label}: game window disappeared")

                def shot(name: str):
                    x11.focus_local(window, width - 10, height // 2)
                    time.sleep(0.5)
                    return capture(session.display, window,
                                   session.artifacts / f"dashboard-{label}-{name}.png")

                expanded = shot("expanded")
                # The control spans three cells ending two cells before the right border; click
                # its middle cell so a one-cell rounding difference still lands inside it.
                click_cell(x11, window, (map_cells - 4, rows - 8), cell_w, cell_h)
                collapsed = shot("collapsed")
                click_cell(x11, window, (map_cells - 4, rows - 2), cell_w, cell_h)
                restored = shot("restored")
            finally:
                x11.close()

        # 1. Geometry: hidden vs shown is exactly the bottom-right dashboard rectangle.
        x0, y0, x1, y1 = changed_region(
            off, expanded, 0, 0, map_right, height,
            f"{label}: the dashboard window did not change the map")
        require(x1 // cell_w == map_cells - 1, f"{label}: window does not reach the map edge")
        require(x0 // cell_w == map_cells - window_cells,
                f"{label}: wrong window width: {(x1 - x0 + 1) / cell_w:.1f} cells")
        require((y0 // cell_h, y1 // cell_h) == (rows - 9, rows - 1),
                f"{label}: wrong window rows: {(y0 // cell_h, y1 // cell_h)}")

        # 2. Collapse: the old top border, title and six body rows change; the shared bottom
        #    border does not.  A click that only raised the window would change no body row.
        x0, y0, x1, y1 = changed_region(
            expanded, collapsed, 0, 0, map_right, height,
            f"{label}: the collapse click did not change the dashboard body")
        require((y0 // cell_h, y1 // cell_h) == (rows - 9, rows - 2),
                f"{label}: collapse must hide the six-reading body: "
                f"{(y0 // cell_h, y1 // cell_h)}")
        require((x0 // cell_w, x1 // cell_w) == (map_cells - window_cells, map_cells - 1),
                f"{label}: wrong collapsed window columns")

        # 3. Restore: the same eight rows change again, and the window is byte-identical to the
        #    expanded frame (same time, same map, pointer parked).
        x0, y0, x1, y1 = changed_region(
            collapsed, restored, 0, 0, map_right, height,
            f"{label}: the expand click did not restore the dashboard body")
        require((y0 // cell_h, y1 // cell_h) == (rows - 9, rows - 2),
                f"{label}: restore must bring the six-reading body back")
        require(not mismatched_pixels(expanded, restored,
                                      (map_cells - window_cells) * cell_w,
                                      (rows - 9) * cell_h, map_right, height),
                f"{label}: the restored window does not match the expanded window")

        observations[label] = {
            "icons": icons, "cells": [cols, rows], "cell_pixels": [cell_w, cell_h],
            "window_cells": [window_cells, 9],
            "off": str(session.artifacts / f"dashboard-{label}-off.png"),
            "expanded": str(session.artifacts / f"dashboard-{label}-expanded.png"),
            "collapsed": str(session.artifacts / f"dashboard-{label}-collapsed.png"),
            "restored": str(session.artifacts / f"dashboard-{label}-restored.png"),
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
