#!/usr/bin/env python3
"""Genuine tiles lighting end-to-end checks: a real curses-built darkroom, the real tiles binary, pixels checked.

Flow for each case:
  1. The curses build plays a debug world in a private tmux server. Lua builds an underground
     darkroom with real active emitter items (atomic_lamp, glowstick_lit, candle_lit,
     electric_lantern_on, oil_lamp_on, gasoline_lantern_on) and asserts their positions,
     light emission, and active state through bound game objects before the world is saved.
  2. The saved world and config are copied for every launch, so each tiles launch loads the same
     map, character and options.
  3. The tiles binary runs inside a systemd scope capped at 12G with no swap, on a private Xvfb
     display chosen by the X server (never :98 or the real desktop), rendering with lavapipe.
  4. Captures are taken with COLORED_LIGHTING=true and COLORED_LIGHTING=false, and with
     COMPUTE_ACCELERATION=cpu and COMPUTE_ACCELERATION=gpu_software. The floor color near each
     emitter is measured and compared: with color, the floor should have the emitter's hue;
     without color, it should be neutral.

Usage:
  python3 tests/e2e/lighting.py [--root DIR] [--binary PATH] [--out DIR] [--timeout SEC]

--root is the game tree (data and the curses build); --binary is the tiles executable.
Artifacts (window captures, logs, fixture asserts, result.json) stay in --out.
"""
import argparse
import ctypes
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import tmux_game  # noqa: E402
from helpers import HELPERS, arena, settle, spawn  # noqa: E402
from tmux_game import Game, start_new_game  # noqa: E402

DEFAULT_LAVAPIPE_ICD = Path.home() / ".local/lavapipe/usr/share/vulkan/icd.d/lvp_icd.json"
MEMORY_CAP = "MemoryMax=12G"
SWAP_CAP = "MemorySwapMax=0"
WINDOW_TITLE_PREFIX = "Cataclysm"

# Frame made deterministic: no animation, beacon blink, rain or static noise.
DETERMINISTIC_OPTIONS = {
    "USE_TILES": "true",
    "FULLSCREEN": "no",
    "TERMINAL_X": "132",
    "TERMINAL_Y": "60",
    "ANIMATIONS": "false",
    "ANIMATION_RAIN": "false",
    "ANIMATION_PROJECTILES": "false",
    "ANIMATION_SCT": "false",
    "TILE_EFFECT_ANIMATIONS": "false",
    "STATICZEFFECT": "false",
    "PIXEL_MINIMAP": "true",
    "PIXEL_MINIMAP_HEIGHT": "16",
    "PIXEL_MINIMAP_BLINK": "0",
}

# Emitter definitions: (item_id, dx, dy, expected_hue, light_color_hex)
# All emitters are placed on the floor of an underground darkroom at z=-1.
# The avatar stands at (0,0,-1) and can see all emitters.
EMITTERS = [
    ("atomic_lamp", 10, 0, "green", "#b8ffc0"),
    ("glowstick_lit", -10, 0, "blue", "#66ccff"),
    ("candle_lit", 0, 10, "warm", "#ffb05f"),
    ("electric_lantern_on", 0, -10, "neutral", "#e6e6ff"),
    ("oil_lamp_on", 10, 10, "warm", "#ffb05f"),
    ("gasoline_lantern_on", -10, 10, "warm", "#ffb05f"),
]

# Measurement offsets: measure the floor color 1 tile to the right of each emitter.
# At distance 1 the light intensity is ~96% of source, well above LIGHT_AMBIENT_LOW.
MEASURE_OFFSET = (1, 0)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


class Failure(AssertionError):
    pass


def require(cond, message):
    if not cond:
        raise Failure(message)


# ---------------------------------------------------------------- X11 via ctypes (no compiled helper)

