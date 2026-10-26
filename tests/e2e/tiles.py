#!/usr/bin/env python3
"""Genuine tiles end-to-end checks: a real curses-built world, the real tiles binary, pixels checked.

Flow for each case:
  1. The curses build plays a debug world in a private tmux server. Lua builds the fixture and
     asserts its sight, opacity and item state through bound game objects before the world is saved.
  2. The saved world and config are copied for every launch, so each tiles launch loads the same
     map, character and options.
  3. The tiles binary runs inside a systemd scope capped at 12G with no swap, on a private Xvfb
     display numbered :100 or higher (never :0, the real desktop), rendering with lavapipe.
  4. Markers are found by diffing whole-window captures: each zoom is captured with markers off and
     on from the same saved world; the only changed pixels must be gold, and the new gold is the marker set.

Usage:
  python3 tests/e2e/tiles.py minimap [--root DIR] [--binary PATH] [--out DIR] [--timeout SEC]
  python3 tests/e2e/tiles.py mouse [--root DIR] [--binary PATH] [--out DIR] [--timeout SEC]
  python3 tests/e2e/tiles.py sound_menu [--root DIR] [--binary PATH] [--out DIR] [--timeout SEC]
  python3 tests/e2e/tiles.py zoom [--root DIR] [--binary PATH] [--out DIR] [--timeout SEC]
  python3 tests/e2e/tiles.py overmap [--root DIR] [--binary PATH] [--out DIR] [--timeout SEC]
  python3 tests/e2e/tiles.py known_locks [--root DIR] [--binary PATH] [--out DIR] [--timeout SEC]

--root is the game tree (data and the curses build); --binary is the tiles executable.
Artifacts (window captures, marker crops, logs, fixture asserts, result.json) stay in --out.
"""
import argparse
import ctypes
import itertools
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
from dataclasses import dataclass, field
from contextlib import contextmanager
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
WINDOW_TITLE_PREFIX = "Bright Nights Overhaul"
GOLD = (255, 215, 0)
GOLD_TOLERANCE = 12
ZOOMS = ("1x", "2x", "4x")

# Frame made deterministic: no animation, beacon blink, rain or static noise.
# Fit the default 11x24 font within the 1200px-high Xvfb display.
DETERMINISTIC_OPTIONS = {
    "USE_TILES": "true",
    "FULLSCREEN": "no",
    "TERMINAL_X": "132",
    "TERMINAL_Y": "50",
    "ANIMATIONS": "false",
    "ANIMATION_RAIN": "false",
    "ANIMATION_PROJECTILES": "false",
    "ANIMATION_SCT": "false",
    "TILE_EFFECT_ANIMATIONS": "false",
    "STATICZEFFECT": "false",
    "PIXEL_MINIMAP": "true",
    "PIXEL_MINIMAP_HEIGHT": "16",
    "PIXEL_MINIMAP_BLINK": "0",
    # The frame wait reads the loader by its default compact progress window at the bottom.
    "LOADING_PROGRESS_COMPACT": "true",
    "LOADING_SCREEN_IMAGES": "false",
}

# Fixture offsets relative to the avatar, (dx, dy).
GROUND_ITEMS = {"east": (3, 0), "west": (-3, 2), "north": (0, -4)}  # open floor, loose rock
GROUND_JAR = (-6, -3)     # glass jar on open floor with a rock sealed inside: a perceived item, marked
SEALED_SAFE = (0, 3)      # f_safe_c with a rock inside: outer tile seen, contents inaccessible, unmarked
HIDDEN_BEHIND_WALL = (8, 0)  # loose rock, sight blocked by the wall column at dx=6: unmarked
WALL_TILE = (6, 0)
# Tiles that must carry a new gold marker. Everything else stays unmarked.
MARKED = {"east": GROUND_ITEMS["east"], "west": GROUND_ITEMS["west"], "north": GROUND_ITEMS["north"],
          "jar": GROUND_JAR}


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
        x.XTranslateCoordinates.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
        ]
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

    def focus_local(self, win, x, y):
        """Moves to a window-local pixel without assuming SDL placed the window at root (0, 0)."""
        root_x, root_y, child = ctypes.c_int(), ctypes.c_int(), ctypes.c_ulong()
        require(self.xlib.XTranslateCoordinates(self.dpy, win, self.root, x, y,
                                                ctypes.byref(root_x), ctypes.byref(root_y),
                                                ctypes.byref(child)),
                "could not translate window-local pointer position")
        self.focus(win, root_x.value, root_y.value)

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

    def press(self, button, delay=0.1):
        self.xtst.XTestFakeButtonEvent(self.dpy, button, 1, 0)
        self.xlib.XSync(self.dpy, 0)
        time.sleep(delay)

    def release(self, button, delay=0.1):
        self.xtst.XTestFakeButtonEvent(self.dpy, button, 0, 0)
        self.xlib.XSync(self.dpy, 0)
        time.sleep(delay)

    def drag(self, win, start, end, button=3, steps=6, delay=0.05):
        """Presses a button on a window-local point, moves in steps, releases."""
        self.focus_local(win, *start)
        self.press(button)
        for step in range(1, steps + 1):
            x = start[0] + (end[0] - start[0]) * step // steps
            y = start[1] + (end[1] - start[1]) * step // steps
            self.focus_local(win, x, y)
            time.sleep(delay)
        self.release(button)


# ---------------------------------------------------------------- private display

def start_xvfb(work, size=(1920, 1200)):
    """Start Xvfb on a free display from :100 up and wait for its -displayfd ready report.

    The display number must be explicit. Without one, Xvfb -displayfd probes from :0 and replaces
    the desktop Xwayland socket /tmp/.X11-unix/X0; X11 apps such as Steam then fail until relogin.
    """
    log = (work / "xvfb.log").open("w")
    candidates = [n for n in range(100, 200)
                  if not os.path.lexists(f"/tmp/.X{n}-lock") and not os.path.lexists(f"/tmp/.X11-unix/X{n}")]
    for number in candidates[:5]:
        read_fd, write_fd = os.pipe()
        proc = subprocess.Popen(["Xvfb", f":{number}", "-displayfd", str(write_fd), "-screen", "0",
                                 f"{size[0]}x{size[1]}x24", "-nolisten", "tcp", "-noreset"],
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
        if data.strip() == str(number).encode():
            return proc, f":{number}", log
        stop_process(proc)  # another server took this number first, or Xvfb failed; try the next one
    log.close()
    raise Failure(f"Xvfb did not report a display (see {work / 'xvfb.log'})")


def stop_process(proc, timeout=10):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout)


