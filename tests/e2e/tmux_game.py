"""Drives the curses build inside a detached tmux session."""
import curses
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def find_binary():
    for candidate in (
        ROOT / "cataclysm-bn",
        ROOT / "out/build/linux-curses/src/cataclysm-bn",
        ROOT / "build/src/cataclysm-bn",
    ):
        if candidate.exists():
            return candidate
    raise SystemExit("cataclysm-bn binary not found; build the curses target first")


class Game:
    def __init__(self, name="bn-e2e", cols=140, rows=45, options=None, keybindings=None,
                 userdir=None, layout="labels"):
        # Sessions from two processes must not collide: local parallel shards run at once.
        self.name = f"{name}-{os.getpid()}"
        self.userdir = Path(userdir) if userdir else Path(tempfile.mkdtemp(prefix="bn-e2e-"))
        config = self.userdir / "config"
        config.mkdir(parents=True, exist_ok=True)
        # Legacy HUD contracts are explicit fixtures, not assumptions about the fresh-user default.
        # A caller's saved panel layout always wins; layout=None exercises the real fresh default.
        panels = config / "panel_options.json"
        if layout is not None and not panels.exists():
            panels.write_text(json.dumps([{"current_layout_id": layout, "layouts": []}]))
        if options:
            (config / "options.json").write_text(json.dumps(
                [{"info": "", "default": "", "name": k, "value": v} for k, v in options.items()]))
        if keybindings:
            (config / "keybindings.json").write_text((ROOT / keybindings).read_text())
        subprocess.run(["tmux", "kill-session", "-t", self.name], stderr=subprocess.DEVNULL)
        # Wiki and guide keys open a URL; a stub opener keeps the browser off the desktop.
        stub_bin = self.userdir / "bin"
        stub_bin.mkdir(exist_ok=True)
        (stub_bin / "xdg-open").write_text("#!/bin/sh\nexit 0\n")
        (stub_bin / "xdg-open").chmod(0o755)
        env = f"PATH={stub_bin}:$PATH BROWSER=true LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=xterm-256color"
        cmd = f"cd {ROOT} && env -u DISPLAY -u WAYLAND_DISPLAY {env} {os.environ.get('GAME_WRAPPER', '')} {find_binary()} --basepath {ROOT}/ --userdir {self.userdir}/"
        subprocess.run(["tmux", "new-session", "-d", "-s", self.name, "-x", str(cols), "-y", str(rows), cmd], check=True)

    def screen(self):
        return subprocess.run(["tmux", "capture-pane", "-p", "-t", self.name],
                              capture_output=True, text=True, check=True).stdout

    def resize(self, cols, rows):
        """Force the pane size: tmux sizes new windows from the server, not only from -x/-y."""
        subprocess.run(["tmux", "resize-window", "-t", self.name,
                        "-x", str(cols), "-y", str(rows)], check=True)

    def screen_colors(self):
        return subprocess.run(["tmux", "capture-pane", "-p", "-e", "-t", self.name],
                              capture_output=True, text=True, check=True).stdout

    def keys(self, *keys, delay=0.25):
        for k in keys:
            if k == "Home":
                # tmux's Home sequence differs from xterm's terminfo.
                curses.setupterm(term="xterm-256color")
                code = curses.tigetstr("khome")
                subprocess.run(["tmux", "send-keys", "-H", "-t", self.name, "--",
                                *(f"{byte:02x}" for byte in code)], check=True)
            else:
                subprocess.run(["tmux", "send-keys", "-t", self.name, "--", k], check=True)
            time.sleep(delay)

    def type(self, text, delay=0.05):
        # The game drops identical keys that arrive together, so split runs of repeated characters.
        # Long lines also arrive in chunks: a busy frame can otherwise swallow their middle.
        chunk = ""
        for ch in text:
            if chunk and (chunk[-1] == ch or len(chunk) >= 24):
                subprocess.run(["tmux", "send-keys", "-t", self.name, "-l", "--", chunk], check=True)
                time.sleep(0.08 if chunk[-1] == ch else 0.02)
                chunk = ""
            chunk += ch
        subprocess.run(["tmux", "send-keys", "-t", self.name, "-l", "--", chunk], check=True)
        time.sleep(delay)

    def click(self, x, y, button=0):
        """Mouse click at a screen cell, SGR (1006) encoded as xterm-256color terminfo expects.

        Preserve the one-second observation window; wait longer if the redraw is still changing.
        """
        for suffix in ("M", "m"):
            subprocess.run(["tmux", "send-keys", "-t", self.name, "-l", "--", f"\x1b[<{button};{x + 1};{y + 1}{suffix}"], check=True)
            time.sleep(0.05)
        self.settle_screen(minimum=1.0, timeout=1.5)

    def double_click(self, x, y, button=0):
        """Two clicks inside the terminal's double-click interval, as a person double-clicks."""
        for _ in range(2):
            for suffix in ("M", "m"):
                subprocess.run(["tmux", "send-keys", "-t", self.name, "-l", "--", f"\x1b[<{button};{x + 1};{y + 1}{suffix}"], check=True)
                time.sleep(0.02)
        self.settle_screen(minimum=1.0, timeout=1.5)

    def hover(self, x, y):
        """Mouse motion with no button held, SGR encoded (button code 35).

        The second of stillness is the pan itself: while the cursor stays in an edge zone the
        game keeps panning on its timeouts, so the tests count steps per hover.
        """
        subprocess.run(["tmux", "send-keys", "-t", self.name, "-l", "--", f"\x1b[<35;{x + 1};{y + 1}M"], check=True)
        time.sleep(1)

    def find(self, ch):
        for y, line in enumerate(self.screen().splitlines()):
            if ch in line[:95]:
                return line.index(ch), y
        return None

    def wait_for(self, text, timeout=60, poll=0.05):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if text in self.screen():
                return True
            time.sleep(poll)
        raise AssertionError(f"timed out waiting for {text!r}\n{self.screen()}")

    def wait_gone(self, text, timeout=60, poll=0.05):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if text not in self.screen():
                return True
            time.sleep(poll)
        raise AssertionError(f"timed out waiting for {text!r} to go away\n{self.screen()}")

    def settle_screen(self, minimum=0.3, timeout=2.0):
        """Returns once two consecutive captures match and `minimum` seconds have passed."""
        started = time.time()
        previous = self.screen()
        while time.time() - started < timeout:
            time.sleep(0.05)
            current = self.screen()
            if current == previous and time.time() - started >= minimum:
                return True
            previous = current
        return False

    def dismiss_error_popup(self):
        """Answer a debug assertion popup, which blocks every key until it is answered.

        The CI build keeps debug assertions on, so a game-side debugmsg stalls the harness
        mid-test. The text is reported rather than swallowed, and the keypress resumes play.
        """
        screen = self.screen()
        if "An error has occurred!" not in screen:
            return False
        detail = [l.strip() for l in screen.splitlines() if "DEBUG" in l or "FUNCTION" in l][:2]
        print("debug assertion popup, answering it to continue: " + " | ".join(detail),
              file=sys.stderr)
        self.keys("Space", delay=0.1)
        try:
            self.wait_gone("An error has occurred!", timeout=5)
        except AssertionError:
            # The title can linger in the message log after the modal closes; the next
            # screen read shows whether the game is still blocked.
            print("the error popup title did not clear", file=sys.stderr)
        return True

    def lua(self, code, _retried=False):
        """Runs one line in the in-game Lua console; `out(...)` reports values back."""
        try:
            return self._lua(code)
        except AssertionError as err:
            # A fresh game can still be handing over the avatar when the fixture runs, which
            # makes `gapi.get_avatar()` nil. Only that case is retried, after a settle.
            if _retried or "attempt to call a nil value" not in str(err):
                raise
            helpers = getattr(self, "_helper_src", "")
            helper_names = set(re.findall(r"function (\w+)", helpers))
            # A definition call carries "function out("; restoring from inside it would recurse.
            lost_helper = "function out(" not in code and any(
                f"{name}(" in code for name in helper_names)
            if "gapi.get_avatar()" not in code and not lost_helper:
                raise
            time.sleep(0.5)
            self.settle_screen()
            if lost_helper:
                # A pooled game can reload its Lua state and lose the helpers; restore them.
                self.define_lua(helpers)
            return self.lua(code, _retried=True)

    def _lua(self, code):
        self.calls = getattr(self, "calls", 0) + 1
        marker = f"#{os.getpid()}.{self.calls}#"
        data_prefix = marker + "V:"
        done_marker = marker + "END"
        prompt = "Press Enter to enter/edit command"
        editing = "Press Ctrl+S to run script"

        for _ in range(3):
            self.dismiss_error_popup()
            self.keys("`", delay=0)
            try:
                self.wait_for(prompt, timeout=15)
                break
            except AssertionError:
                self.keys("Escape", delay=0)
        else:
            raise AssertionError("could not open the Lua console; refusing to type code into the game\n" + self.screen())

        self.keys("Enter", delay=0)
        # Wait for editor ownership before sending source.
        self.wait_for(editing, timeout=15)
        # `out` is defined per call: a pooled game that reloaded its Lua state may have lost it.
        self.type(f"OUT='{marker}' function out(...) local t={{}} for i,v in ipairs({{...}}) do "
                  f"t[i]=tostring(v) end print(OUT..'V:'..table.concat(t,',')) end "
                  + code + f" print('{done_marker}')")
        self.keys("C-s", delay=0)

        def capture(screen):
            lines = [line.strip("│^v ").strip() for line in screen.splitlines()]
            values = [line[len(data_prefix):] for line in lines if line.startswith(data_prefix)]
            errors = [line.strip() for line in screen.splitlines()
                      if "Runtime error:" in line or "Failed to load:" in line]
            return lines, values, errors

        deadline = time.time() + 20
        last_screen = ""
        completed = False
        while time.time() < deadline:
            last_screen = self.screen()
            lines, found, errors = capture(last_screen)
            if done_marker in lines and prompt in last_screen:
                completed = True
                break
            time.sleep(0.05)

        def close_console():
            screen = self.screen()
            if editing in screen:
                self.keys("Escape", delay=0)
                self.wait_for(prompt, timeout=15)
            elif prompt not in screen:
                return False
            self.keys("Escape", delay=0)
            self.wait_gone(prompt, timeout=15)
            return True

        if not completed:
            lines, found, errors = capture(last_screen or self.screen())
            details = "\n".join(errors) if errors else "No Lua runtime or load error was visible."
            close_console()
            reason = "Lua console returned to its prompt without the completion marker."
            if prompt not in last_screen:
                reason = "Lua console did not finish within 20 seconds."
            raise AssertionError(
                f"{reason} Outputs received: {found!r}. {details}"
            )

        close_console()
        return found

    def define_lua(self, code):
        """Defines globals once; later `lua` calls can stay short."""
        prelude = ("function out(...) local t = {} for i, v in ipairs({...}) do t[i] = tostring(v) end "
                   "print(OUT .. 'V:' .. table.concat(t, ',')) end ")
        self._helper_prelude, self._helper_src = prelude, code
        # Long lines can lose characters under load; prove every helper exists before trusting them.
        names = re.findall(r"function (\w+)", code)
        probe = " ".join(f"assert(type({name}) == 'function', '{name}')" for name in names)
        last = ""
        for _ in range(3):
            try:
                result = self.lua(prelude + code + " " + probe + " out('defined')")
            except AssertionError as err:
                last = str(err)
                continue
            if result == ["defined"]:
                return
            last = f"Lua helper definition returned {result!r}"
        raise AssertionError(f"{last}\n{self.screen()}")

    def pos(self):
        line = next(l for l in self.screen().splitlines() if "X,Y,Z:" in l)
        return tuple(int(v) for v in line.split("X,Y,Z:")[1].split()[0:3] for v in [v.strip(",")])

    def close(self):
        subprocess.run(["tmux", "kill-session", "-t", self.name], stderr=subprocess.DEVNULL)
        shutil.rmtree(self.userdir, ignore_errors=True)