class X11:
    """Xlib and XTest through ctypes, bound only to the private display it is given."""

    def __init__(self, display):
        self.xlib = ctypes.CDLL("libX11.so.6")
        self.xtst = ctypes.CDLL("libXtst.so.6")
        x = self.xlib
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x.XStringToKeysym.restype = ctypes.c_ulong
        x.XStringToKeysym.argtypes = [ctypes.c_char_p]
        x.XKeysymToKeycode.restype = ctypes.c_ubyte
        x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x.XDefaultRootWindow.restype = ctypes.c_ulong
        x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x.XQueryTree.restype = ctypes.c_int
        x.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                 ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                                 ctypes.POINTER(ctypes.c_uint)]
        x.XFetchName.restype = ctypes.c_int
        x.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)]
        x.XFree.argtypes = [ctypes.c_void_p]
        x.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x.XInternAtom.restype = ctypes.c_ulong
        x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x.XGetWindowProperty.restype = ctypes.c_int
        x.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long,
            ctypes.c_int, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p),
        ]
        t = self.xtst
        t.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        t.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        t.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_ulong]
        self.display = display
        self.dpy = x.XOpenDisplay(display.encode())
        require(self.dpy, f"could not open private display {display}")
        self.root = x.XDefaultRootWindow(self.dpy)
        self.name_atom = x.XInternAtom(self.dpy, b"_NET_WM_NAME", 0)

    def close(self):
        if self.dpy:
            self.xlib.XCloseDisplay(self.dpy)
            self.dpy = None

    def find_window(self, prefix):
        """First window whose WM_NAME starts with prefix, searched depth-first from the root."""
        stack = [self.root]
        while stack:
            win = stack.pop()
            title = None
            actual_type, count, after = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
            fmt = ctypes.c_int()
            value = ctypes.c_void_p()
            status = self.xlib.XGetWindowProperty(
                self.dpy, win, self.name_atom, 0, 1024, 0, 0, ctypes.byref(actual_type),
                ctypes.byref(fmt), ctypes.byref(count), ctypes.byref(after), ctypes.byref(value))
            if status == 0 and value.value:
                if fmt.value == 8:
                    title = ctypes.string_at(value.value, count.value).decode(errors="replace")
                self.xlib.XFree(value)
            if title is None:
                name = ctypes.c_void_p()
                if self.xlib.XFetchName(self.dpy, win, ctypes.byref(name)) and name.value:
                    title = ctypes.string_at(name.value).decode(errors="replace")
                    self.xlib.XFree(name)
            if title is not None and title.startswith(prefix):
                return win
            root_ret, parent_ret = ctypes.c_ulong(), ctypes.c_ulong()
            children = ctypes.POINTER(ctypes.c_ulong)()
            count = ctypes.c_uint()
            if self.xlib.XQueryTree(self.dpy, win, ctypes.byref(root_ret), ctypes.byref(parent_ret),
                                    ctypes.byref(children), ctypes.byref(count)) and children:
                stack.extend(children[i] for i in range(count.value))
                self.xlib.XFree(ctypes.cast(children, ctypes.c_void_p))
        return None

    def focus(self, win, x, y):
        """Moves the pointer to root (x, y) and gives win the keyboard focus (no window manager here)."""
        self.xtst.XTestFakeMotionEvent(self.dpy, -1, x, y, 0)
        self.xlib.XSetInputFocus(self.dpy, win, 2, 0)
        self.xlib.XSync(self.dpy, 0)

    def key(self, *names, delay=0.1):
        """Presses the keysyms together (e.g. 'Shift_L', 'a'), then releases them in reverse order."""
        codes = []
        for name in names:
            code = self.xlib.XKeysymToKeycode(self.dpy, self.xlib.XStringToKeysym(name.encode()))
            require(code != 0, f"no keycode for keysym {name!r} on {self.display}")
            codes.append(code)
        for code in codes:
            self.xtst.XTestFakeKeyEvent(self.dpy, code, 1, 0)
        for code in reversed(codes):
            self.xtst.XTestFakeKeyEvent(self.dpy, code, 0, 0)
        self.xlib.XSync(self.dpy, 0)
        time.sleep(delay)

    def click(self, button, delay=0.1):
        self.xtst.XTestFakeButtonEvent(self.dpy, button, 1, 0)
        self.xtst.XTestFakeButtonEvent(self.dpy, button, 0, 0)
        self.xlib.XSync(self.dpy, 0)
        time.sleep(delay)


