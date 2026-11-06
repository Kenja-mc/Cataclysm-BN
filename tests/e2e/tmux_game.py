import atexit
import curses
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TMUX_TIMEOUT = 5
START_TIMEOUT = 60

_owned = set()
_orphan_userdirs = set()
_starting = {}
_shutdown_hooks = []
_cleanup_hooks = []
_handling_signal = None


def _target(name):
    return f"={name}:"


def _kill_session(name):
    try:
        return subprocess.run(["tmux", "kill-session", "-t", _target(name)],
                              stderr=subprocess.DEVNULL, timeout=TMUX_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _session_exists(name):
    try:
        return subprocess.run(["tmux", "has-session", "-t", _target(name)],
                              stderr=subprocess.DEVNULL,
                              timeout=TMUX_TIMEOUT).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return True


def _close_starting_sessions(grace=3.0):
    deadline = time.time() + grace
    seen = set()
    while True:
        for name, client in tuple(_starting.items()):
            if client is not None:
                seen.add(name)
                _stop_pid(client[0], 1.0, client[1])
            found = _new_session_client_pids(name)
            for pid, started in found:
                _stop_pid(pid, 1.0, started)
            if found:
                seen.add(name)
                if _starting.get(name) is None:
                    _starting[name] = found[0]
            _kill_session(name)
            if name in seen and not _session_exists(name) and not _new_session_client_pids(name):
                _starting.pop(name, None)
        if not _starting:
            return
        if time.time() >= deadline:
            for _ in range(2):
                for name in tuple(_starting):
                    for pid, started in _new_session_client_pids(name):
                        _stop_pid(pid, 0.5, started)
                    _kill_session(name)
                time.sleep(0.05)
            for name in tuple(_starting):
                _starting.pop(name, None)
            return
        time.sleep(0.05)


def on_shutdown(hook):
    _shutdown_hooks.append(hook)
    return hook


def remove_shutdown_hook(hook):
    if hook in _shutdown_hooks:
        _shutdown_hooks.remove(hook)


def on_cleanup(hook):
    _cleanup_hooks.append(hook)
    return hook


def remove_cleanup_hook(hook):
    if hook in _cleanup_hooks:
        _cleanup_hooks.remove(hook)


def close_owned_games():
    if os.environ.get("BN_E2E_KEEP"):
        return
    try:
        _close_starting_sessions()
    except Exception as error:
        print(f"could not stop a starting game: {error}", file=sys.stderr)
    for game in tuple(_owned):
        try:
            game.close()
        except Exception as error:
            print(f"could not stop {game.name}: {error}", file=sys.stderr)
    for path in tuple(_orphan_userdirs):
        shutil.rmtree(path, ignore_errors=True)
        _orphan_userdirs.discard(path)


def _run_shutdown_hooks():
    for hook in tuple(_shutdown_hooks):
        try:
            hook()
        except Exception as error:
            print(f"shutdown hook failed: {error}", file=sys.stderr)


def _run_cleanup_hooks():
    for hook in tuple(_cleanup_hooks):
        try:
            hook()
        except Exception as error:
            print(f"cleanup hook failed: {error}", file=sys.stderr)


def _report_kept_games():
    socket_dir = os.environ.get("TMUX_TMPDIR", "")
    for game in tuple(_owned):
        print(f"Kept game: env -u TMUX TMUX_TMPDIR={socket_dir} "
              f"tmux attach-session -t {_target(game.name)}", file=sys.stderr)
        print(f"User directory: {game.userdir}", file=sys.stderr)
    sys.stderr.flush()


def _cleanup_at_exit():
    if os.environ.get("BN_E2E_KEEP"):
        return
    _run_shutdown_hooks()
    close_owned_games()
    _run_cleanup_hooks()


atexit.register(_cleanup_at_exit)


def _handle_signal(signum, _frame):
    global _handling_signal
    if _handling_signal is not None:
        return
    _handling_signal = signum
    try:
        _run_shutdown_hooks()
        close_owned_games()
        if os.environ.get("BN_E2E_KEEP"):
            _report_kept_games()
        else:
            _run_cleanup_hooks()
    finally:
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)


