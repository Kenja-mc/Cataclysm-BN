#!/usr/bin/env python3
"""Playtest harness: sets up a scenario for a fork feature in a fresh game, then hands it to you.

    python3 tests/e2e/playtest.py --list
    python3 tests/e2e/playtest.py <scenario> [--tiles] [--scheme modern|classic] [--no-attach]

The game starts headless in tmux with the curses binary, the scenario's Lua builds the situation
next to the player, and then:
  - by default you are attached to the tmux session and play in your terminal (Ctrl+B D detaches);
  - with --tiles the game is saved and reopened in the tiles binary, in a normal window;
  - with --no-attach the screen is printed and the session closed (for checking scenarios).

The same startup path serves the agentic playtest (tests/e2e/agent_playtest.py): start_scenario()
returns a handle whose .game (curses) or .tiles (the tiles build on a private Xvfb display) carries
the live game for tests/e2e/agent_state.py to read and drive, and whose .close() stops the game
without deleting the private user directory. See docs/fork/agentic-playtests.md.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tiles  # noqa: E402
from helpers import HELPERS, save_and_quit, settle  # noqa: E402
from tmux_game import ROOT, Game, find_binary, in_game, start_new_game  # noqa: E402
ZOMBIE = "gapi.place_monster_at(MonsterTypeId.new('{id}'), here({x},{y})) "

SCENARIOS = [
    {
        "id": "quick_stack",
        "about": "Quick stack puts carried items into nearby storage that already holds them",
        "setup": "arena() spawn(2,0,'usb_drive',1,'f_rack') give('usb_drive',3) give('plastic_six_dice',1) ",
        "check": [
            "Enter > Interact > Quick stack: the three USB drives join the rack two tiles east.",
            "The dice stay in your inventory: nothing nearby holds dice.",
            "The log says 'Stashed N items into 1 spot'.",
        ],
    },
    {
        "id": "sort_pile",
        "about": "Sort pile moves the pile under you onto matching shelves",
        "setup": "arena() spawn(3,0,'usb_drive',1,'f_rack') spawn(-3,0,'flyer',1,'f_rack') "
                 "spawn(0,0,'usb_drive',2) spawn(0,0,'character_sheet',1) spawn(0,0,'plastic_six_dice',1) ",
        "check": [
            "Enter > Interact > Sort the pile: drives go to the east rack, the character sheet to the west rack.",
            "The dice stay on your tile.",
        ],
    },
    {
        "id": "combine",
        "about": "Combine partly used tools (matchbooks with 5 and 7 matches)",
        "setup": "arena() local u=gapi.get_avatar() u:create_item(ItypeId.new('matches'),1):set_charges(5) "
                 "u:create_item(ItypeId.new('matches'),1):set_charges(7) ",
        "check": [
            "Open the inventory (i), select a matchbook, press C (Combine).",
            "One matchbook with 12 matches remains; the log says 'You combine 2 matchbooks into one.'",
        ],
    },
    {
        "id": "folded_items",
        "about": "Black powder rounds stack with factory rounds; different rings share one line",
        "setup": "arena() local p=here(1,0) M:create_item_at(p, ItypeId.new('9mm'), 20) "
                 "local it=gapi.create_item(ItypeId.new('9mm'), 10) it:set_var_str('stack_mod:black_powder','10') "
                 "M:add_item(p, it) local u=gapi.get_avatar() for _,v in ipairs({'ruby_gold_ring','copper_ring'}) do "
                 "local r=gapi.create_item(ItypeId.new('jewelry_ring'), -1) r:set_var_str('variant',v) u:add_item(r) end ",
        "check": [
            "Look at the tile east of you (Shift+D): one stack of 30 9mm rounds, '10 black powder' in its name.",
            "Open the inventory (i): both rings share one line, each keeps its own name and price.",
        ],
    },
    {
        "id": "hud",
        "about": "Weather and Status boxes on the map, stance line, aligned sidebar, body panel",
        "setup": "arena() give('bat',1) gapi.get_avatar():add_effect(EffectTypeId.new('bleed'), "
                 "TimeDuration.from_turns(30), BodyPartTypeId.new('arm_l')) ",
        "check": [
            "Top-left boxes: weather and time; what you fight with, your style and stance.",
            "Sidebar rows share one label column; the Body panel lists the bleeding arm. Enter > Info > Body status opens details.",
            "Options > Interface > Weather box / Status box move the boxes or turn them off.",
        ],
    },
    {
        "id": "targeting",
        "about": "Aiming starts on the reachable hostile and warns about an ally in the line of fire",
        "setup": "arena() local u=gapi.get_avatar() u:add_item(gapi.create_item(ItypeId.new('model_10_revolver'), -1)) "
                 "u:add_item(gapi.create_item(ItypeId.new('38_special'), 12)) "
                 + ZOMBIE.format(id="mon_zombie", x=6, y=0)
                 + "local d=gapi.place_monster_at(MonsterTypeId.new('mon_dog'), here(3,0)) d:make_friendly() "
                 + ZOMBIE.format(id="mon_zombie_rot", x=-6, y=0),
        "check": [
            "Open inventory (i), select the revolver, choose Wield in its item actions, then reload (r).",
            "Press f: aiming starts on the decayed zombie to the west, whose line is clear.",
            "Tab to the east zombie: the panel says 'Ally in the line of fire: <dog>'.",
            "Hover a zombie with the mouse: the hint says what a click does.",
        ],
    },
    {
        "id": "loudness",
        "about": "Gun info shows how loud a shot is",
        "setup": "arena() give('m9',1) give('model_10_revolver',1) ",
        "check": [
            "Open the inventory, pick a gun, read its info: 'Loudness: N (loud|very loud|...)'.",
        ],
    },
    {
        "id": "sound_markers",
        "about": "A zombie walks behind a wall: its footsteps leave '?' markers that fade",
        "setup": "arena() for dy=-9,9 do M:set_ter_at(here(6,dy), TerId.new('t_wall'):int_id()) "
                 "for dx=7,9 do M:set_ter_at(here(dx,dy), TerId.new('t_floor'):int_id()) "
                 "M:set_furn_at(here(dx,dy), FurnId.new('f_null'):int_id()) end end "
                 + ZOMBIE.format(id="mon_zombie", x=8, y=6)
                 + "gapi.get_monster_at(here(8,6)):wander_to(here(8,-8), 100) ",
        "check": [
            "Wait a few turns (x): '?' markers appear east of the wall and dim as they age.",
            "Options > Interface > Sound marker turns sets how long they stay (1 = upstream).",
        ],
    },
    {
        "id": "safe_mode",
        "about": "Smart safe mode ignores a zombie locked in a glass cell, not one that can reach you",
        "options": {"SAFEMODE": "true"},
        "setup": "arena() for dx=-1,1 do for dy=-1,1 do if dx ~= 0 or dy ~= 0 then "
                 "M:set_ter_at(here(6+dx,dy), TerId.new('t_reinforced_glass'):int_id()) end end end "
                 + ZOMBIE.format(id="mon_zombie", x=6, y=0),
        "check": [
            "Press n (auto-explore) or walk away: safe mode does not stop you for the caged zombie.",
            "Smash the glass or let another zombie in: now safe mode stops you.",
        ],
    },
    {
        "id": "stances",
        "about": "Shift+X cycles walk, run, crouch and prone; the Status box shows the stance",
        "setup": "arena() ",
        "check": [
            "Press Shift+X repeatedly and watch all four stances in the Status box and Movement row.",
            "Enter > Combat > Movement Mode Menu opens the full movement mode menu.",
        ],
    },
    {
        "id": "contextual",
        "about": "Space offers explicit actions for the selected tile",
        "setup": "arena() M:set_ter_at(here(1,0), TerId.new('t_door_c'):int_id()) "
                 "M:set_ter_at(here(-3,0), TerId.new('t_door_c'):int_id()) spawn(-3,2,'rock',2) ",
        "check": [
            "Right-click the east door to select it; Space then Open opens it, Space then Close closes it.",
            "With no tile selected, Space lists nearby tiles; choose a direction then the explicit Open or Smash action.",
            "Inventory (i), select an item, then choose Use from its item actions.",
        ],
    },
    {
        "id": "crafting",
        "about": "Crafting says what is missing and jumps to a part you can make",
        "setup": "arena() give('string_6',6) ",
        "check": [
            "Open crafting (i, then F5), filter (f) 'short rope'.",
            "The recipe panel starts with 'Missing: ...'; long string is tagged '(can make)'.",
            "Press p (modern scheme): the list jumps to the long string recipe.",
        ],
    },
    {
        "id": "status_effects",
        "about": "Tiles: bleeding, poisoned and stunned creatures show looping overlays (use --tiles)",
        "setup": "arena() "
                 + ZOMBIE.format(id="mon_zombie", x=2, y=0)
                 + "local a=gapi.get_monster_at(here(2,0)) a:make_friendly() "
                 "a:add_effect(EffectTypeId.new('bleed'), TimeDuration.from_turns(600)) "
                 + ZOMBIE.format(id="mon_zombie", x=-2, y=1)
                 + "local b=gapi.get_monster_at(here(-2,1)) b:make_friendly() "
                 "b:add_effect(EffectTypeId.new('poison'), TimeDuration.from_turns(600)) "
                 + ZOMBIE.format(id="mon_zombie", x=0, y=-2)
                 + "local c=gapi.get_monster_at(here(0,-2)) c:make_friendly() "
                 "c:add_effect(EffectTypeId.new('stunned'), TimeDuration.from_turns(600)) ",
        "check": [
            "In the tiles window: a falling blood drip, a bobbing poison icon and dizzy stars loop.",
            "Options > Graphics > Status effect animations turns them off.",
        ],
    },
    {
        "id": "stress",
        "about": "A horde of 120 zombies around you behind reinforced glass: smart features must not lag",
        "options": {"SAFEMODE": "true"},
        "setup": "arena() for dx=-2,2 do for dy=-2,2 do if math.max(math.abs(dx),math.abs(dy))==2 then "
                 "M:set_ter_at(here(dx,dy), TerId.new('t_reinforced_glass'):int_id()) end end end "
                 "local n=0 for r=6,40,3 do for dx=-r,r,4 do for _,dy in ipairs({-r,r}) do if n<120 then "
                 "M:set_ter_at(here(dx,dy), TerId.new('t_floor'):int_id()) "
                 "M:set_furn_at(here(dx,dy), FurnId.new('f_null'):int_id()) "
                 "if gapi.place_monster_at(MonsterTypeId.new('mon_zombie'), here(dx,dy)) then n=n+1 end "
                 "end end end end ",
        "check": [
            "The horde surrounds you but cannot break the glass; compare turn responsiveness with the",
            "smart options off (Options > Interface: Smart safe mode, Enemy edge arrows).",
            "Wait a few turns (x), then rest or wait an hour: no stutter. A large horde can stop safe",
            "mode conservatively when the per-update route-search budget is exhausted.",
            "On a small terminal, edge arrows point at the off-screen part of the horde in yellow.",
        ],
    },
    # ------------------------------------------------------------------ agentic playtest content
    {
        "id": "main_menu",
        "about": "Main menu navigation: the title screen and every submenu the fork reaches from it",
        "start": "menu",
        "setup": "",
        "check": [
            "Title screen: the MOTD panel, the menu list and the version line.",
            "New Game opens the character submenu (Custom, Preset, Random, Play Now, Tutorial, Defence).",
            "World > Show World Mods lists the fork's mods; Settings > Options opens the options pages.",
            "Load is greyed out on an empty user directory; Quit leaves the game.",
            "Every row shows its hotkey, and a mouse click selects and activates rows too.",
        ],
    },
    {
        "id": "tutorial",
        "about": "The built-in tutorial: popups teach movement, inventory, crafting and combat",
        "start": "tutorial",
        "setup": "",
        "check": [
            "The tutorial room loads at noon with a popup explaining the lesson; spacebar closes it.",
            "Follow every popup: move, take an item, wield, craft, read the safety instructions.",
            "The sidebar, the body panel and Enter > Info > Body status match what the tutorial says.",
        ],
    },
    {
        "id": "natural_gameplay",
        "about": "A fresh world with no scripted setup: play naturally and report what the agent finds",
        "setup": "",
        "check": [
            "Start inside the shelter: pick up and wield gear, read the first tips, then leave the shelter.",
            "Play ordinary survival turns: fight, loot, craft, rest. Report bugs, unclear prompts and stale hints.",
            "Nothing here is scripted, so this is the one scenario that sees the game as a player does.",
        ],
    },
    {
        # One map that gathers the fork's inventory, HUD, body panel and hub changes within a few tiles
        # of the player. The groups below are the fork features, in the order the checks read them.
        "id": "fork_features",
        "about": "A custom map next to the fork's inventory, HUD, body panel, weather and hub changes",
        "setup":
            "arena() "
            # Quick stack: a rack that already holds what the player carries.
            "spawn(2,0,'usb_drive',1,'f_rack') give('usb_drive',3) give('plastic_six_dice',1) "
            # Sort pile: loose piles under the player next to racks that already hold the same items.
            "spawn(3,2,'flyer',1,'f_rack') spawn(-3,0,'character_sheet',1,'f_rack') "
            "spawn(0,0,'usb_drive',2) spawn(0,0,'character_sheet',1) spawn(0,0,'plastic_six_dice',1) "
            "spawn(-1,0,'rag',4) "
            # Item variants and stack modifiers: one folded 9mm line and two rings sharing one row.
            "local p=here(1,0) M:create_item_at(p, ItypeId.new('9mm'), 20) "
            "local bp=gapi.create_item(ItypeId.new('9mm'), 10) bp:set_var_str('stack_mod:black_powder','10') "
            "M:add_item(p, bp) local u=gapi.get_avatar() "
            "for _,v in ipairs({'ruby_gold_ring','copper_ring'}) do "
            "local r=gapi.create_item(ItypeId.new('jewelry_ring'), -1) r:set_var_str('variant',v) u:add_item(r) end "
            # Body panel: a bleeding left arm and a bat to wield, so wounds and stance have a subject.
            "u:add_effect(EffectTypeId.new('bleed'), TimeDuration.from_turns(30), BodyPartTypeId.new('arm_l')) "
            "u:add_item(gapi.create_item(ItypeId.new('bat'), -1)) "
            # Thermometer and weather: rain over the player's overmap tile, so the reading and the
            # weather box both have something to show.
            "u:add_item(gapi.create_item(ItypeId.new('thermometer'), -1)) "
            "gapi.set_omt_weather_override(coords.project_to_omt(u:abs_pos()), 3, 'rain', nil) "
            # Combat and interaction: a zombie west of you and another near the shelter's edge.
            + ZOMBIE.format(id="mon_zombie", x=-6, y=0)
            + ZOMBIE.format(id="mon_zombie", x=6, y=-4),
        "check": [
            "Enter > Interact > Quick stack folds the carried USB drives into the rack two tiles east.",
            "Enter > Interact > Sort the pile sends the two USB drives and the character sheet from under "
            "you to the matching racks; the rags and the dice have no shelf and stay.",
            "Look east (Shift+D): the 9mm stack reads '30' with '10 black powder'; the inventory (i) shows both rings.",
            "The sidebar Body panel lists the bleeding left arm; Enter > Info > Body status opens the details.",
            "The weather box and the thermometer both show the rain override; wait (x) and watch them track the weather.",
            "Enter is one keypress into the hub menu; the two zombies placed around you are the combat lesson.",
        ],
    },
]

SCENARIOS_BY_ID = {scenario["id"]: scenario for scenario in SCENARIOS}


def scenario_by_id(scenario_id):
    if scenario_id not in SCENARIOS_BY_ID:
        raise SystemExit(f"unknown scenario {scenario_id!r}; see --list")
    return SCENARIOS_BY_ID[scenario_id]


def tiles_binary():
    for candidate in (ROOT / "out" / "build" / "linux-full" / "src" / "cataclysm-bn-tiles",
                      ROOT / "cataclysm-bn-tiles"):
        if candidate.exists():
            return candidate
    raise SystemExit("cataclysm-bn-tiles not found; build the tiles target first")


# ------------------------------------------------------------------ the startup handle

@dataclass
class TilesRun:
    """A live tiles game on a private Xvfb display, in the shape agent_state reads.

    agent_state resolves handle.tiles.x11 / .display / .window_id (or .win) and falls back to a
    fresh tiles.capture(); .frame is the capture that proved the window had drawn.
    """
    proc: object
    xvfb: object
    x11: "tiles.X11"
    window_id: int
    display: str
    run: Path
    frame: object  # Path of the drawn-world capture, or None
    log: object
    xvfb_log: object = None

    @property
    def window(self):
        return self.window_id

    @property
    def win(self):
        return self.window_id

    def capture(self, png=None):
        """Whole-window PNG of the current frame, written under the run directory by default."""
        path = Path(png) if png else self.run / f"frame-{time.time():.3f}.png"
        return tiles.capture(self.display, self.window_id, path)

    def frame_rgb(self):
        return tiles.frame_rgb(self.capture())

    def key(self, *keysyms, delay=0.1):
        self.x11.key(*keysyms, delay=delay)

    def click(self, button, delay=0.1):
        self.x11.click(button, delay=delay)

    def close(self):
        # Close the display connection first: Xvfb going away under an open connection aborts the
        # whole process with an XIO fatal IO error, which would skip the caller's own teardown.
        if self.x11:
            self.x11.close()
        tiles.stop_process(self.proc)
        tiles.stop_process(self.xvfb)
        for handle in (self.log, self.xvfb_log):
            if handle:
                handle.close()


@dataclass
class ScenarioHandle:
    """The started scenario: one shape for both modes, so callers never branch on the library."""
    scenario_id: str
    mode: str                      # "curses" | "tiles"
    scheme: str
    userdir: Path                  # private; never deleted here
    save_name: str | None          # the saved world, read before teardown in tiles mode
    game: Game | None = None       # curses only
    tiles: TilesRun | None = None  # tiles only
    about: str = ""
    check: tuple[str, ...] = field(default_factory=tuple)

    def close(self):
        """Stop the game: kill the tmux session and stop Xvfb/the tiles process."""
        if self.game is not None:
            subprocess.run(["tmux", "kill-session", "-t", self.game.name], stderr=subprocess.DEVNULL)
        if self.tiles is not None:
            self.tiles.close()


# ------------------------------------------------------------------ startup

# tmux_game.Game builds its command line from the Game constructor, which takes no extra game
# arguments, so a --seed run goes through a shim in front of the binary: the wrapper receives the
# binary path as $1 and the game's own arguments after it. Only --seed is injected.
SEED_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def seed_wrapper(userdir, seed):
    if not SEED_PATTERN.fullmatch(seed):
        raise SystemExit(f"seed {seed!r} must be 1-64 characters of letters, digits, '.', '_' or '-'")
    script = Path(userdir) / "bin" / "seed-wrapper"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(f'#!/bin/sh\nbin="$1"; shift\nexec "$bin" --seed \'{seed}\' "$@"\n')
    script.chmod(0o755)
    return str(script)


def reach_main_menu(g, timeout=240):
    """Get past the language prompt and welcome popup, and stop on the title screen."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        screen = g.screen()
        if "Select your language" in screen:
            g.keys("1")
        elif "Welcome to Bright Nights" in screen:
            g.keys("Escape", delay=1)
        elif "Really quit?" in screen:
            g.keys("Escape", delay=1)  # Escape at the title screen opens this; it would eat later keys
        elif "MOTD" in screen and "New Game" in screen:
            return
        elif not screen.strip():
            g.keys("F5", delay=1)
        else:
            time.sleep(0.5)
    raise SystemExit("never reached the main menu\n" + g.screen())


