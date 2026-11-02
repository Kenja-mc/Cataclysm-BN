#!/usr/bin/env python3
"""Verify native HUD overlay placement, full weather facts and the driving dashboard."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

from driving_dashboard_native import build_driving_dashboard_world, case_driving_dashboard
from tiles import ROOT, Session, frame_rgb, require


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
    config = session.curses_userdir / "config" / "panel_options.json"
    config.write_text(json.dumps([{"current_layout_id": "classic", "layouts": []}]))
    observations = {}
    for side in ("right", "left"):
        opts = {**options, "SIDEBAR_POSITION": side}
        off = session.launch(f"{side}-off", opts)
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
    def build_world(self):
        build_driving_dashboard_world(self)


def check_dashboard(session):
    failures, observations = case_driving_dashboard(session)
    require(not failures, "\n".join(failures))
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
        session.close()
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