def install_signal_handlers():
    try:
        signal.pthread_sigmask(signal.SIG_UNBLOCK,
                               (signal.SIGTERM, signal.SIGINT, signal.SIGHUP))
    except (AttributeError, OSError):
        pass
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            if signal.getsignal(signum) == signal.SIG_IGN:
                continue
            signal.signal(signum, _handle_signal)
        except (ValueError, OSError):
            continue


_UNAVAILABLE_START_TIME = "unavailable"


def _start_time(pid):
    if not os.path.isdir("/proc"):
        return _UNAVAILABLE_START_TIME
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return _UNAVAILABLE_START_TIME if os.path.exists(f"/proc/{pid}") else None
    fields = stat.rsplit(")", 1)[1].split()
    if len(fields) < 20 or fields[0] == "Z":
        return None
    return fields[19]


def _child_processes():
    if not os.path.isdir("/proc"):
        return []
    parent = str(os.getpid())
    children = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            stat = Path(f"/proc/{entry}/stat").read_text()
            argv = Path(f"/proc/{entry}/cmdline").read_bytes()
        except OSError:
            continue
        fields = stat.rsplit(")", 1)[1].split()
        if len(fields) < 20 or fields[1] != parent or fields[0] == "Z":
            continue
        children.append((int(entry), argv))
    return children


def _unreaped_client_identity(client):
    return client.pid, _start_time(client.pid)


def _new_session_client_pids(name):
    marker = b"-s\0" + name.encode() + b"\0"
    return [(pid, _start_time(pid)) for pid, argv in _child_processes()
            if b"tmux" in argv and b"new-session" in argv and marker in argv]


def _group_members(pid):
    if not os.path.isdir("/proc"):
        return []
    group = str(pid)
    members = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            stat = Path(f"/proc/{entry}/stat").read_text()
        except OSError:
            continue
        fields = stat.rsplit(")", 1)[1].split()
        if len(fields) < 20 or fields[2] != group or fields[0] == "Z":
            continue
        members.append((int(entry), fields[19]))
    return members


def _pid_matches(pid, started):
    if started == _UNAVAILABLE_START_TIME:
        return True
    if started is None:
        return False
    return _start_time(pid) == started


def _signal_pid(pid, signum, started=None):
    if not _pid_matches(pid, started):
        return False
    try:
        os.kill(pid, signum)
    except OSError:
        return False
    return True


def _stop_pid(pid, grace, started=None):
    if not _signal_pid(pid, signal.SIGTERM, started):
        return True
    deadline = time.time() + grace
    while time.time() < deadline:
        if not _pid_matches(pid, started):
            return True
        time.sleep(0.05)
    _signal_pid(pid, signal.SIGKILL, started)
    time.sleep(0.05)
    return not _pid_matches(pid, started)


def _stop_process_group(pid, grace=2.0, started=None, members=()):
    if not _pid_matches(pid, started):
        return True
    verified = [(member, member_start) for member, member_start in members
                if _pid_matches(member, member_start)]

    def alive():
        if _pid_matches(pid, started):
            return True
        return any(_pid_matches(member, member_start) for member, member_start in verified)

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError:
        return _stop_pid(pid, grace, started)
    for member, member_start in verified:
        _signal_pid(member, signal.SIGTERM, member_start)
    deadline = time.time() + grace
    while time.time() < deadline:
        if not alive():
            return True
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass
    for member, member_start in verified:
        _signal_pid(member, signal.SIGKILL, member_start)
    time.sleep(0.05)
    return not alive()


def _program(argv):
    return argv.split(b"\0", 1)[0].rsplit(b"/", 1)[-1]


def _processes_using(userdir):
    if not os.path.isdir("/proc"):
        return []
    directory = str(userdir).encode()
    spaced = b"--userdir " + directory
    separate = b"--userdir\0" + directory
    needles = (separate + b"\0", separate + b"/\0", spaced + b" ", spaced + b"\0")
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            argv = Path(f"/proc/{entry}/cmdline").read_bytes()
        except OSError:
            continue
        if _program(argv) == b"tmux":
            continue
        if any(needle in argv for needle in needles):
            pid = int(entry)
            pids.append((pid, _start_time(pid)))
    return pids


def _stop_userdir_processes(userdir, grace=1.0):
    for pid, started in _processes_using(userdir):
        _stop_pid(pid, grace, started)


