#!/usr/bin/env python3
"""Captures one screenshot per visible fork feature and writes the markdown page that shows them.

    python3 tests/e2e/feature_shots.py [--out docs/fork] [--only hud-modern inventory]

The fixture world is built once with the curses build and its Lua helpers, then every shot starts the
tiles build on a copy of that save under a private Xvfb display, sends the feature's keys and captures
the window.  A shot that fails is reported and skipped, so one broken key sequence does not lose the
rest of the set.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tiles  # noqa: E402
from tiles import (Session, X11, WINDOW_TITLE_PREFIX, DETERMINISTIC_OPTIONS, patch_launch_options,
                   capture)  # noqa: E402
from tmux_game import Game, start_new_game  # noqa: E402
from helpers import HELPERS, arena, give, spawn, settle, save_and_quit  # noqa: E402

# Each key tuple is one chord; successive tuples are separate key presses.
SHOTS = [
    dict(id="hud-modern", title="Modern HUD",
         keys=[], options={"CONTROL_SCHEME": "modern", "HUD_WEATHER_BOX": "top_left",
                           "HUD_COMBAT_BOX": "top_left"},
         body="Weather and time sit above the weapon, style, stance and needs boxes. The sidebar keeps "
              "the limb bars, sound, mood, stats, message log, compass and pixel minimap."),
    dict(id="hud-classic", title="Classic HUD",
         keys=[], options={"CONTROL_SCHEME": "classic", "HUD_WEATHER_BOX": "top_left",
                           "HUD_COMBAT_BOX": "top_left"},
         body="Classic keeps the upstream scheme, and the game follows the classic key list. Menu text and "
              "hints name the classic keys, and `?` still lists everything."),
    dict(id="enter-menu", title="The Enter menu",
         keys=[("Return",)], options={"CONTROL_SCHEME": "modern"},
         body="Enter opens every command group: Items, Interact, Info, Misc, crafting, vehicles and "
              "settings. Modern routes each group here instead of binding a top-row number."),
    dict(id="interact-menu", title="Interact menu: quick stack and sort pile",
         keys=[("Return",), ("2",)], options={"CONTROL_SCHEME": "modern"},
         body="Enter, then Interact, opens this menu. Quick stack moves carried items into nearby storage "
              "that already holds them, and sort pile sorts the player's pile without sorting zones."),
    dict(id="inventory", title="Inventory with item variants",
         keys=[("i",)], options={"CONTROL_SCHEME": "modern"},
         body="One line holds one kind of thing. Rings, novels and other folded families list as a "
              "single entry with a count, and selecting a line opens the item's actions."),
    dict(id="crafting", title="Crafting with the parts chain",
         keys=[("i",), ("F5",)], options={"CONTROL_SCHEME": "modern"},
         body="The crafting menu opens on a tab with recipes to make. The parts chain shows what a "
              "recipe needs, which of those parts the player can produce, and one honest time estimate."),
    dict(id="look", title="Look around and tile selection",
         # RMB selects the tile east of the avatar: 11x24 cells, an 88-cell map with the avatar
         # centered on cell (44, 24), so the tile's center pixel is (45*11+5, 24*24+12).
         keys=[], click=(500, 588, 3), options={"CONTROL_SCHEME": "modern"},
         body="A right click selects and inspects the adjacent tile without spending a turn. The "
              "tile inspector shows what it holds, and Space interacts with the selected tile."),
    dict(id="map", title="Map and minimap",
         keys=[("m",)], options={"CONTROL_SCHEME": "modern"},
         body="The map opens on the local area with the pixel minimap the fork keeps on by default."),
    dict(id="sidebar-options", title="Sidebar options from the Enter menu",
         keys=[("Return",), ("7",), ("9",)], options={"CONTROL_SCHEME": "modern"},
         body="Modern leaves the panel key unbound. Enter, then Misc, then Sidebar Options opens the "
              "editor, where the panels can be moved, hidden and reordered."),
    dict(id="body-panel", title="Body panel and limb details",
         keys=[], options={"CONTROL_SCHEME": "modern"},
         setup="gapi.get_avatar():add_effect(EffectTypeId.new('bleed'), "
               "TimeDuration.from_turns(600), BodyPartTypeId.new('arm_l')) "
               "gapi.get_avatar():add_effect(EffectTypeId.new('bandaged'), "
               "TimeDuration.from_turns(600), BodyPartTypeId.new('leg_r')) out('ok')",
         body="The body panel lists every limb with its own bar and names each wound. Enter, then Info, "
              "then Body status opens the same list with treatment hints."),
]

DOC_HEAD = """# Fork feature screenshots