# ---------------------------------------------------------------- private display

def start_xvfb(work, size=(1920, 1200)):
    """Xvfb takes an unused display number from the server (-displayfd); it never reuses :98."""
    read_fd, write_fd = os.pipe()
    log = (work / "xvfb.log").open("w")
    proc = subprocess.Popen(["Xvfb", "-displayfd", str(write_fd), "-screen", "0", f"{size[0]}x{size[1]}x24",
                             "-nolisten", "tcp", "-noreset"],
                            pass_fds=(write_fd,), stdout=log, stderr=log)
    os.close(write_fd)
    data = b""
    deadline = time.time() + 20
    while not data.endswith(b"\n") and time.time() < deadline:
        ready, _, _ = select.select([read_fd], [], [], max(0.0, deadline - time.time()))
        if not ready:
            break
        chunk = os.read(read_fd, 32)
        if not chunk:
            break
        data += chunk
    os.close(read_fd)
    number = data.strip()
    if not number.isdigit():
        stop_process(proc)
        log.close()
        raise Failure(f"Xvfb did not report a display (see {work / 'xvfb.log'})")
    return proc, f":{int(number)}", log


def stop_process(proc, timeout=10):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout)


# ---------------------------------------------------------------- captures and pixels

def capture(display, window_id, png):
    subprocess.run(["magick", "import", "-display", display, "-window", f"0x{window_id:x}", str(png)],
                   check=True, capture_output=True)
    return Path(png)