def _unique_session_name(base):
    taken = {game.name for game in tuple(_owned)}
    if base not in taken:
        return base
    suffix = 1
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


def _pane_pids(name):
    try:
        listed = subprocess.run(["tmux", "list-panes", "-t", _target(name), "-F", "#{pane_pid}"],
                                capture_output=True, text=True, timeout=TMUX_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if listed.returncode:
        return []
    pids = [int(value) for value in listed.stdout.split() if value.isdigit()]
    return [(pid, _start_time(pid), _group_members(pid)) for pid in pids]


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
                 userdir=None, layout="labels", state_path=None, owns_userdir=None):
        self.name = _unique_session_name(f"{name}-{os.getpid()}")
        if userdir:
            self.userdir = Path(userdir)
            if owns_userdir is None:
                owns_userdir = False
        else:
            self.userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-"))
            _orphan_userdirs.add(self.userdir)
            if owns_userdir is None:
                owns_userdir = True
        self._owns_userdir = bool(owns_userdir)
        self._defined = set()
        _owned.add(self)
        self.state_path = Path(state_path).resolve() if state_path else None
        config = self.userdir / "config"
        config.mkdir(parents=True, exist_ok=True)
        panels = config / "panel_options.json"
        if layout is not None and not panels.exists():
            panels.write_text(json.dumps([{"current_layout_id": layout, "layouts": []}]))
        if options:
            (config / "options.json").write_text(json.dumps(
                [{"info": "", "default": "", "name": k, "value": v} for k, v in options.items()]))
        if keybindings:
            (config / "keybindings.json").write_text((ROOT / keybindings).read_text())
        _kill_session(self.name)
        stub_bin = self.userdir / "bin"
        stub_bin.mkdir(exist_ok=True)
        (stub_bin / "xdg-open").write_text("#!/bin/sh\nexit 0\n")
        (stub_bin / "xdg-open").chmod(0o755)
        env = f"PATH={stub_bin}:$PATH BROWSER=true LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=xterm-256color"
        state_arg = f" --state-out {self.state_path}" if self.state_path else ""
        cmd = (f"cd {ROOT} && env -u DISPLAY -u WAYLAND_DISPLAY {env} "
               f"{os.environ.get('GAME_WRAPPER', '')} {find_binary()} "
               f"--basepath {ROOT}/ --userdir {self.userdir}{state_arg}")
        _starting[self.name] = None
        try:
            client = subprocess.Popen(["tmux", "new-session", "-d", "-s", self.name,
                                       "-x", str(cols), "-y", str(rows), cmd])
            _starting[self.name] = _unreaped_client_identity(client)
            try:
                code = client.wait(timeout=START_TIMEOUT)
            except subprocess.TimeoutExpired:
                _stop_pid(client.pid, 1.0, _start_time(client.pid))
                raise subprocess.TimeoutExpired(client.args, START_TIMEOUT)
            if code:
                raise subprocess.CalledProcessError(code, client.args)
        except BaseException:
            self.close()
            raise
        finally:
            _starting.pop(self.name, None)

    def screen(self):
        return subprocess.run(["tmux", "capture-pane", "-p", "-t", _target(self.name)],
                              capture_output=True, text=True, check=True).stdout

    def state(self):
        if self.state_path is None:
            return None
        return json.loads(self.state_path.read_text())

    def resize(self, cols, rows):
        subprocess.run(["tmux", "resize-window", "-t", _target(self.name),
                        "-x", str(cols), "-y", str(rows)], check=True)

    def screen_colors(self):
        return subprocess.run(["tmux", "capture-pane", "-p", "-e", "-t", _target(self.name)],
                              capture_output=True, text=True, check=True).stdout

    def keys(self, *keys, delay=0.25):
        for k in keys:
            if k == "Home":
                curses.setupterm(term="xterm-256color")
                code = curses.tigetstr("khome")
                subprocess.run(["tmux", "send-keys", "-H", "-t", _target(self.name), "--",
                                *(f"{byte:02x}" for byte in code)], check=True)
            else:
                subprocess.run(["tmux", "send-keys", "-t", _target(self.name), "--", k], check=True)
            time.sleep(delay)

    def type(self, text, delay=0.05):
        subprocess.run(["tmux", "send-keys", "-t", _target(self.name), "-l", "--", text], check=True)
        time.sleep(delay)

    def click(self, x, y, button=0, settle=True):
        for suffix in ("M", "m"):
            subprocess.run(["tmux", "send-keys", "-t", _target(self.name), "-l", "--", f"\x1b[<{button};{x + 1};{y + 1}{suffix}"], check=True)
            time.sleep(0.05)
        if settle:
            self.settle_screen(minimum=1.0, timeout=1.5)

    def double_click(self, x, y, button=0):
        for _ in range(2):
            for suffix in ("M", "m"):
                subprocess.run(["tmux", "send-keys", "-t", _target(self.name), "-l", "--", f"\x1b[<{button};{x + 1};{y + 1}{suffix}"], check=True)
                time.sleep(0.02)
        self.settle_screen(minimum=1.0, timeout=1.5)

    def hover(self, x, y):
        subprocess.run(["tmux", "send-keys", "-t", _target(self.name), "-l", "--", f"\x1b[<35;{x + 1};{y + 1}M"], check=True)
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
            print("the error popup title did not clear", file=sys.stderr)
        return True

    def lua(self, code, _retried=False):
        try:
            return self._lua(code)
        except AssertionError as err:
            if _retried or "attempt to call a nil value" not in str(err):
                raise
            helpers = getattr(self, "_helper_src", "")
            helper_names = set(re.findall(r"function (\w+)", helpers))
            lost_helper = "function out(" not in code and any(
                f"{name}(" in code for name in helper_names)
            if "gapi.get_avatar()" not in code and not lost_helper:
                raise
            time.sleep(0.5)
            self.settle_screen()
            if lost_helper:
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
        self.wait_for(editing, timeout=15)
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
        prelude = ("function out(...) local t = {} for i, v in ipairs({...}) do t[i] = tostring(v) end "
                   "print(OUT .. 'V:' .. table.concat(t, ',')) end ")
        self._helper_prelude, self._helper_src = prelude, code
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
                self._defined.add(code)
                return
            last = f"Lua helper definition returned {result!r}"
        raise AssertionError(f"{last}\n{self.screen()}")

    def pos(self):
        line = next(l for l in self.screen().splitlines() if "X,Y,Z:" in l)
        return tuple(int(v) for v in line.split("X,Y,Z:")[1].split()[0:3] for v in [v.strip(",")])

    def keep_userdir(self):
        self._owns_userdir = False
        _orphan_userdirs.discard(self.userdir)

    def adopt_userdir(self):
        self._owns_userdir = True

    def detach(self):
        self._owns_userdir = False
        _orphan_userdirs.discard(self.userdir)
        _owned.discard(self)

    def _shares_userdir(self):
        others = [other for other in tuple(_owned)
                  if other is not self and other.userdir == self.userdir]
        return any(_session_exists(other.name) for other in others)

    def close(self):
        stopped = False
        shared = self._owns_userdir and self._shares_userdir()
        try:
            for pid, started, members in _pane_pids(self.name):
                _stop_process_group(pid, started=started, members=members)
            _kill_session(self.name)
            deadline = time.time() + 2.0
            while _session_exists(self.name) and time.time() < deadline:
                _kill_session(self.name)
                time.sleep(0.05)
            stopped = not _session_exists(self.name)
            if self._owns_userdir and stopped and not shared:
                _stop_userdir_processes(self.userdir)
        finally:
            if self._owns_userdir and stopped and not shared:
                shutil.rmtree(self.userdir, ignore_errors=True)
            _orphan_userdirs.discard(self.userdir)
            _owned.discard(self)


def in_game(screen):
    return (("X,Y,Z" in screen and (" move " in screen or "Place :" in screen))
            or ("Location:" in screen and "Stm" in screen)
            or ("HEAD" in screen and "TORSO" in screen)
            or ("STATUS" in screen and "LOADOUT" in screen))


def start_new_game(game, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = game.screen()
        if "Are you SURE" in s:
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
            game.keys("F5", delay=1)
        else:
            time.sleep(0.5)
    raise AssertionError("never reached the game\n" + game.screen())