# ---------------------------------------------------------------- captures and pixels

def magick_command(tool):
    """The ImageMagick command for `tool`: 7.x `magick <tool>`, or the 6.x binary.

    Ubuntu runners carry ImageMagick 6, which has no `magick` shim, so `import`,
    `identify` and `convert` are called directly there; a developer machine usually
    carries 7, whose `magick` shim fronts the same three tools.
    """
    if not shutil.which("magick"):
        return ["convert" if tool == "convert" else tool]
    return ["magick"] if tool == "convert" else ["magick", tool]


def capture(display, window_id, png):
    subprocess.run([*magick_command("import"), "-display", display, "-window", f"0x{window_id:x}", str(png)],
                   check=True, capture_output=True)
    return Path(png)


def frame_shows_world(rgb):
    """Recognize edge content from the loaded world's map and sidebar.

    Launch options disable splash artwork; the title and compact loader stay centered.
    """
    width, height, pixels = rgb
    inset = min(20, width // 8)          # a full-screen border line is not the sidebar
    band = min(max(40, width // 8), width - 2 * inset)
    edges = ((inset, inset + band), (width - inset - band, width - inset))
    painted_rows = 0
    bottom_content = False
    for y in range(height):
        base = 3 * y * width
        for start, stop in edges:
            if any(pixels[offset] or pixels[offset + 1] or pixels[offset + 2]
                   for offset in range(base + 3 * start, base + 3 * stop, 3)):
                painted_rows += 1
                bottom_content |= y >= 3 * height // 4
                break
    return painted_rows * 4 >= height and bottom_content


def frame_rgb(png):
    """(width, height, raw 8-bit RGB bytes) of a whole capture."""
    size = subprocess.run([*magick_command("identify"), "-format", "%w %h", str(png)],
                          check=True, capture_output=True, text=True).stdout.split()
    w, h = int(size[0]), int(size[1])
    data = subprocess.run([*magick_command("convert"), str(png), "-depth", "8", "rgb:-"],
                          check=True, capture_output=True).stdout
    require(len(data) == w * h * 3, f"{png} decoded to {len(data)} bytes for {w}x{h}")
    return w, h, data


def gold_mask(rgb):
    """1 for each pixel within GOLD_TOLERANCE of the marker gold, else 0."""
    r, g, b = rgb[0::3], rgb[1::3], rgb[2::3]
    return bytearray(1 if (abs(r[i] - GOLD[0]) <= GOLD_TOLERANCE and abs(g[i] - GOLD[1]) <= GOLD_TOLERANCE
                           and abs(b[i] - GOLD[2]) <= GOLD_TOLERANCE) else 0
                     for i in range(len(r)))


def blobs_of(mask, w, h):
    """4-connected blobs of set pixels with bounding boxes and centres."""
    seen = bytearray(w * h)
    blobs = []
    for start in range(w * h):
        if seen[start] or not mask[start]:
            continue
        seen[start] = 1
        stack, xs, ys = [start], [], []
        while stack:
            p = stack.pop()
            px, py = p % w, p // w
            xs.append(px)
            ys.append(py)
            for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    q = ny * w + nx
                    if not seen[q] and mask[q]:
                        seen[q] = 1
                        stack.append(q)
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        blobs.append({"x0": x0, "y0": y0, "w": x1 - x0 + 1, "h": y1 - y0 + 1,
                      "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2, "pixels": len(xs)})
    return blobs


def crop_to(png, blob, out, margin=4):
    x0 = max(0, blob["x0"] - margin)
    y0 = max(0, blob["y0"] - margin)
    subprocess.run([*magick_command("convert"), str(png),
                    "-crop", f"{blob['w'] + 2 * margin}x{blob['h'] + 2 * margin}+{x0}+{y0}",
                    "+repage", str(out)], check=True, capture_output=True)


# ---------------------------------------------------------------- marker grid

def solve_line(xs, ys):
    """Least squares y = a + b*x; returns (a, b)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    require(var > 0, "fixture offsets must differ to recover the tile pitch")
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
    return my - b * mx, b


def fit_marker_grid(blobs, expected):
    """Pairs each expected tile with one blob so the centres sit on one grid, x = ox + dx*tx, y = oy + dy*ty.

    Every assignment of blobs to expected tiles is tried; the smallest worst-case residual wins.
    """
    names = list(expected)
    best = None
    for perm in itertools.permutations(range(len(blobs)), len(names)):
        pairs = [(expected[name], blobs[index]) for name, index in zip(names, perm)]
        ox, tx = solve_line([d[0] for d, _ in pairs], [b["cx"] for _, b in pairs])
        oy, ty = solve_line([d[1] for d, _ in pairs], [b["cy"] for _, b in pairs])
        if tx <= 0 or ty <= 0:
            continue
        residual = max(max(abs(ox + tx * d[0] - b["cx"]), abs(oy + ty * d[1] - b["cy"])) for d, b in pairs)
        if best is None or residual < best["residual"]:
            best = {"ox": ox, "tx": tx, "oy": oy, "ty": ty, "residual": residual,
                    "assignment": dict(zip(names, perm))}
    require(best is not None, f"no grid fits {len(blobs)} blobs for {len(names)} expected markers")
    return best


# ---------------------------------------------------------------- curses fixture

FIXTURE_LUA = (
    # An outdoor courtyard with an opaque ring; remove the shelter roof so daylight survives reload.
    # The internal column hides (8,0).
    "function minimap_fixture() "
    "for dx=-11,11 do for dy=-11,11 do local p=here(dx,dy) "
    "M:set_ter_at(p, TerId.new('t_floor'):int_id()) "
    "local above=TripointBubMs.new(p.x,p.y,p.z+1) "
    "M:set_furn_at(above, FurnId.new('f_null'):int_id()) M:clear_items_at(above) "
    "M:set_ter_at(above, TerId.new('t_open_air'):int_id()) "
    "M:set_furn_at(p, FurnId.new('f_null'):int_id()) M:clear_items_at(p) end end "
    "for dx=-12,12 do for dy=-12,12 do if math.abs(dx)==12 or math.abs(dy)==12 then local p=here(dx,dy) "
    "M:set_ter_at(p, TerId.new('t_wall'):int_id()) M:set_furn_at(p, FurnId.new('f_null'):int_id()) "
    "M:clear_items_at(p) end end end "
    "for dy=-2,2 do M:set_ter_at(here(6,dy), TerId.new('t_wall'):int_id()) end "
    "out('fixture') end "
    # A glass jar on open floor with a rock sealed inside it.
    "function ground_jar(dx,dy) local p=here(dx,dy) M:create_item_at(p, ItypeId.new('jar_glass'), -1) "
    "local jar=nil for _,it in pairs(M:get_items_at(p)) do if it:get_type():str()=='jar_glass' then jar=it end end "
    "jar:add_item_with_id(ItypeId.new('rock'), 1) out(jar:has_item_with_id(ItypeId.new('rock'))) end "
    # Sight, opacity, items, sealed-container flags, and game clock. Every value comes from a bound method.
    "function minimap_sight() local a=gapi.get_avatar() "
    "out(a:sees(here(3,0)), a:sees(here(-3,2)), a:sees(here(0,-4)), a:sees(here(-6,-3)), a:sees(here(0,3))) "
    "out(a:sees(here(8,0)), M:has_ter_flag_at('TRANSPARENT', here(6,0)), "
    "M:has_items_at(here(3,0)), M:has_items_at(here(-3,2)), M:has_items_at(here(0,-4))) "
    "out(M:has_items_at(here(-6,-3)), M:has_items_at(here(0,3)), M:has_items_at(here(8,0))) "
    "out(M:has_flag_at('CONTAINER', here(0,3)), M:has_flag_at('SEALED', here(0,3)), "
    "gapi.current_turn():hour_of_day()) end"
)
# Expected values, in the order minimap_sight() returns them.
SIGHT_ASSERTS = [
    ("sees east (3,0)", "true"),
    ("sees west (-3,2)", "true"),
    ("sees north (0,-4)", "true"),
    ("sees jar (-6,-3)", "true"),
    ("sees safe (0,3)", "true"),
    ("hidden (8,0) not seen", "false"),
    ("wall (6,0) not transparent", "false"),
    ("items east (3,0)", "true"),
    ("items west (-3,2)", "true"),
    ("items north (0,-4)", "true"),
    ("items jar (-6,-3)", "true"),
    ("items safe (0,3)", "true"),
    ("items hidden (8,0)", "true"),
    # Sealed container: could_see_items() is false when CONTAINER and SEALED both hold on the tile.
    ("safe is CONTAINER", "true"),
    ("safe is SEALED", "true"),
    ("game hour is INITIAL_TIME 12", "12"),
]


def build_fixture(game, work, zoom_ruler=False):
    """Builds the fixture in the curses game and asserts it through bound objects, then saves."""
    game.define_lua(HELPERS + " " + FIXTURE_LUA)
    arena(game)
    require(game.lua("minimap_fixture()") == ["fixture"], "fixture setup did not finish:\n" + game.screen())
    settle(game)
    # Terrain changes can drop old shelter contents; clear that debris before placing the measured loot.
    require(game.lua("minimap_fixture()") == ["fixture"], "post-settle courtyard cleanup failed")
    if zoom_ruler:
        require(game.lua("for dx=-11,11 do for dy=-11,11 do "
                         "local t=(dx%2==0) and 't_pavement' or 't_floor' "
                         "M:set_ter_at(here(dx,dy),TerId.new(t):int_id()) end end "
                         "for dy=-2,2 do M:set_ter_at(here(6,dy),TerId.new('t_wall'):int_id()) end "
                         "out('ruler')") == ["ruler"], "zoom ruler setup did not finish")
    for dx, dy in GROUND_ITEMS.values():
        spawn(game, dx, dy, "rock")
    spawn(game, *HIDDEN_BEHIND_WALL, "rock")
    spawn(game, *SEALED_SAFE, "rock", 1, "f_safe_c")
    require(game.lua(f"ground_jar({GROUND_JAR[0]},{GROUND_JAR[1]})") == ["true"],
            "jar did not take the sealed rock:\n" + game.screen())
    settle(game)
    sight = game.lua("minimap_sight()")
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


def patch_launch_options(userdir, xdg, values):
    """Patch both config locations selected by the compile-time USE_XDG_DIR option."""
    patch_options(Path(userdir) / "config" / "options.json", values)
    patch_options(Path(xdg) / "cataclysm-bn" / "options.json", values)


def wait_for_frame(session, proc, run, timeout):
    """Waits for two identical decoded captures of the loaded world.

    The world must be drawn (see frame_shows_world) as well as still, so neither a loading screen
    nor a half-painted first frame satisfies the wait.
    """
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
                if data == previous and frame_shows_world(data):
                    return shot
                previous = data
            time.sleep(1.0)
        raise Failure(f"timed out after {timeout}s waiting for a drawn frame; see {run / 'tiles.log'}")
    finally:
        x11.close()


@dataclass(frozen=True)
class RunningGame:
    proc: subprocess.Popen
    run: Path
    frame: Path


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

    def build_world(self, zoom_ruler=False):
        tmux_game.ROOT = self.root
        # INITIAL_TIME 12 starts the world at noon, so the fixture is lit the same way on every run.
        game = Game(name="bn-tiles-e2e-fixture", options={"SAFEMODE": "false", "INITIAL_TIME": "12"},
                    userdir=self.curses_userdir)
        try:
            start_new_game(game)
            build_fixture(game, self.work, zoom_ruler=zoom_ruler)
            (self.artifacts / "fixture-curses.txt").write_text(game.screen_colors())
        finally:
            subprocess.run(["tmux", "kill-session", "-t", game.name], stderr=subprocess.DEVNULL, check=False)
        saves = [p for p in (self.curses_userdir / "save").iterdir() if p.is_dir()]
        require(len(saves) == 1, f"expected one saved world, found {saves}")
        self.world = saves[0].name

    @contextmanager
    def running_game(self, label, tiles_options, fresh=True):
        """Keeps a fixture copy running for real input and captures; owns process cleanup.

        ``fresh=False`` reuses the label's own directories, so a relaunch sees the config a
        previous process wrote (zoom persistence, for instance).
        """
        run = self.work / "runs" / label
        userdir = run / "userdir"
        xdg = run / "xdg"
        if fresh:
            if run.exists():
                shutil.rmtree(run)
            shutil.copytree(self.curses_userdir / "config", userdir / "config")
            shutil.copytree(self.curses_userdir / "save", userdir / "save")
            shutil.copytree(self.curses_userdir / "config", xdg / "cataclysm-bn")
            patch_launch_options(userdir, xdg, {**DETERMINISTIC_OPTIONS, **tiles_options})
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
            yield RunningGame(proc=proc, run=run, frame=shot)
        finally:
            subprocess.run(["systemctl", "--user", "stop", unit + ".scope"], check=False, capture_output=True)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                stop_process(proc)
            log.close()
            shutil.copy(run / "tiles.log", self.artifacts / f"{label}-tiles.log")

    def launch(self, label, tiles_options):
        with self.running_game(label, tiles_options) as live:
            kept = self.artifacts / f"{label}.png"
            shutil.copy(live.frame, kept)
        return kept


# ---------------------------------------------------------------- minimap case

def analyse_zoom(zoom, off_png, on_png, artifacts):
    """Compares a markers-off and a markers-on capture of the same frame and checks the marker set."""
    checks = []
    w, h, off = frame_rgb(off_png)
    w2, h2, on = frame_rgb(on_png)
    require((w, h) == (w2, h2), f"{zoom}: off and on captures differ in size: {w}x{h} vs {w2}x{h2}")
    off_gold = gold_mask(off)
    on_gold = gold_mask(on)
    n = w * h
    r1, g1, b1 = off[0::3], off[1::3], off[2::3]
    r2, g2, b2 = on[0::3], on[1::3], on[2::3]
    changed = [i for i in range(n) if r1[i] != r2[i] or g1[i] != g2[i] or b1[i] != b2[i]]
    not_gold = [i for i in changed if not on_gold[i]]
    checks.append(Check("only gold pixels change between markers off and on", not not_gold,
                        f"{len(changed)} changed pixels, {len(not_gold)} not gold, first at "
                        f"{[(i % w, i // w) for i in not_gold[:5]]}"))
    new_gold = bytearray(1 if (on_gold[i] and not off_gold[i]) else 0 for i in range(n))
    blobs = blobs_of(new_gold, w, h)
    for k, blob in enumerate(blobs):
        crop_to(on_png, blob, artifacts / f"{zoom}-marker-{k}.png")
    expected = MARKED
    checks.append(Check("marker count", len(blobs) == len(expected),
                        f"expected {len(expected)}, saw {len(blobs)}"))
    result = {"zoom": zoom, "blobs": blobs, "checks": checks}
    if len(blobs) != len(expected):
        return result
    grid = fit_marker_grid(blobs, expected)
    result.update(ox=grid["ox"], oy=grid["oy"], tx=grid["tx"], ty=grid["ty"])
    tol = 0.5 * max(grid["tx"], grid["ty"]) + 1
    checks.append(Check("markers sit on one tile grid", grid["residual"] <= tol,
                        f"residual {grid['residual']:.2f}px, pitch {grid['tx']:.2f}x{grid['ty']:.2f}px"))
    cells = {(round((b["cx"] - grid["ox"]) / grid["tx"]), round((b["cy"] - grid["oy"]) / grid["ty"])): b
             for b in blobs}
    want = set(expected.values())
    unexpected = sorted(set(cells) - want)
    missing = sorted(want - set(cells))
    checks.append(Check("markers only on the perceived tiles", not unexpected and not missing,
                        f"unexpected {unexpected}, missing {missing}"))
    checks.append(Check("sealed safe stays unmarked", SEALED_SAFE not in cells,
                        f"tile {SEALED_SAFE} marked: {SEALED_SAFE in cells}"))
    checks.append(Check("item behind the wall stays unmarked", HIDDEN_BEHIND_WALL not in cells,
                        f"tile {HIDDEN_BEHIND_WALL} marked: {HIDDEN_BEHIND_WALL in cells}"))
    marker_px = max(1, int(grid["tx"]) // 3)
    sized = all(abs(b["w"] - marker_px) <= 1 and abs(b["h"] - marker_px) <= 1 for b in blobs)
    checks.append(Check("marker size tracks tile pitch", sized,
                        f"expected ~{marker_px}px, saw {[(b['w'], b['h']) for b in blobs]}"))
    return result


def case_minimap(session):
    captures = {}
    failures = []
    for zoom in ZOOMS:
        for on in (False, True):
            label = f"{zoom}-markers-{'on' if on else 'off'}"
            try:
                captures[label] = session.launch(label, {"PIXEL_MINIMAP_ITEM_MARKERS": "true" if on else "false",
                                                         "PIXEL_MINIMAP_ZOOM": zoom})
            except (Failure, subprocess.CalledProcessError) as exc:
                failures.append(f"{label}: {exc}")
    analyses = {}
    for zoom in ZOOMS:
        off, on = captures.get(f"{zoom}-markers-off"), captures.get(f"{zoom}-markers-on")
        if off is None or on is None:
            continue
        try:
            analyses[zoom] = analyse_zoom(zoom, off, on, session.artifacts)
        except (Failure, subprocess.CalledProcessError) as exc:
            failures.append(f"{zoom}: {exc}")
    base = analyses.get("1x")
    for zoom, factor in (("2x", 2), ("4x", 4)):
        obs = analyses.get(zoom)
        if not base or not obs or "tx" not in base or "tx" not in obs:
            continue
        ratio_x, ratio_y = obs["tx"] / base["tx"], obs["ty"] / base["ty"]
        obs["checks"].append(Check(f"zoom {zoom} scales the grid {factor}x", abs(ratio_x - factor) <= 0.2 * factor
                                   and abs(ratio_y - factor) <= 0.2 * factor,
                                   f"ratio x {ratio_x:.2f}, y {ratio_y:.2f}"))
    report = {}
    for zoom, obs in analyses.items():
        report[zoom] = {k: v for k, v in obs.items() if k != "checks"} | {
            "checks": [c.__dict__ for c in obs["checks"]]}
        failures += [f"{zoom}: {c.name}: {c.detail}" for c in obs["checks"] if not c.ok]
    report["captures"] = {k: str(v) for k, v in captures.items()}
    return failures, report


def case_mouse(session):
    """Check 2x selection with either sidebar origin."""
    # Free selection doesn't enable quicksave; use save-and-quit.
    bindings = session.curses_userdir / "config" / "keybindings.json"
    rows = json.loads(bindings.read_text()) if bindings.exists() else []
    rows = [row for row in rows if not (row.get("category") == "DEFAULTMODE"
                                      and row.get("id") in ("save", "quicksave"))]
    rows.append({"type": "keybinding", "id": "save", "category": "DEFAULTMODE",
                 "bindings": [{"input_method": "keyboard", "key": "F6"}]})
    bindings.write_text(json.dumps(rows))
    options = {
        "CONTROL_SCHEME": "modern", "MOUSE_MOVE": "false",
        "MOUSE_TILE_SELECTION": "true", "CURSOR_PANNING": "false",
        "SCALING_FACTOR": "2", "FULLSCREEN": "borderless", "TILES": "UNDEAD_PEOPLE_BASE",
        "FONT_WIDTH": "8", "FONT_HEIGHT": "16", "FONT_SIZE": "16",
        "TERMINAL_X": "160", "TERMINAL_Y": "60",
    }
    observations = {}
    hover_panel = None
    for side in ("right", "left"):
        label = f"mouse-2x-{side}"
        with session.running_game(label, {**options, "SIDEBAR_POSITION": side}) as live:
            x11 = X11(session.display)
            try:
                win = x11.find_window(WINDOW_TITLE_PREFIX)
                require(win is not None, f"{label}: game window disappeared")
                width, height, before = frame_rgb(live.frame)
                # The isolated fork layout has 44 sidebar cells, UndeadPeople tiles are 32px.
                # At 2x scale the visible map origin is 704px for the left sidebar, 0 otherwise.
                sidebar_width, tile_size = 44 * 8 * 2, 32 * 2
                terrain_width = width - sidebar_width
                require(terrain_width >= 3 * tile_size, f"{label}: terrain too narrow")
                origin = sidebar_width if side == "left" else 0
                avatar_x = origin + (terrain_width // tile_size // 2) * tile_size + tile_size // 2
                avatar_y = (height // tile_size // 2) * tile_size + tile_size // 2
                sidebar_x = 0 if side == "left" else terrain_width
                x11.focus_local(win, avatar_x + tile_size, avatar_y)
                time.sleep(1)
                hover_png = capture(session.display, win, session.artifacts / f"{label}-hover.png")
                _, _, hovered = frame_rgb(hover_png)
                def panel(rgb):
                    # Mouse View is a fixed-width sidebar panel; compare its actual rendered
                    # terrain description and action hint, not just the presence of changed pixels.
                    return b"".join(rgb[3 * (y * width + sidebar_x):
                                        3 * (y * width + sidebar_x + sidebar_width)]
                                    for y in range(height // 2))
                actual_panel = panel(hovered)
                require(actual_panel != panel(before), f"{label}: adjacent tile produced no hover")
                if hover_panel is None:
                    hover_panel = actual_panel
                else:
                    require(actual_panel == hover_panel,
                            f"{label}: visible adjacent tile has a different description/hint")
                saves = list((live.run / "userdir" / "save" / session.world).glob("*.sav"))
                require(len(saves) == 1, f"{label}: expected one character save, got {saves}")
                save = saves[0]
                def position():
                    return json.loads(save.read_text().split("\n", 1)[1])["player"]["abs_pos"]
                start = position()
                previous_stamp = save.stat().st_mtime_ns
                x11.click(3, delay=1)
                capture(session.display, win, session.artifacts / f"{label}-clicked.png")
                x11.key("F6", delay=1)
                x11.key("Left", delay=0.2)
                x11.key("Return", delay=1)
                deadline = time.time() + 30
                while save.stat().st_mtime_ns == previous_stamp and time.time() < deadline:
                    time.sleep(0.2)
                require(save.stat().st_mtime_ns != previous_stamp, f"{label}: save-and-quit did not persist")
                final = position()
                require(final == start, f"{label}: RMB selection moved the avatar {start} -> {final}")
                observations[side] = {"start": start, "final": final, "pointer": [avatar_x + tile_size, avatar_y],
                                      "terrain_origin": origin, "hover": str(hover_png)}
            finally:
                x11.close()
    return [], observations


ZOOM_SIDEBAR_CELLS = 44
ZOOM_FONT_WIDTH = 8


def saved_turn(path):
    return json.loads(path.read_text().split("\n", 1)[1])["turn"]


def column_levels(rgb, width, x0, x1, y0, y1):
    levels = []
    for x in range(x0, x1):
        samples = []
        for y in range(y0, y1):
            offset = 3 * (y * width + x)
            samples.append((rgb[offset] * 299 + rgb[offset + 1] * 587 + rgb[offset + 2] * 114) // 1000)
        samples.sort()
        levels.append(samples[len(samples) // 2])
    return levels


def tile_pitch(png, terrain_width, center_y):
    """Median rendered width of the fixture's alternating floor columns, in pixels."""
    width, height, rgb = frame_rgb(png)
    left, right = max(0, terrain_width // 2 - 360), terrain_width // 2 - 60
    top, bottom = max(0, center_y - 360), center_y - 140
    require(right - left >= 160 and bottom - top >= 80, f"{png}: map crop is too small")
    levels = column_levels(rgb, width, left, right, top, bottom)
    dark, light = min(levels), max(levels)
    require(light - dark >= 25, f"{png}: alternating floor columns are not contrasty ({dark}..{light})")
    split = (dark + light) / 2
    runs, start = [], 0
    for index in range(1, len(levels) + 1):
        if index == len(levels) or (levels[index] >= split) != (levels[start] >= split):
            runs.append((start, index - start))
            start = index
    widths = [length for offset, length in runs if offset > 0 and offset + length < len(levels)]
    require(len(widths) >= 2, f"{png}: not enough whole tiles in view: runs {runs}")
    return sorted(widths)[len(widths) // 2]


def case_overmap(session):
    """Click the drawn cursor on partial-tile viewports without shifting the map."""
    state_path = session.curses_userdir / "save" / session.world / "uistate.json"
    state = json.loads(state_path.read_text())
    state["overmap_blinking"] = False
    state["overmap_show_overlays"] = True
    state_path.write_text(json.dumps(state))
    checks, observations = [], {}
    for scale, columns, rows in ((1, 166, 60), (2, 90, 30)):
        label = f"overmap-{scale}x"
        options = {
            "CONTROL_SCHEME": "modern", "SCALING_FACTOR": str(scale),
            "FONT_WIDTH": "8", "FONT_HEIGHT": "16", "FONT_SIZE": "16",
            "TERMINAL_X": str(columns * scale), "TERMINAL_Y": str(rows * scale),
            "USE_TILES_OVERMAP": "true", "OVERMAP_TILES": "UNDEAD_PEOPLE_BASE",
            "EDGE_SCROLL": "-1", "CURSOR_PANNING": "false",
        }
        with session.running_game(label, options) as live:
            x11 = X11(session.display)
            try:
                window = x11.find_window(WINDOW_TITLE_PREFIX)
                require(window is not None, f"{label}: window disappeared")

                def settled(name, reference=None):
                    previous = None
                    deadline = time.time() + session.timeout
                    while time.time() < deadline:
                        require(live.proc.poll() is None, f"{label}: game exited")
                        png = capture(session.display, window, session.artifacts / f"{label}-{name}.png")
                        frame = frame_rgb(png)
                        if frame == previous and (reference is None or frame != reference):
                            return frame
                        previous = frame
                        time.sleep(0.3)
                    raise Failure(f"{label}: {name} did not settle")

                world = frame_rgb(live.frame)
                width, height, _ = world
                require((width, height) == (columns * 8 * scale, rows * 16 * scale),
                        f"{label}: unexpected window dimensions {width}x{height}")
                x11.focus_local(window, width // 3, height // 2)
                x11.key("m")
                before = settled("before", reference=world)
                legend = min(55, max(28, columns // 5))
                map_width = (columns - legend) * 8 * scale
                tile = 32 * scale
                center_x = ((map_width + tile - 1) // tile // 2) * tile + tile // 2
                center_y = ((height + tile - 1) // tile // 2) * tile + tile // 2
                x11.focus_local(window, center_x, center_y)
                x11.click(1)
                clicked = settled("clicked")
                # A later popup acknowledges the click before the no-change assertion.
                x11.key("Shift_L", "n")
                settled("note-popup", reference=clicked)
                x11.key("Escape")
                after = settled("after")
                changed = sum(before[2][i:i + 3] != after[2][i:i + 3]
                              for i in range(0, len(before[2]), 3))
                checks.append(Check(f"{scale}x cursor click does not pan",
                                    changed == 0, f"{changed} pixels changed"))
                # Right-drag pans the map with the pointer.
                x11.drag(window, (center_x, center_y), (center_x + 2 * tile, center_y + tile))
                dragged = settled("dragged", reference=after)
                panned = sum(before[2][i:i + 3] != dragged[2][i:i + 3]
                             for i in range(0, len(before[2]), 3))
                checks.append(Check(f"{scale}x right-drag pans the overmap",
                                    panned > 0, f"{panned} pixels changed"))
                x11.key("m")
                returned = wait_for_frame(session, live.proc, live.run, session.timeout)
                checks.append(Check(f"{scale}x m closes the overmap",
                                    frame_shows_world(frame_rgb(returned)), str(returned)))
                observations[label] = {"cursor": [center_x, center_y], "changed_pixels": changed}
            finally:
                x11.close()
    return [check.detail for check in checks if not check.ok], {
        "checks": [check.__dict__ for check in checks], "views": observations,
    }


def case_zoom(session):
    """Default keyboard and wheel zoom change the rendered tile pitch and spend no turn."""
    bindings = session.curses_userdir / "config" / "keybindings.json"
    rows = json.loads(bindings.read_text()) if bindings.exists() else []
    rows = [row for row in rows if not (row.get("category") == "DEFAULTMODE"
                                      and row.get("id") == "quicksave")]
    rows.append({"type": "keybinding", "id": "quicksave", "category": "DEFAULTMODE",
                 "bindings": [{"input_method": "keyboard", "key": "F6"}]})
    # Modern leaves the full look screen unbound; bind it so the case can open it by key.
    rows.append({"type": "keybinding", "id": "look", "category": "DEFAULTMODE",
                 "bindings": [{"input_method": "keyboard", "key": ";"}]})
    bindings.write_text(json.dumps(rows))
    source = session.curses_userdir / "save" / session.world
    starts = list(source.glob("*.sav"))
    require(len(starts) == 1, f"zoom: expected one character save in {source}, got {starts}")
    initial_turn = saved_turn(starts[0])
    options = {
        "CONTROL_SCHEME": "modern", "ZOOM_STEP_COUNT": "1",
        "SCALING_FACTOR": "1", "FONT_WIDTH": str(ZOOM_FONT_WIDTH), "FONT_HEIGHT": "16",
        "FONT_SIZE": "16", "TILES": "UNDEAD_PEOPLE_BASE",
        "TERMINAL_X": "160", "TERMINAL_Y": "60", "SIDEBAR_POSITION": "right",
        "MOUSE_MOVE": "false",
    }
    checks, pitches, frames = [], {}, {}
    final_turn = None
    with session.running_game("zoom", options) as live:
        x11 = X11(session.display)
        try:
            win = x11.find_window(WINDOW_TITLE_PREFIX)
            require(win is not None, "zoom: game window disappeared")
            width, height, _ = frame_rgb(live.frame)
            terrain_width = width - ZOOM_SIDEBAR_CELLS * ZOOM_FONT_WIDTH
            require(terrain_width >= 640, f"zoom: terrain too narrow ({terrain_width}px)")
            x11.focus_local(win, terrain_width // 2, height // 2)

            def observe(label):
                wait_for_frame(session, live.proc, live.run, session.timeout)
                png = capture(session.display, win, session.artifacts / f"zoom-{label}.png")
                frames[label] = str(png)
                w, h, _ = frame_rgb(png)
                require((w, h) == (width, height), f"zoom: {label} changed the window size")
                pitches[label] = tile_pitch(png, terrain_width, height * 3 // 4)
                return pitches[label]

            def snapshot(label):
                """Captures a frame without measuring pitch; the far zoom is too dense to measure."""
                wait_for_frame(session, live.proc, live.run, session.timeout)
                png = capture(session.display, win, session.artifacts / f"zoom-{label}.png")
                frames[label] = str(png)
                return png

            initial = observe("initial")
            x11.key("equal")
            zoomed = observe("keyboard-in")
            x11.key("minus")
            restored = observe("keyboard-out")
            x11.key("Shift_L", "equal")
            plus_zoomed = observe("keyboard-plus")
            x11.key("minus")
            plus_restored = observe("keyboard-plus-out")
            x11.click(4)
            wheel_zoomed = observe("wheel-in")
            x11.click(5)
            wheel_restored = observe("wheel-out")

            # Zoom must work while looking: first the modern reticle, then the full look screen.
            x11.key("Shift_L", "d")
            reticle = observe("reticle")
            x11.key("equal")
            reticle_in = observe("reticle-zoom-in")
            x11.key("minus")
            observe("reticle-zoom-out")
            # Escape opens the main menu in the tiles build, so close it before opening look.
            x11.key("Escape")
            x11.key("Escape")
            map_frame_label = "map-after-reticle"
            map_frame = observe(map_frame_label)
            x11.key("semicolon", delay=0.5)
            look = observe("look")
            require(Path(frames["look"]).read_bytes() != Path(frames[map_frame_label]).read_bytes(),
                    "look: the look screen never opened")
            x11.key("equal")
            look_in = observe("look-zoom-in")
            x11.key("minus")
            look_out = observe("look-zoom-out")
            x11.key("Escape", delay=0.5)

            save = next((live.run / "userdir" / "save" / session.world).glob("*.sav"), None)
            require(save is not None, "zoom: running copy has no character save")
            stamp = save.stat().st_mtime_ns
            x11.key("F6", delay=0.5)
            deadline = time.time() + 30
            while save.stat().st_mtime_ns == stamp and time.time() < deadline:
                time.sleep(0.2)
            require(save.stat().st_mtime_ns != stamp, "zoom: quicksave did not write the save")
            final_turn = saved_turn(save)
            # Zoom stops at its ends: winding past the last step must not jump to the other end.
            for _ in range(8):
                x11.key("equal", delay=0.05)
            at_max = snapshot("zoom-max")
            x11.key("equal", delay=0.1)
            still_max = snapshot("zoom-max-plus")
            same_max = at_max.read_bytes() == still_max.read_bytes()
            for _ in range(8):
                x11.key("minus", delay=0.05)
            at_min = snapshot("zoom-min")
            x11.key("minus", delay=0.1)
            still_min = snapshot("zoom-min-minus")
            same_min = at_min.read_bytes() == still_min.read_bytes()

            # Clamp at the far end, walk back to 1x deterministically, then one step to 2x.
            for _ in range(8):
                x11.key("minus", delay=0.05)
            for _ in range(2):
                x11.key("equal", delay=0.1)
            observe("persist-1x")
            x11.key("equal", delay=0.2)
            observe("persist-2x")
            zoom_file = live.run / "xdg" / "cataclysm-bn" / "tileset_zoom"
            require(zoom_file.exists(), f"zoom: preference file was not written at {zoom_file}")
            checks.extend([
                Check("keyboard zoom in doubles the tile pitch", abs(zoomed / initial - 2) <= 0.2,
                      f"{initial}px -> {zoomed}px"),
                Check("keyboard zoom out restores the tile pitch", abs(restored / initial - 1) <= 0.05,
                      f"{initial}px -> {restored}px"),
                Check("shifted plus zooms in", abs(plus_zoomed / initial - 2) <= 0.2,
                      f"{initial}px -> {plus_zoomed}px"),
                Check("minus restores after shifted plus", abs(plus_restored / initial - 1) <= 0.05,
                      f"{initial}px -> {plus_restored}px"),
                Check("mouse wheel zoom in doubles the tile pitch", abs(wheel_zoomed / initial - 2) <= 0.2,
                      f"{initial}px -> {wheel_zoomed}px"),
                Check("mouse wheel zoom out restores the tile pitch",
                      abs(wheel_restored / initial - 1) <= 0.05,
                      f"{initial}px -> {wheel_restored}px"),
                Check("the reticle view zooms in", abs(reticle_in / reticle - 2) <= 0.3,
                      f"{reticle}px -> {reticle_in}px"),
                Check("the look screen zooms in", abs(look_in / look - 2) <= 0.3,
                      f"{look}px -> {look_in}px"),
                Check("the look screen zooms back out", abs(look_out / look - 1) <= 0.1,
                      f"{look}px -> {look_out}px"),
                Check("zoom stops at the closest level", same_max,
                      "the frame changed after the last zoom step"),
                Check("zoom stops at the farthest level", same_min,
                      "the frame changed after the last zoom step"),
                Check("the two ends differ", at_min.read_bytes() != at_max.read_bytes(),
                      "the closest and farthest frames are identical"),
                Check("zoom spends no turn", final_turn == initial_turn,
                      f"turn {initial_turn} -> {final_turn}"),
            ])
        finally:
            x11.close()
    # A relaunch over the same config directory must come back at the zoom it left.
    with session.running_game("zoom", options, fresh=False) as live:
        x11 = X11(session.display)
        try:
            win = x11.find_window(WINDOW_TITLE_PREFIX)
            require(win is not None, "zoom: relaunch window disappeared")
            wait_for_frame(session, live.proc, live.run, session.timeout)
            png = capture(session.display, win, session.artifacts / "zoom-relaunch.png")
            frames["relaunch"] = str(png)
            relaunch = tile_pitch(png, terrain_width, height * 3 // 4)
            checks.append(Check("the zoom chosen last session is restored",
                                abs(relaunch / initial - 2) <= 0.2,
                                f"{initial}px default -> {relaunch}px relaunch"))
        finally:
            x11.close()

    failures = [f"{check.name}: {check.detail}" for check in checks if not check.ok]
    return failures, {"checks": [check.__dict__ for check in checks], "pitches": pitches,
                      "initial_turn": initial_turn, "final_turn": final_turn, "frames": frames}


def case_known_locks(session):
    """Only a door found locked gets a marker, at either display scale."""
    from known_locks import (analyse_known_lock_icons,
                             test_lock_icon_option_follows_the_control_scheme)

    failures, observations = [], {}
    for scale, columns, rows in ((1, 160, 60), (2, 96, 30)):
        label = f"known-locks-{scale}x"
        options = {
            "CONTROL_SCHEME": "modern", "SCALING_FACTOR": str(scale),
            "FONT_WIDTH": "8", "FONT_HEIGHT": "16", "FONT_SIZE": "16",
            "TERMINAL_X": str(columns * scale), "TERMINAL_Y": str(rows * scale),
            "TILES": "UNDEAD_PEOPLE_BASE", "SIDEBAR_POSITION": "right",
            "MOUSE_MOVE": "false", "CURSOR_PANNING": "false",
        }
        off = session.launch(f"{label}-off", {**options, "KNOWN_LOCKED_DOOR_ICONS": "false"})
        on = session.launch(f"{label}-on", {**options, "KNOWN_LOCKED_DOOR_ICONS": "true"})
        width, height, _ = frame_rgb(off)
        require((width, height) == (columns * 8 * scale, rows * 16 * scale),
                f"{label}: unexpected window dimensions {width}x{height}")
        tile = 32 * scale
        terrain_width = width - ZOOM_SIDEBAR_CELLS * ZOOM_FONT_WIDTH * scale
        avatar_x = terrain_width // tile // 2 * tile
        avatar_y = height // tile // 2 * tile

        def tile_rect(dx, dy):
            x, y = avatar_x + dx * tile, avatar_y + dy * tile
            return x, y, x + tile, y + tile

        attempted, untried = tile_rect(1, 0), tile_rect(0, -1)
        crops = session.artifacts / label
        crops.mkdir()
        checks = analyse_known_lock_icons(off, on, attempted, untried, crops)
        failures.extend(f"{label}: {check.name}: {check.detail}" for check in checks if not check.ok)
        observations[label] = {
            "attempted_tile": attempted, "untried_tile": untried,
            "checks": [check.__dict__ for check in checks],
        }
        if scale == 1:
            defaults, report = test_lock_icon_option_follows_the_control_scheme(
                session, options, attempted, off, on)
            failures.extend(f"scheme defaults: {check.name}: {check.detail}"
                            for check in defaults if not check.ok)
            observations["scheme_defaults"] = {
                "checks": [check.__dict__ for check in defaults], "schemes": report}
    return failures, observations


def case_sound_menu(session):
    """Drive the tiles menu; check saved settings, not audible output or OCR."""
    bindings = session.curses_userdir / "config" / "keybindings.json"
    rows = json.loads(bindings.read_text()) if bindings.exists() else []
    rows = [row for row in rows if not (row.get("category") == "DEFAULTMODE"
                                      and row.get("id") == "sound_menu")]
    rows.append({"type": "keybinding", "id": "sound_menu", "category": "DEFAULTMODE",
                 "bindings": [{"input_method": "keyboard", "key": "F7"}]})
    bindings.write_text(json.dumps(rows))
    options = {"CONTROL_SCHEME": "modern", "SOUND_ENABLED": "true",
               "MUSIC_VOLUME": "64", "SOUND_EFFECT_VOLUME": "64", "AMBIENT_SOUND_VOLUME": "64"}
    observations = {}
    with session.running_game("sound-menu", options) as live:
        paths = (live.run / "userdir" / "config" / "options.json",
                 live.run / "xdg" / "cataclysm-bn" / "options.json")
        saved_path = None
        x11 = X11(session.display)
        try:
            window = x11.find_window(WINDOW_TITLE_PREFIX)
            require(window is not None, "sound menu: game window disappeared")
            x11.focus_local(window, 0, 0)

            def open_menu(label):
                x11.key("F7")
                wait_for_frame(session, live.proc, live.run, session.timeout)
                capture(session.display, window, session.artifacts / f"sound-menu-{label}.png")

            def saved_values(expected):
                nonlocal saved_path
                deadline = time.monotonic() + 15
                last = {}
                while time.monotonic() < deadline:
                    for path in (saved_path,) if saved_path else paths:
                        try:
                            values = {row["name"]: row["value"] for row in json.loads(path.read_text())}
                        except (FileNotFoundError, json.JSONDecodeError):
                            continue
                        last[str(path)] = {name: values.get(name) for name in expected}
                        if all(values.get(name) == value for name, value in expected.items()):
                            saved_path = path
                            return {name: values[name] for name in expected}
                    time.sleep(0.1)
                raise AssertionError(f"sound menu did not persist {expected}: {last}")

            # Leave MUSIC_ENABLED unpatched: the first save also checks its true default.
            open_menu("initial")
            x11.key("Left")
            x11.key("Escape")
            initial = {**options, "SOUND_ENABLED": "false", "MUSIC_ENABLED": "true"}
            observations["sound_off"] = saved_values(initial)

            open_menu("sound-off")
            x11.key("Right")
            x11.key("Down")
            x11.key("Return")
            for _ in range(3):
                x11.key("Down")
                x11.key("Right")
            x11.key("Escape")
            changed = {**options, "MUSIC_ENABLED": "false", "MUSIC_VOLUME": "72",
                       "SOUND_EFFECT_VOLUME": "72", "AMBIENT_SOUND_VOLUME": "72"}
            observations["music_off_volumes_raised"] = saved_values(changed)

            open_menu("changed")
            x11.key("Down")
            x11.key("Return")
            for _ in range(3):
                x11.key("Down")
                x11.key("Left")
            x11.key("Escape")
            observations["restored"] = saved_values({**options, "MUSIC_ENABLED": "true"})
        finally:
            x11.close()
    return [], observations


CASES = {"minimap": case_minimap, "mouse": case_mouse, "sound_menu": case_sound_menu,
         "zoom": case_zoom, "overmap": case_overmap, "known_locks": case_known_locks}


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
        if args.case == "known_locks":
            from known_locks import build_known_lock_world
            build_known_lock_world(session)
        else:
            session.build_world(zoom_ruler=args.case == "zoom")
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