def select_row(g, label, *, timeout=20):
    """Move the cursor inside the open menu box onto the row containing label, then activate it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = [line for line in g.screen().splitlines() if line.count("│") >= 2]
        cursor = next((i for i, line in enumerate(rows) if "»" in line), None)
        target = next((i for i, line in enumerate(rows) if label in line), None)
        if cursor is not None and target is not None:
            for _ in range(abs(target - cursor)):
                g.keys("Down" if target > cursor else "Up", delay=0.25)
            g.keys("Enter", delay=1)
            return True
        time.sleep(0.3)
    return False


def start_tutorial(g, timeout=300):
    """New Game > Tutorial, then wait for the tutorial room and dismiss its intro popup."""
    reach_main_menu(g)
    # The title screen is a tab bar with the selected tab's rows in a box next to it; New Game
    # holds Tutorial, and picking a row needs the cursor moved onto it, not a hotkey.
    g.keys("n", delay=1)
    if not select_row(g, "Tutorial"):
        g.keys("Enter", delay=1)  # some layouts need Enter to open the tab's rows first
        if not select_row(g, "Tutorial"):
            raise SystemExit("no Tutorial row in the New Game menu\n" + g.screen())
    deadline = time.time() + timeout
    while time.time() < deadline:
        screen = g.screen()
        if "Really quit?" in screen:
            g.keys("Escape", delay=1)  # a stray quit prompt would eat every later key
        elif "Are you SURE" in screen:
            g.keys("Y", delay=1)
        elif "How should death work" in screen:
            g.keys("r", delay=1)
        elif in_game(screen) or ("tutorial" in screen.lower() and "[MOTD]" not in screen):
            # The lesson is a modal popup; leave it up so the first state dump shows it.
            return
        else:
            time.sleep(0.5)
    raise SystemExit("never reached the tutorial\n" + g.screen())


def wait_for_save(userdir, timeout=90):
    """Wait for the saved world and return its name.

    The title screen renders the Load tab as "LoAd", so the save on disk is the reliable signal.
    """
    save_dir = Path(userdir) / "save"
    deadline = time.time() + timeout
    while time.time() < deadline:
        saves = [p.name for p in save_dir.glob("*") if p.is_dir()] if save_dir.is_dir() else []
        if len(saves) == 1:
            return saves[0]
        time.sleep(0.5)
    raise SystemExit(f"no single saved world under {save_dir}")


def start_tiles(userdir, save_name, seed=None, timeout=180):
    """Reopen a saved scenario world in the tiles build on a private Xvfb display.

    The tiles build reads its options from XDG_CONFIG_HOME, not --userdir, so the scenario's config
    is copied there and the deterministic tiles options are merged in.
    """
    icd = tiles.DEFAULT_LAVAPIPE_ICD
    if not icd.exists():
        raise SystemExit(f"lavapipe ICD not found: {icd} (install the software Vulkan driver)")
    run = Path(userdir) / "tiles"
    (run / "xdg" / "cataclysm-bn").mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(userdir) / "config", run / "xdg" / "cataclysm-bn", dirs_exist_ok=True)
    tiles.patch_options(run / "xdg" / "cataclysm-bn" / "options.json", tiles.DETERMINISTIC_OPTIONS)
    for sub in ("home", "cache", "data", "state"):
        (run / sub).mkdir(parents=True, exist_ok=True)
    xvfb, display, xvfb_log = tiles.start_xvfb(run)
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(run / "home"),
        "XDG_CONFIG_HOME": str(run / "xdg"),
        "XDG_CACHE_HOME": str(run / "cache"),
        "XDG_DATA_HOME": str(run / "data"),
        "XDG_STATE_HOME": str(run / "state"),
        "DISPLAY": display,
        "SDL_VIDEODRIVER": "x11",
        "SDL_AUDIODRIVER": "dummy",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "VK_DRIVER_FILES": str(icd),
    }
    cmd = [str(tiles_binary()), "--basepath", f"{ROOT}/", "--userdir", f"{userdir}/", "--world", save_name]
    if seed:
        cmd += ["--seed", seed]
    log = (run / "tiles.log").open("w")
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=log)
    x11 = None
    try:
        # wait_for_frame wants two identical captures of a drawn world, so the title screen does not count.
        frame = tiles.wait_for_frame(_Display(display), proc, run, timeout)
        x11 = tiles.X11(display)
        window = x11.find_window(tiles.WINDOW_TITLE_PREFIX)
        if not window:
            raise SystemExit(f"tiles window not found (see {run / 'tiles.log'})")
        # There is no window manager, so keys must be aimed at the game window explicitly.
        x11.focus_local(window, 40, 40)
    except BaseException:
        if x11:
            x11.close()  # before Xvfb goes away, or Xlib aborts this process
        tiles.stop_process(proc)
        tiles.stop_process(xvfb)
        log.close()
        raise
    return TilesRun(proc=proc, xvfb=xvfb, x11=x11, window_id=window, display=display, run=run,
                    frame=frame, log=log, xvfb_log=xvfb_log)


class _Display:
    """tiles.wait_for_frame only needs the display name on its session argument."""

    def __init__(self, display):
        self.display = display


def start_scenario(scenario_id, *, mode="curses", scheme="modern", userdir=None, seed=None):
    """Build a scenario in a fresh private world and return a live ScenarioHandle.

    mode: "curses" keeps the tmux game in the handle's .game; "tiles" saves the prepared world and
    reopens it in the tiles build under a private Xvfb display, in the handle's .tiles. scheme is
    written as CONTROL_SCHEME (pass "" to leave the game's own default). seed fixes the world
    generator when given; it is taken as text (1-64 letters, digits, '.', '_' or '-'), and any
    other type is stringified so an int seed from argparse still works. userdir defaults to
    /tmp/bn-playtest/<scenario> and is always rebuilt.
    """
    scenario = scenario_by_id(scenario_id)
    if mode not in ("curses", "tiles"):
        raise SystemExit(f"unknown mode {mode!r}; use 'curses' or 'tiles'")
    if seed is not None and not isinstance(seed, str):
        seed = str(seed)
    start = scenario.get("start", "game")
    if mode == "tiles" and start != "game":
        raise SystemExit(f"scenario {scenario_id!r} starts at {start!r} and has no saved world; "
                         "the tiles build can only reopen a saved world")
    dirpath = Path(userdir) if userdir else Path("/tmp/bn-playtest") / scenario_id
    shutil.rmtree(dirpath, ignore_errors=True)
    dirpath.mkdir(parents=True)

    options = {"SAFEMODE": "false", **scenario.get("options", {})}
    if scheme:
        options["CONTROL_SCHEME"] = scheme
    wrapper = seed_wrapper(dirpath, seed) if seed else None
    previous_wrapper = os.environ.get("GAME_WRAPPER")
    if wrapper:
        os.environ["GAME_WRAPPER"] = wrapper
    try:
        g = Game(name=f"bn-playtest-{scenario_id}", options=options, userdir=dirpath)
    finally:
        if wrapper:
            if previous_wrapper is None:
                os.environ.pop("GAME_WRAPPER", None)
            else:
                os.environ["GAME_WRAPPER"] = previous_wrapper

    def handle(**kwargs):
        return ScenarioHandle(scenario_id=scenario_id, mode=mode, scheme=scheme, userdir=dirpath,
                              about=scenario["about"], check=tuple(scenario["check"]), **kwargs)

    if start == "menu":
        reach_main_menu(g)
        return handle(save_name=None, game=g)
    if start == "tutorial":
        start_tutorial(g)
    else:
        start_new_game(g)
        settle(g)
        g.define_lua(HELPERS)
        setup = scenario.get("setup", "")
        if setup:
            result = g.lua(setup + "out('done')")
            if not result or result[-1] != "done":
                print(g.screen())
                raise SystemExit(f"scenario setup failed: {result}")
        settle(g)

    if mode == "curses":
        return handle(save_name=None, game=g)

    save_and_quit(g)
    save_name = wait_for_save(dirpath)
    # Game.close() would delete the private user directory, so kill the session instead.
    subprocess.run(["tmux", "kill-session", "-t", g.name], stderr=subprocess.DEVNULL)
    run = start_tiles(dirpath, save_name, seed=seed)
    return handle(save_name=save_name, game=None, tiles=run)


# ------------------------------------------------------------------ the CLI

def record_session(handle, scenario, scheme):
    """Write a reproducible session record into the scenario's userdir and a persistent log.

    SESSION.md in the scenario userdir travels with the save while the game is running;
    an identical record is archived under ~/.local/share/cataclysm-bn/playtests/ so
    --no-attach runs are not lost.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    try:
        sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                                      text=True).strip()
        branch = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
                                         text=True).strip()
    except subprocess.CalledProcessError:
        sha = "unknown"
        branch = "unknown"

    binary = find_binary()
    lines = [
        f"# Playtest session: {scenario['id']} — {scenario['about']}",
        "",
        f"- **Scenario:** {scenario['id']}",
        f"- **Scheme:** {scheme or 'modern'}",
        f"- **Binary:** {binary}",
        f"- **Commit SHA:** {sha}",
        f"- **Branch:** {branch}",
        f"- **Started:** {ts}",
        "",
        "## Checklist",
    ]
    for check in scenario["check"]:
        lines.append(f"  - [ ] {check}   (result: )  (notes: )")
    lines.append("")
    lines.append("## Notes / feedback")
    lines.append("Write what you observed, what passed or failed, and any bugs or suggestions here.")
    lines.append("")
    lines.append("---")
    try:
        options = [f"{o['name']}={o['value']}"
                   for o in json.loads((handle.userdir / "config" / "options.json").read_text())]
    except Exception:
        options = []
    lines.append(f"- options: {options}")
    lines.append(f"- basepath: {ROOT}/")
    lines.append(f"- game data: {handle.userdir}")

    content = "\n".join(lines) + "\n"
    (handle.userdir / "SESSION.md").write_text(content)

    playtests = Path.home() / ".local" / "share" / "cataclysm-bn" / "playtests"
    playtests.mkdir(parents=True, exist_ok=True)
    (playtests / f"{scenario['id']}-{sha[:7]}-{ts.replace(':', '-')}").write_text(content)