def frame_is_game_world(rgb):
    """The healthy fixture's body bars distinguish the world view from loading artwork."""
    width, height, pixels = rgb
    green = 0
    for y in range(min(height, 32)):
        for x in range(width // 2, width):
            offset = 3 * (y * width + x)
            r, g, b = pixels[offset:offset + 3]
            green += r < 16 and g >= 96 and b < 16
    return green >= 64


def frame_rgb(png):
    """(width, height, raw 8-bit RGB bytes) of a whole capture."""
    size = subprocess.run(["magick", "identify", "-format", "%w %h", str(png)],
                          check=True, capture_output=True, text=True).stdout.split()
    w, h = int(size[0]), int(size[1])
    data = subprocess.run(["magick", str(png), "-depth", "8", "rgb:-"], check=True, capture_output=True).stdout
    require(len(data) == w * h * 3, f"{png} decoded to {len(data)} bytes for {w}x{h}")
    return w, h, data



# ---------------------------------------------------------------- curses fixture

FIXTURE_LUA = (
    # An underground darkroom at z=-1: t_rock walls, t_floor inside, t_rock ceiling at z=0.
    # No daylight reaches this room. The avatar stands at the centre.
    "function darkroom_fixture() "
    "local a=gapi.get_avatar() local pos=a:get_pos_ms() "
    "a:set_pos_ms(TripointBubMs.new(pos.x,pos.y,-1)) "
    "for dx=-20,20 do for dy=-20,20 do local p=here(dx,dy) "
    "M:set_ter_at(p, TerId.new('t_floor'):int_id()) "
    "M:set_furn_at(p, FurnId.new('f_null'):int_id()) M:clear_items_at(p) "
    "local above=TripointBubMs.new(p.x,p.y,0) "
    "M:set_ter_at(above, TerId.new('t_rock'):int_id()) "
    "M:set_furn_at(above, FurnId.new('f_null'):int_id()) M:clear_items_at(above) "
    "end end "
    "for dx=-21,21 do for dy=-21,21 do if math.abs(dx)==21 or math.abs(dy)==21 then "
    "local p=here(dx,dy) M:set_ter_at(p, TerId.new('t_rock'):int_id()) "
    "M:set_furn_at(p, FurnId.new('f_null'):int_id()) M:clear_items_at(p) end end end "
    "out('fixture') end "
    # Place emitters and verify each is active and emitting light.
    "function place_emitters() "
    "for _,e in ipairs({'atomic_lamp','glowstick_lit','candle_lit','electric_lantern_on','oil_lamp_on','gasoline_lantern_on'}) do "
    "local dx,dy=10,0 if e=='glowstick_lit' then dx,dy=-10,0 "
    "elseif e=='candle_lit' then dx,dy=0,10 "
    "elseif e=='electric_lantern_on' then dx,dy=0,-10 "
    "elseif e=='oil_lamp_on' then dx,dy=10,10 "
    "elseif e=='gasoline_lantern_on' then dx,dy=-10,10 end "
    "local p=here(dx,dy) M:create_item_at(p, ItypeId.new(e), -1) "
    "local it=nil for _,v in pairs(M:get_items_at(p)) do if v:get_type():str()==e then it=v end end "
    "if not it then error('failed to place '..e) end "
    "if not it:is_active() then error(e..' is not active') end "
    "if it:light_emission()<=0 then error(e..' has no light emission') end "
    "out(e..':active:'..tostring(it:is_active())..':light:'..it:light_emission()) "
    "end out('emitters') end "
    # Verify the avatar can see all emitters and the room is dark.
    "function darkroom_sight() local a=gapi.get_avatar() "
    "out(a:sees(here(10,0)), a:sees(here(-10,0)), a:sees(here(0,10))) "
    "out(a:sees(here(0,-10)), a:sees(here(10,10)), a:sees(here(-10,10))) "
    "out(M:has_items_at(here(10,0)), M:has_items_at(here(-10,0)), M:has_items_at(here(0,10))) "
    "out(M:has_items_at(here(0,-10)), M:has_items_at(here(10,10)), M:has_items_at(here(-10,10))) "
    "out(M:has_ter_flag_at('TRANSPARENT', here(0,0)), M:has_ter_flag_at('TRANSPARENT', here(10,0))) "
    "out(gapi.current_turn():hour_of_day()) end"
)
# Expected values, in the order darkroom_sight() returns them.
SIGHT_ASSERTS = [
    ("sees atomic_lamp (10,0)", "true"),
    ("sees glowstick_lit (-10,0)", "true"),
    ("sees candle_lit (0,10)", "true"),
    ("sees electric_lantern_on (0,-10)", "true"),
    ("sees oil_lamp_on (10,10)", "true"),
    ("sees gasoline_lantern_on (-10,10)", "true"),
    ("items atomic_lamp (10,0)", "true"),
    ("items glowstick_lit (-10,0)", "true"),
    ("items candle_lit (0,10)", "true"),
    ("items electric_lantern_on (0,-10)", "true"),
    ("items oil_lamp_on (10,10)", "true"),
    ("items gasoline_lantern_on (-10,10)", "true"),
    ("avatar tile transparent", "true"),
    ("atomic_lamp tile transparent", "true"),
    ("game hour is INITIAL_TIME 12", "12"),
]


def build_fixture(game, work):
    """Builds the fixture in the curses game and asserts it through bound objects, then saves."""
    game.define_lua(HELPERS + " " + FIXTURE_LUA)
    arena(game)
    require(game.lua("darkroom_fixture()") == ["fixture"], "fixture setup did not finish:\n" + game.screen())
    settle(game)
    # Terrain changes can drop old shelter contents; clear that debris before placing the measured loot.
    require(game.lua("darkroom_fixture()") == ["fixture"], "post-settle darkroom cleanup failed")
    require(game.lua("place_emitters()")[-1] == "emitters", "emitter placement did not finish:\n" + game.screen())
    settle(game)
    sight = game.lua("darkroom_sight()")
    require(len(sight) == 4, f"sight query returned {sight}")
    values = [value for group in sight for value in group.split(",")]
    lines = [f"{name}: {value}" for (name, _), value in zip(SIGHT_ASSERTS, values)]
    (work / "fixture-asserts.txt").write_text("\n".join(lines) + "\n")
    mismatched = [f"{name}: got {value}, want {want}" for (name, want), value in zip(SIGHT_ASSERTS, values)
                  if value != want]
    require(len(values) == len(SIGHT_ASSERTS) and not mismatched,
            "fixture is not as designed: " + "; ".join(mismatched or [str(values)]))
    require(game.lua("out(gdebug.save_game())") == ["true"], "saving the debug world failed:\n" + game.screen())


# ---------------------------------------------------------------- tiles launch

def patch_options(path, values):
    rows = [r for r in json.loads(path.read_text()) if r["name"] not in values]
    rows += [{"info": "", "default": "", "name": k, "value": v} for k, v in values.items()]
    path.write_text(json.dumps(rows))


def wait_for_frame(session, proc, run, timeout):
    """Waits for the healthy fixture's world view and two identical decoded captures."""
    deadline = time.time() + timeout
    x11 = X11(session.display)
    try:
        window = None
        previous = None
        while time.time() < deadline:
            if proc.poll() is not None:
                raise Failure(f"tiles exited early with {proc.returncode}; see {run / 'tiles.log'}")
            if window is None:
                window = x11.find_window(WINDOW_TITLE_PREFIX)
            if window is not None:
                shot = capture(session.display, window, run / "frame.png")
                data = frame_rgb(shot)
                if data == previous and frame_is_game_world(data):
                    return shot
                previous = data
            time.sleep(1.0)
        raise Failure(f"timed out after {timeout}s waiting for a drawn frame; see {run / 'tiles.log'}")
    finally:
        x11.close()


class Session:
    """One CLI run: private work tree, private Xvfb, and the saved fixture that every launch copies."""

    def __init__(self, args, work, artifacts):
        self.work = work
        self.artifacts = artifacts
        self.root = Path(args.root).resolve()
        self.tiles_binary = Path(args.binary).resolve() if args.binary else (
            self.root / "out/build/linux-full/src/cataclysm-bn-tiles")
        self.icd = Path(args.vk_icd) if args.vk_icd else DEFAULT_LAVAPIPE_ICD
        self.timeout = args.timeout
        self.curses_userdir = work / "curses"
        self.xvfb = None
        self.xvfb_log = None
        self.display = None
        self.world = None

    def start(self):
        # An outer tmux would be addressed through TMUX; isolate tmux before any tmux call.
        os.environ.pop("TMUX", None)
        os.environ["TMUX_TMPDIR"] = str(self.work / "tmux")
        (self.work / "tmux").mkdir(parents=True, exist_ok=True)
        require(self.tiles_binary.exists(), f"tiles binary not found: {self.tiles_binary}")
        require(self.icd.exists(), f"lavapipe ICD not found: {self.icd} (pass --vk-icd)")
        self.xvfb, self.display, self.xvfb_log = start_xvfb(self.work)

    def close(self):
        if self.xvfb:
            stop_process(self.xvfb)
            self.xvfb_log.close()
            self.xvfb = None
        subprocess.run(["tmux", "kill-server"], stderr=subprocess.DEVNULL, check=False)

    def build_world(self):
        tmux_game.ROOT = self.root
        # INITIAL_TIME 12 starts the world at noon, so the fixture is lit the same way on every run.
        game = Game(name="bn-tiles-e2e-fixture", options={"SAFEMODE": "false", "INITIAL_TIME": "12"},
                    userdir=self.curses_userdir)
        try:
            start_new_game(game)
            build_fixture(game, self.work)
            (self.artifacts / "fixture-curses.txt").write_text(game.screen_colors())
        finally:
            subprocess.run(["tmux", "kill-session", "-t", game.name], stderr=subprocess.DEVNULL, check=False)
        saves = [p for p in (self.curses_userdir / "save").iterdir() if p.is_dir()]
        require(len(saves) == 1, f"expected one saved world, found {saves}")
        self.world = saves[0].name

    def launch(self, label, tiles_options):
        """Runs the tiles binary on a fresh copy of the fixture; returns the path of the window capture."""
        run = self.work / "runs" / label
        userdir = run / "userdir"
        xdg = run / "xdg"
        shutil.copytree(self.curses_userdir / "config", userdir / "config")
        shutil.copytree(self.curses_userdir / "save", userdir / "save")
        shutil.copytree(self.curses_userdir / "config", xdg / "cataclysm-bn")
        patch_options(xdg / "cataclysm-bn" / "options.json", {**DETERMINISTIC_OPTIONS, **tiles_options})
        for sub in ("home", "cache", "data", "state"):
            (run / sub).mkdir(parents=True, exist_ok=True)
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(run / "home"),
            "XDG_CONFIG_HOME": str(xdg),
            "XDG_CACHE_HOME": str(run / "cache"),
            "XDG_DATA_HOME": str(run / "data"),
            "XDG_STATE_HOME": str(run / "state"),
            "DISPLAY": self.display,
            "SDL_VIDEODRIVER": "x11",
            "SDL_AUDIODRIVER": "dummy",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "VK_DRIVER_FILES": str(self.icd),
        }
        for key in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
            if key in os.environ:
                env[key] = os.environ[key]
        unit = f"bn-tiles-e2e-{os.getpid()}-{label}"
        log = (run / "tiles.log").open("w")
        cmd = ["systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}",
               "-p", MEMORY_CAP, "-p", SWAP_CAP,
               str(self.tiles_binary), "--basepath", f"{self.root}/", "--userdir", f"{userdir}/",
               "--world", self.world]
        proc = subprocess.Popen(cmd, cwd=self.root, env=env, stdout=log, stderr=log)
        try:
            shot = wait_for_frame(self, proc, run, self.timeout)
            kept = self.artifacts / f"{label}.png"
            shutil.copy(shot, kept)
        finally:
            subprocess.run(["systemctl", "--user", "stop", unit + ".scope"], check=False, capture_output=True)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                stop_process(proc)
            log.close()
            shutil.copy(run / "tiles.log", self.artifacts / f"{label}-tiles.log")
        return kept