def in_game(screen):
    # Small terminals can cut off Controls; classic uses Location and stamina instead of coordinates.
    # The limb bars are the one reading every layout and panel subset keeps.
    return (("X,Y,Z" in screen and (" move " in screen or "Place :" in screen))
            or ("Location:" in screen and "Stm" in screen)
            or ("HEAD" in screen and "TORSO" in screen))


def start_new_game(game, timeout=240):
    """Language prompt -> New Game -> Play Now (default scenario) -> world -> in game.

    Each branch reads the screen again, so a late or doubled key only costs one pass. The title
    menu is walked by what it shows: RIGHT switches tabs until the New Game sub-items appear and
    DOWN then moves inside that tab. Blind DOWN presses would instead scroll whichever tab is
    open, and the game can be left on the Load tab by a stray confirm.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = game.screen()
        # The title menu draws over the last game frame, so its markers come first: the stale
        # HEAD/TORSO pixels below it would otherwise pass for being in game.
        if "Are you SURE" in s:
            # A confirmation is cancelled, never answered: answering a quit prompt leaves the
            # game on the title menu with no save.
            game.keys("Escape", delay=1)
            continue
        if "Welcome to Bright Nights" in s:
            game.saw_welcome = True
            game.welcome_screen = s
            game.keys("Escape", delay=1)
            continue
        if "How should death work" in s:
            game.saw_death_choice = True
            game.keys("r", delay=1)
            continue
        if "[New Game]" in s or "Play Now!  (Default Scenario)" in s:
            if "Play Now!  (Default Scenario)" not in s:
                # RIGHT walks the tab strip and wraps, so the New Game tab comes back around.
                game.keys("Down" if "Custom Character" in s else "Right", delay=0.6)
            else:
                line = next((l for l in s.splitlines() if "Play Now!  (Default Scenario)" in l), "")
                game.keys("Enter" if "»" in line else "Down", delay=1)
        elif in_game(s):
            return
        elif "Select your language" in s:
            game.keys("1")
        elif "Finalize World" in s and "World Name" in s:
            game.keys("Tab", delay=1)
        elif "World Mods" in s:
            game.keys("Tab", "Tab", delay=0.6)
        elif not s.strip():
            # The first frame only shows up after some input.
            game.keys("F5", delay=1)
        else:
            time.sleep(0.5)
    raise AssertionError("never reached the game\n" + game.screen())