def reopen_in_tiles_window(handle):
    """Hand the prepared save to the tiles build in the user's own display, and wait for it.

    This is the human path behind --tiles: a normal window the reader can play. The agent path uses
    start_scenario(mode="tiles") instead, which runs headless on a private Xvfb display.
    """
    g = handle.game
    save_and_quit(g)
    handle.save_name = wait_for_save(handle.userdir)
    handle.close()
    # The tiles build reads its options from XDG_CONFIG_HOME, not --userdir; give it the scenario's
    # options there so it neither ignores them nor touches your own config.
    xdg = handle.userdir / "xdg"
    shutil.rmtree(xdg, ignore_errors=True)
    shutil.copytree(handle.userdir / "config", xdg / "cataclysm-bn")
    options_file = xdg / "cataclysm-bn" / "options.json"
    options_file.write_text(json.dumps(
        [o for o in json.loads(options_file.read_text()) if o["name"] != "USE_TILES"]
        + [{"info": "", "default": "", "name": "USE_TILES", "value": "true"}]))
    # The tiles binary loads the first save of the world given by --world.
    return subprocess.run([str(tiles_binary()), "--basepath", f"{ROOT}/", "--userdir", f"{handle.userdir}/",
                           "--world", handle.save_name], cwd=ROOT,
                          env={**os.environ, "XDG_CONFIG_HOME": str(xdg)}).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", nargs="?")
    parser.add_argument("--list", action="store_true", help="list the scenarios")
    parser.add_argument("--tiles", action="store_true", help="reopen the prepared game in the tiles binary")
    parser.add_argument("--scheme", choices=["modern", "classic"], help="control scheme (default: modern)")
    parser.add_argument("--no-attach", action="store_true", help="print the screen and close instead of attaching")
    args = parser.parse_args()

    if args.list or not args.scenario:
        for s in SCENARIOS:
            print(f"  {s['id']:<16} {s['about']}")
        return 0
    scenario = scenario_by_id(args.scenario)
    if args.tiles and scenario.get("start", "game") != "game":
        raise SystemExit(f"{args.scenario} starts at the {scenario['start']} screen and has no saved world; "
                         "the tiles build can only reopen a saved world")

    handle = start_scenario(args.scenario, mode="curses", scheme=args.scheme or "")
    record_session(handle, scenario, args.scheme)
    print(f"\n{scenario['id']}: {scenario['about']}\nWhat to check:")
    for line in scenario["check"]:
        print(f"  - {line}")
    print(f"Game data: {handle.userdir}\n")

    if args.no_attach:
        print(handle.game.screen())
        handle.game.close()
        return 0
    if args.tiles:
        # Reopen the prepared world in the reader's display, so the old blocking --tiles path stays.
        return reopen_in_tiles_window(handle)
    if sys.stdin.isatty() and "TMUX" not in os.environ:
        os.execvp("tmux", ["tmux", "attach", "-t", handle.game.name])
    print(f"Attach with: tmux attach -t {handle.game.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
