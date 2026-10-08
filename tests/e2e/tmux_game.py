"""Drives the curses build inside a detached tmux session."""
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def find_binary():
    for candidate in (ROOT / "cataclysm-bn", ROOT / "build" / "src" / "cataclysm-bn"):
        if candidate.exists():
            return candidate
    raise SystemExit("cataclysm-bn binary not found; build the curses target first")


class Game:
    def __init__(self, name="bn-e2e", cols=140, rows=45, options=None):
        self.name = name
        self.userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-"))
        config = self.userdir / "config"
        config.mkdir(parents=True)
        if options:
            import json
            (config / "options.json").write_text(json.dumps(
                [{"info": "", "default": "", "name": k, "value": v} for k, v in options.items()]))
        subprocess.run(["tmux", "kill-session", "-t", name], stderr=subprocess.DEVNULL)
        cmd = f"cd {ROOT} && LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=xterm-256color {os.environ.get('GAME_WRAPPER', '')} {find_binary()} --basepath {ROOT}/ --userdir {self.userdir}/"
        subprocess.run(["tmux", "new-session", "-d", "-s", name, "-x", str(cols), "-y", str(rows), cmd], check=True)

    def screen(self):
        return subprocess.run(["tmux", "capture-pane", "-p", "-t", self.name],
                              capture_output=True, text=True).stdout

    def screen_colors(self):
        return subprocess.run(["tmux", "capture-pane", "-p", "-e", "-t", self.name],
                              capture_output=True, text=True).stdout

    def keys(self, *keys, delay=0.25):
        for k in keys:
            subprocess.run(["tmux", "send-keys", "-t", self.name, k])
            time.sleep(delay)

    def type(self, text, delay=0.05):
        # The game drops identical keys that arrive together, so split runs of repeated characters.
        chunk = ""
        for ch in text:
            if chunk and chunk[-1] == ch:
                subprocess.run(["tmux", "send-keys", "-t", self.name, "-l", chunk])
                time.sleep(0.08)
                chunk = ""
            chunk += ch
        subprocess.run(["tmux", "send-keys", "-t", self.name, "-l", chunk])
        time.sleep(delay)

    def wait_for(self, text, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if text in self.screen():
                return True
            time.sleep(0.3)
        raise AssertionError(f"timed out waiting for {text!r}\n{self.screen()}")

    def lua(self, code):
        """Runs one line in the in-game Lua console; `out(...)` inside it reports values back."""
        self.calls = getattr(self, "calls", 0) + 1
        marker = f"#{os.getpid()}.{self.calls}#"
        self.keys("`", delay=1)
        self.keys("Enter", delay=0.5)
        # Keep the echoed command short so its output is still on screen afterwards.
        self.type(f"OUT='{marker}' " + code)
        self.keys("C-s", delay=1.5)
        lines = [l.strip("│^v ").strip() for l in self.screen().splitlines()]
        self.keys("Escape", delay=0.8)
        return [l[len(marker):] for l in lines if l.startswith(marker)]

    def define_lua(self, code):
        """Defines globals once; later `lua` calls can stay short."""
        prelude = ("function out(...) local t = {} for i, v in ipairs({...}) do t[i] = tostring(v) end "
                   "print(OUT .. table.concat(t, ',')) end ")
        assert self.lua(prelude + code + " out('defined')") == ["defined"], self.screen()

    def pos(self):
        line = next(l for l in self.screen().splitlines() if "X,Y,Z:" in l)
        return tuple(int(v) for v in line.split("X,Y,Z:")[1].split()[0:3] for v in [v.strip(",")])

    def close(self):
        subprocess.run(["tmux", "kill-session", "-t", self.name], stderr=subprocess.DEVNULL)
        shutil.rmtree(self.userdir, ignore_errors=True)


def in_game(screen):
    return "X,Y,Z:" in screen and "wasd move" in screen


def start_new_game(game, timeout=240):
    """Language prompt -> New Game -> Play Now (default scenario) -> world -> in game."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = game.screen()
        if "Welcome to Bright Nights" in s:
            game.saw_welcome = True
            game.welcome_screen = s
            game.keys("Escape", delay=1)
            continue
        if in_game(s) and "Are you SURE" not in s:
            return
        if "Select your language" in s:
            game.keys("1")
        elif "Are you SURE" in s:
            game.keys("Y", delay=1)
        elif "Finalize World" in s and "World Name" in s:
            game.keys("Tab", delay=1)
        elif "World Mods" in s:
            game.keys("Tab", "Tab", delay=0.6)
        elif "Play Now!  (Default Scenario)" in s:
            line = next((l for l in s.splitlines() if "»" in l), "")
            if "Play Now!  (Default Scenario)" in line:
                game.keys("Enter", delay=1)
            else:
                game.keys("Down")
        elif "[New Game]" in s:
            line = next((l for l in s.splitlines() if "[New Game]" in l), "")
            game.keys("Down")
        elif not s.strip():
            # The first frame only shows up after some input.
            game.keys("F5", delay=1)
        else:
            time.sleep(0.5)
    raise AssertionError("never reached the game\n" + game.screen())