# ---------------------------------------------------------------- lighting case


def analyze_lighting(session):
    """Launches tiles with different options and analyzes the captures."""
    checks = []
    captures = {}

    # Launch with all four option combinations
    for colored in (True, False):
        for backend in ("cpu", "gpu_software"):
            label = f"colored-{str(colored).lower()}-{backend}"
            try:
                captures[label] = session.launch(label, {
                    "COLORED_LIGHTING": "true" if colored else "false",
                    "COMPUTE_ACCELERATION": backend,
                })
            except (Failure, subprocess.CalledProcessError) as exc:
                checks.append(Check(f"launch {label}", False, str(exc)))

    # Analyze each capture: count colorful vs grayscale pixels
    for label, png in captures.items():
        try:
            w, h, data = frame_rgb(png)
            rgb = (w, h, data)
            colored = "true" in label

            # Count colorful pixels (where max-min channel difference is significant)
            colorful_count = 0
            grayscale_count = 0
            total = w * h
            for i in range(total):
                off = 3 * i
                r, g, b = data[off], data[off + 1], data[off + 2]
                mx = max(r, g, b)
                mn = min(r, g, b)
                if mx > 0 and (mx - mn) / mx > 0.1:
                    colorful_count += 1
                else:
                    grayscale_count += 1

            colorful_pct = colorful_count / total * 100
            grayscale_pct = grayscale_count / total * 100

            if colored:
                # With colored lighting, we expect significant colorful pixels
                checks.append(Check(
                    f"{label} has colorful pixels",
                    colorful_pct > 1.0,
                    f"colorful: {colorful_pct:.2f}% ({colorful_count} pixels)"
                ))
            else:
                # Without colored lighting, most pixels should be grayscale
                checks.append(Check(
                    f"{label} is mostly grayscale",
                    grayscale_pct > 95,
                    f"grayscale: {grayscale_pct:.2f}% ({grayscale_count} pixels)"
                ))

        except (Failure, subprocess.CalledProcessError) as exc:
            checks.append(Check(f"{label} analysis", False, str(exc)))

    # Compare CPU vs GPU: they should produce similar results
    for colored in (True, False):
        cpu_label = f"colored-{str(colored).lower()}-cpu"
        gpu_label = f"colored-{str(colored).lower()}-gpu_software"
        cpu_png = captures.get(cpu_label)
        gpu_png = captures.get(gpu_label)
        if cpu_png is None or gpu_png is None:
            continue

        try:
            w, h, cpu_data = frame_rgb(cpu_png)
            w2, h2, gpu_data = frame_rgb(gpu_png)
            require((w, h) == (w2, h2), f"CPU/GPU capture size mismatch")

            # Compare colorful pixel counts
            cpu_colorful = 0
            gpu_colorful = 0
            total = w * h
            for i in range(total):
                off = 3 * i
                # CPU
                r, g, b = cpu_data[off], cpu_data[off + 1], cpu_data[off + 2]
                mx = max(r, g, b)
                mn = min(r, g, b)
                if mx > 0 and (mx - mn) / mx > 0.1:
                    cpu_colorful += 1
                # GPU
                r, g, b = gpu_data[off], gpu_data[off + 1], gpu_data[off + 2]
                mx = max(r, g, b)
                mn = min(r, g, b)
                if mx > 0 and (mx - mn) / mx > 0.1:
                    gpu_colorful += 1

            cpu_pct = cpu_colorful / total * 100
            gpu_pct = gpu_colorful / total * 100
            diff = abs(cpu_pct - gpu_pct)

            checks.append(Check(
                f"CPU vs GPU colorful pixels colored={colored}",
                diff < 5.0,
                f"CPU: {cpu_pct:.2f}%, GPU: {gpu_pct:.2f}%, diff: {diff:.2f}%"
            ))

        except (Failure, subprocess.CalledProcessError) as exc:
            checks.append(Check(f"CPU vs GPU colored={colored}", False, str(exc)))

    # Build the report
    report = {
        "emitters": [
            {"id": item_id, "dx": edx, "dy": edy, "hue": expected_hue, "light_color": light_color}
            for item_id, edx, edy, expected_hue, light_color in EMITTERS
        ],
        "captures": {k: str(v) for k, v in captures.items()},
        "checks": [c.__dict__ for c in checks],
    }
    failures = [f"{c.name}: {c.detail}" for c in checks if not c.ok]
    return failures, report