One capture for each visible change this fork makes. Every image comes from the tiles build of the
current tree, started on a private display with a private user directory.

Regenerate them with:

```sh
python3 tests/e2e/feature_shots.py
```
"""


def build_world(session, scheme="modern", setup=""):
    """Builds one fixture save per control scheme and setup, and returns (user directory, world name).

    The save carries the options it was created with, so a Classic capture needs a Classic fixture.
    A setup snippet runs in the fixture game before the save, for shots that need a state the
    default fixture does not have.
    """
    tiles.tmux_game.ROOT = session.root
    key = f"{scheme}-{hashlib.sha256(setup.encode()).hexdigest()[:6]}" if setup else scheme
    userdir = session.work / f"fixture-{key}"
    game = Game(name=f"bn-shots-fixture-{key}", userdir=userdir,
                options={"SAFEMODE": "false", "INITIAL_TIME": "12", "SHOW_WELCOME": "false",
                         "CONTROL_SCHEME": scheme})
    try:
        start_new_game(game)
        game.define_lua(HELPERS)
        arena(game)
        # Storage that already holds what the player carries, so quick stack has a target.
        spawn(game, 2, 0, "usb_drive", 1, "f_rack")
        spawn(game, 4, 0, "rag", 8, "f_workbench")
        give(game, "usb_drive", 3)
        give(game, "rag", 4)
        give(game, "jewelry_ring", 3)
        give(game, "water_clean", 2)
        if setup:
            assert game.lua(setup) == ["ok"], "fixture setup failed:\n" + game.screen()
        settle(game)
        assert game.lua("out(gdebug.save_game())") == ["true"], \
            "saving the fixture failed:\n" + game.screen()
        # Game.close() removes the private user directory, so read the world name before teardown.
        saves = [p for p in (userdir / "save").iterdir() if p.is_dir()]
        if len(saves) != 1:
            raise SystemExit(f"expected one saved world, found {saves}")
        world = saves[0].name
    finally:
        subprocess.run(["tmux", "kill-session", "-t", game.name], stderr=subprocess.DEVNULL, check=False)
    print(f"fixture {key}: {world}")
    return userdir, world


def launch(session, label, options, run_root, fixture):
    """Starts the tiles build on a copy of the scheme's fixture save and returns the process and window."""
    fixture_dir, world = fixture
    run = run_root / label
    userdir, xdg = run / "userdir", run / "xdg"
    shutil.copytree(fixture_dir / "config", userdir / "config")
    shutil.copytree(fixture_dir / "save", userdir / "save")
    shutil.copytree(userdir / "config", xdg / "cataclysm-bn")
    patch_launch_options(userdir, xdg, {**DETERMINISTIC_OPTIONS, **options})
    for sub in ("home", "cache", "data", "state"):
        (run / sub).mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": os.environ["PATH"], "HOME": str(run / "home"), "XDG_CONFIG_HOME": str(xdg),
        "XDG_CACHE_HOME": str(run / "cache"), "XDG_DATA_HOME": str(run / "data"),
        "XDG_STATE_HOME": str(run / "state"), "DISPLAY": session.display,
        "SDL_VIDEODRIVER": "x11", "SDL_AUDIODRIVER": "dummy",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "VK_DRIVER_FILES": str(session.icd),
    }
    log = (run / "tiles.log").open("w")
    proc = subprocess.Popen([str(session.tiles_binary), "--basepath", f"{session.root}/",
                             "--userdir", f"{userdir}/", "--world", world],
                            cwd=session.root, env=env, stdout=log, stderr=log)
    x11 = None
    try:
        # The caller only receives proc once the world is up, so a failed wait must clean up here.
        tiles.wait_for_frame(session, proc, run, min(session.timeout, 120))
        x11 = X11(session.display)
        window = x11.find_window(WINDOW_TITLE_PREFIX)
        if not window:
            raise RuntimeError(f"game window disappeared (see {run / 'tiles.log'})")
        # There is no window manager, so the keys must be aimed at the game window explicitly.
        x11.focus_local(window, 40, 40)
    except BaseException:
        if x11 is not None:
            x11.close()
        tiles.stop_process(proc)
        log.close()
        raise
    return proc, x11, window, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--binary", help="tiles executable")
    parser.add_argument("--vk-icd", help="software Vulkan ICD manifest")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default=None, help="docs directory for images and the page")
    parser.add_argument("--only", nargs="*", help="capture only these shot ids")
    args = parser.parse_args()

    out = Path(args.out).resolve() if args.out else (Path(args.root).resolve() / "docs/fork")
    images = out / "images" / "features"
    images.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="bn-shots-"))
    session = Session(args, work, work / "artifacts")
    session.artifacts.mkdir(parents=True, exist_ok=True)
    session.start()
    keep = args.only or [shot["id"] for shot in SHOTS]
    made, failed = [], []
    seen_shots = {}
    fixtures = {}
    try:
        for shot in SHOTS:
            if shot["id"] not in keep:
                continue
            scheme = shot["options"].get("CONTROL_SCHEME", "modern")
            setup = shot.get("setup", "")
            if (scheme, setup) not in fixtures:
                fixtures[(scheme, setup)] = build_world(session, scheme, setup)
            png = images / f"{shot['id']}.png"
            proc = x11 = None
            try:
                proc, x11, window, run = launch(session, shot["id"], shot["options"], work,
                                                fixtures[(scheme, setup)])
                for keys in shot.get("keys", ()):
                    x11.key(*keys, delay=0.6)
                if shot.get("click"):
                    px, py, button = shot["click"]
                    x11.focus_local(window, px, py)
                    time.sleep(0.6)
                    x11.click(button, delay=0.6)
                time.sleep(1.5)
                capture(session.display, window, png)
                digest = hashlib.sha256(png.read_bytes()).hexdigest()
                if digest in seen_shots:
                    raise RuntimeError(f"identical to {seen_shots[digest]}: the key sequence did not "
                                       "change the screen")
                seen_shots[digest] = shot["id"]
                made.append(shot)
                print(f"ok   {shot['id']} -> {png} ({png.stat().st_size // 1024} KB)")
            except Exception as error:  # one bad key sequence must not lose the rest
                failed.append((shot["id"], str(error)))
                print(f"FAIL {shot['id']}: {error}")
            finally:
                if proc is not None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                if x11 is not None:
                    x11.close()
    finally:
        session.close()

    page = out / "feature-screenshots.md"
    lines = [DOC_HEAD]
    for shot in made:
        lines += [f"## {shot['title']}\n", f"![{shot['title']}](images/features/{shot['id']}.png)\n",
                  shot["body"] + "\n"]
    if failed:
        lines += ["## Not captured\n",
                  "These shots failed in the last run. Re-run the tool for them:\n"]
        lines += [f"- `{name}`: {error}" for name, error in failed]
        lines.append("")
    page.write_text("\n".join(lines))
    print(f"\n{len(made)} captured, {len(failed)} failed. Page: {page}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