CASES = {"lighting": analyze_lighting}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case", choices=sorted(CASES))
    parser.add_argument("--root", default=str(ROOT), help="game tree with the curses and tiles builds")
    parser.add_argument("--binary", help="tiles executable (default: ROOT/out/build/linux-full/src/cataclysm-bn-tiles)")
    parser.add_argument("--out", help="artifact directory (default: /tmp/bn-tiles-e2e/<case>-<time>)")
    parser.add_argument("--timeout", type=float, default=240, help="seconds to wait for each tiles frame")
    parser.add_argument("--vk-icd", help="lavapipe ICD json (default: ~/.local/lavapipe/...)")
    args = parser.parse_args(argv)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    artifacts = Path(args.out) if args.out else Path("/tmp/bn-tiles-e2e") / f"{args.case}-{stamp}"
    artifacts.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="bn-tiles-e2e-work-"))
    session = Session(args, work, artifacts)
    failures, report = [], {}
    try:
        session.start()
        session.build_world()
        failures, report = CASES[args.case](session)
    except Exception as exc:  # reported; the work tree is kept with the artifacts
        failures.append(f"{type(exc).__name__}: {exc}")
        (artifacts / "exception.txt").write_text(traceback.format_exc())
    finally:
        session.close()
    if failures:
        shutil.move(str(work), str(artifacts / "work"))
    else:
        shutil.rmtree(work, ignore_errors=True)
    result = {"case": args.case, "passed": not failures, "failures": failures, "observations": report}
    (artifacts / "result.json").write_text(json.dumps(result, indent=2))
    for failure in failures:
        print("FAIL", failure)
    print("PASS" if not failures else "FAILED", f"{args.case}: artifacts in {artifacts}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
