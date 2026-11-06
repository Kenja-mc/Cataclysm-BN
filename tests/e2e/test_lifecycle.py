import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from subprocess import CalledProcessError

from fixtures import retire, shared_game
import playtest
from run import run_tests
import tmux_game
from tmux_game import Game, start_new_game


PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "3"}
E2E = Path(__file__).resolve().parent

FAKE_GAME = """#!/bin/sh
printf 'pid=%s|tmux=%s|args=%s\\n' "$$" "${TMUX-}" "$*" >> "$FAKE_GAME_LOG"
exec sleep 300
"""

IDLE_CHILD = r"""
import os
import time
from pathlib import Path

import tmux_game

tmux_game.install_signal_handlers()
tmux_game.find_binary = lambda: Path(os.environ["FAKE_GAME"])
while not Path(os.environ["GO_PATH"]).exists():
    time.sleep(0.02)
game = tmux_game.Game(name="bn-e2e-lifecycle-idle", userdir=os.environ["GAME_USERDIR"],
                      owns_userdir=False)
Path(os.environ["READY_PATH"]).write_text(game.name)
time.sleep(300)
"""

STARTUP_CHILD = r"""
import os
import signal
import sys
from pathlib import Path

import tmux_game

tmux_game.install_signal_handlers()
tmux_game.find_binary = lambda: Path(os.environ["FAKE_GAME"])
real_popen = tmux_game.subprocess.Popen
interrupted = []


class InFlightPopen(real_popen):
    def __init__(self, argv, *args, **kwargs):
        super().__init__(argv, *args, **kwargs)
        if list(argv)[:2] == ["tmux", "new-session"] and not interrupted:
            interrupted.append(True)
            Path(os.environ["CLIENT_PATH"]).write_text(str(self.pid))
            os.kill(os.getpid(), signal.SIGTERM)


tmux_game.subprocess.Popen = InFlightPopen
tmux_game.Game(name="bn-e2e-lifecycle-startup", userdir=os.environ["GAME_USERDIR"],
               owns_userdir=False)
print("Game construction returned, so the startup signal was not handled", file=sys.stderr)
sys.exit(4)
"""

CLOSE_CHILD = r"""
import json
import os
import signal
import sys
from pathlib import Path

import tmux_game

tmux_game.install_signal_handlers()
tmux_game.find_binary = lambda: Path(os.environ["FAKE_GAME"])
game = tmux_game.Game(name="bn-e2e-lifecycle-close")
Path(os.environ["READY_PATH"]).write_text(json.dumps({"name": game.name,
                                                      "userdir": str(game.userdir)}))
real_panes = tmux_game._pane_pids
real_stop = tmux_game._stop_process_group
pane_calls = []
stopped = []


def panes_then_duplicate(name):
    result = real_panes(name)
    pane_calls.append(True)
    if len(pane_calls) == 2:
        os.kill(os.getpid(), signal.SIGTERM)
    return result


def stop_then_interrupt(pid, *args, **kwargs):
    result = real_stop(pid, *args, **kwargs)
    if not stopped:
        stopped.append(True)
        os.kill(os.getpid(), signal.SIGTERM)
    return result


tmux_game._pane_pids = panes_then_duplicate
tmux_game._stop_process_group = stop_then_interrupt
game.close()
print("Game.close returned despite the signal", file=sys.stderr)
sys.exit(5)
"""

SURVIVOR_GAME = """#!/bin/sh
( trap '' TERM HUP; exec sleep 300 ) &
printf 'pid=%s|tmux=%s|args=%s\\n' "$!" "${TMUX-}" "$*" >> "$FAKE_GAME_LOG"
exec sleep 300
"""

SURVIVOR_CHILD = r"""
import json
import os
import sys
import time
from pathlib import Path

import tmux_game

tmux_game.install_signal_handlers()
tmux_game.find_binary = lambda: Path(os.environ["FAKE_GAME"])
game = tmux_game.Game(name="bn-e2e-lifecycle-survivor")
Path(os.environ["READY_PATH"]).write_text(json.dumps({"name": game.name,
                                                      "userdir": str(game.userdir)}))
while not Path(os.environ["GO_PATH"]).exists():
    time.sleep(0.02)
game.close()
sys.exit(0)
"""

USERDIR_PREFIX_CHILD = r"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import tmux_game

tmux_game.install_signal_handlers()
tmux_game.find_binary = lambda: Path(os.environ["FAKE_GAME"])
game = tmux_game.Game(name="bn-e2e-lifecycle-prefix")
sibling = str(game.userdir) + "-sibling"
decoys = [
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)",
                      "--userdir", sibling]),
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)",
                      f"--userdir {sibling}"]),
]
pids = [process.pid for process in decoys]
Path(os.environ["READY_PATH"]).write_text(json.dumps({"name": game.name,
                                                      "userdir": str(game.userdir),
                                                      "pids": pids}))


def running(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    return stat.rsplit(")", 1)[1].split()[0] != "Z"


try:
    game.close()
    stopped = [pid for pid in pids if not running(pid)]
finally:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
if stopped:
    print(f"close stopped processes with longer user directories: {stopped}", file=sys.stderr)
    sys.exit(6)
sys.exit(0)
"""


HANDOFF_CHILD = r"""
import json
import os
import sys
from pathlib import Path

import playtest
import tmux_game

tmux_game.find_binary = lambda: Path(os.environ["FAKE_GAME"])
playtest.find_binary = tmux_game.find_binary
playtest.scenario_by_id = lambda scenario_id: {
    "id": "handoff", "about": "keeps its session", "check": (), "start": "game"}


def start(scenario_id, **kwargs):
    game = tmux_game.Game(name="bn-e2e-lifecycle-handoff")
    (game.userdir / "world.txt").write_text("world")
    Path(os.environ["HANDOFF_STATE"]).write_text(json.dumps({"name": game.name,
                                                            "userdir": str(game.userdir)}))
    return playtest.ScenarioHandle(scenario_id=scenario_id, mode="curses", scheme="modern",
                                   userdir=game.userdir, save_name=None, game=game,
                                   about="keeps its session", check=(), owns_userdir=True)


playtest.start_scenario = start
sys.argv = ["playtest.py", "handoff"]
sys.exit(playtest.main())
"""


def _start_time(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    fields = stat.rsplit(")", 1)[1].split()
    if len(fields) < 20 or fields[0] == "Z":
        return None
    return fields[19]


def _pid_running(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    return stat.rsplit(")", 1)[1].split()[0] != "Z"


def _kill_pid(pid):
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def _reap_process(process):
    if process.poll() is None:
        process.kill()
    process.wait()


def _stop_child(child):
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=60)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    for stream in (child.stdout, child.stderr):
        if stream is not None:
            stream.close()


def _kill_session(session, socket=None, env=None):
    command = ["tmux"]
    if socket:
        command += ["-S", socket]
    try:
        subprocess.run([*command, "kill-session", "-t", f"={session}"],
                       stderr=subprocess.DEVNULL, check=False, timeout=30, env=env)
    except subprocess.TimeoutExpired:
        pass


def _userdir_of(args):
    tokens = args.split()
    for index, token in enumerate(tokens[:-1]):
        if token == "--userdir":
            return tokens[index + 1]
    raise KeyError(f"no --userdir in {args!r}")


def _pids_using(userdir):
    wanted = {str(userdir).encode(), str(userdir).encode() + b"/"}
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            argv = Path(f"/proc/{entry}/cmdline").read_bytes()
        except OSError:
            continue
        tokens = argv.split(b"\0")
        if any(token == b"--userdir" and index + 1 < len(tokens)
               and tokens[index + 1] in wanted
               for index, token in enumerate(tokens)):
            pids.append(int(entry))
    return pids


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.socket_dir = tempfile.TemporaryDirectory(prefix="bn-e2e-lifecycle-")
        cls.environment = {key: os.environ.get(key) for key in
                           ("TMUX", "TMUX_TMPDIR", "BN_E2E_KEEP")}
        os.environ.pop("TMUX", None)
        os.environ.pop("BN_E2E_KEEP", None)
        os.environ["TMUX_TMPDIR"] = cls.socket_dir.name

    @classmethod
    def tearDownClass(cls):
        tmux_game.close_owned_games()
        cls.socket_dir.cleanup()
        for key, value in cls.environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory(prefix="bn-e2e-interrupt-",
                                                   ignore_cleanup_errors=True)
        self.root = Path(self.workdir.name)
        self.log = self.root / "games.log"
        self.fake_game = self.root / "fake-game"
        self.fake_game.write_text(FAKE_GAME)
        self.fake_game.chmod(0o755)
        self.quiet_game = self.root / "quiet-game"
        self.quiet_game.write_text("#!/bin/sh\nexec sleep 300\n")
        self.quiet_game.chmod(0o755)
        self.staying_game = self.root / "staying-game"
        self.staying_game.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(300)\n")
        self.staying_game.chmod(0o755)

    def tearDown(self):
        tmux_game.close_owned_games()
        try:
            listed = subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"],
                                    capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            listed = None
        if listed is not None:
            for name in listed.stdout.split():
                if name.startswith("bn-e2e-lifecycle-"):
                    _kill_session(name)
        self.workdir.cleanup()

    def _env(self, wrapper=False, **extra):
        skipped = {"TMUX", "TMUX_TMPDIR", "BN_E2E_KEEP", "GAME_WRAPPER", "FAKE_GAME_LOG"}
        env = {key: value for key, value in os.environ.items() if key not in skipped}
        env.update(TMUX_TMPDIR=self.socket_dir.name, FAKE_GAME_LOG=str(self.log),
                   PYTHONUNBUFFERED="1")
        env["PYTHONPATH"] = str(E2E) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        if wrapper:
            env["GAME_WRAPPER"] = str(self.fake_game)
        env.update(extra)
        return env

    def _start_runner(self, args, output, new_session=False):
        with open(output, "w") as stream:
            return subprocess.Popen([sys.executable, str(E2E / "run.py"), *args],
                                    cwd=tmux_game.ROOT,
                                    env=self._env(wrapper=True), stdout=stream,
                                    stderr=subprocess.STDOUT, start_new_session=new_session)

    def _entries(self):
        try:
            lines = self.log.read_text().splitlines()
        except FileNotFoundError:
            return []
        entries = []
        for line in lines:
            fields = dict(part.split("=", 1) for part in line.split("|") if "=" in part)
            try:
                entries.append({"pid": int(fields["pid"]),
                                "socket": fields["tmux"].rsplit(",", 2)[0],
                                "userdir": _userdir_of(fields["args"])})
            except (KeyError, ValueError):
                continue
        return entries

    def _wait_entries(self, count, process=None, output=None, timeout=180):
        deadline = time.time() + timeout
        while time.time() < deadline:
            entries = self._entries()
            if len({entry["userdir"] for entry in entries}) >= count:
                return entries
            if process is not None and process.poll() is not None:
                detail = output.read_text() if output is not None else ""
                self.fail(f"run.py exited {process.returncode} before {count} game(s) started:\n"
                          + detail)
            time.sleep(0.1)
        detail = output.read_text() if output is not None else ""
        self.fail(f"{count} game(s) never started within {timeout}s:\n" + detail)

    def _wait_pid_gone(self, pid, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not _pid_running(pid):
                return
            time.sleep(0.05)
        self.fail(f"process {pid} outlived the interrupted run")

    def _wait_no_processes(self, userdir, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not _pids_using(userdir):
                return
            time.sleep(0.05)
        self.fail(f"a game still runs with user directory {userdir}: {_pids_using(userdir)}")

    def _children_of(self, parent, count=1, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            children = []
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                try:
                    stat = Path(f"/proc/{entry}/stat").read_text()
                except OSError:
                    continue
                fields = stat.rsplit(")", 1)[1].split()
                if len(fields) < 20 or fields[0] == "Z" or fields[1] != str(parent):
                    continue
                children.append(int(entry))
            if len(children) >= count:
                return children
            time.sleep(0.05)
        return []

    def _has_session(self, session, socket=None):
        command = ["tmux"] + (["-S", socket] if socket else [])
        try:
            return subprocess.run([*command, "has-session", "-t", f"={session}"],
                                  capture_output=True, text=True,
                                  timeout=30).returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def _assert_session_gone(self, socket, session, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                result = subprocess.run(["tmux", "-S", socket, "has-session",
                                         "-t", f"={session}"],
                                        capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired:
                self.fail(f"tmux stopped answering for {socket}")
            if result.returncode:
                return
            time.sleep(0.05)
        self.fail(f"owned tmux session {session} survived on {socket}")

    def _assert_no_sessions(self, socket, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                result = subprocess.run(["tmux", "-S", socket, "list-sessions",
                                         "-F", "#{session_name}"],
                                        capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired:
                self.fail(f"tmux stopped answering for {socket}")
            if result.returncode or not result.stdout.strip():
                return
            time.sleep(0.05)
        self.fail(f"tmux sessions survived on {socket}: {result.stdout}")

    def test_sigterm_and_sigint_stop_a_serial_runner_game(self):
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=signal.Signals(signum).name):
                self.log.unlink(missing_ok=True)
                output = self.root / f"serial-{signum}.log"
                runner = self._start_runner(["--serial", "test_wait_keeps_position"], output)
                try:
                    entries = self._wait_entries(1, runner, output)
                    self.assertEqual(len(entries), 1, output.read_text())
                    runner.send_signal(signum)
                    self.assertEqual(runner.wait(timeout=180), -signum, output.read_text())
                    entry = entries[0]
                    self.assertTrue(entry["socket"], "the game did not report its tmux socket")
                    self._wait_pid_gone(entry["pid"])
                    self._wait_no_processes(entry["userdir"])
                    self.assertFalse(Path(entry["userdir"]).exists(), "user directory survived")
                    self._assert_session_gone(entry["socket"], f"bn-e2e-{runner.pid}")
                finally:
                    if runner.poll() is None:
                        runner.terminate()
                        try:
                            runner.wait(timeout=60)
                        except subprocess.TimeoutExpired:
                            runner.kill()
                            runner.wait()

    def test_sigterm_and_sigint_stop_parallel_runs(self):
        for signum, group in ((signal.SIGTERM, False), (signal.SIGTERM, True),
                              (signal.SIGINT, True)):
            with self.subTest(signal=signal.Signals(signum).name, group=group):
                self.log.unlink(missing_ok=True)
                output = self.root / f"parallel-{signum}.log"
                parent = self._start_runner(["--parallel=2"], output, new_session=group)
                try:
                    entries = self._wait_entries(2, parent, output)
                    shards = self._children_of(parent.pid, count=2)
                    self.assertEqual(len(shards), 2, output.read_text())
                    sockets = {entry["socket"] for entry in entries}
                    self.assertEqual(len(sockets), 2, output.read_text())
                    self.assertTrue(all(sockets), "a shard game did not report its tmux socket")
                    if group:
                        os.killpg(parent.pid, signum)
                    else:
                        parent.send_signal(signum)
                    self.assertEqual(parent.wait(timeout=240), -signum, output.read_text())
                    for pid in shards:
                        self._wait_pid_gone(pid)
                    for entry in entries:
                        self._wait_pid_gone(entry["pid"])
                        self._wait_no_processes(entry["userdir"])
                        self.assertFalse(Path(entry["userdir"]).exists(),
                                         "user directory survived")
                    for socket in sockets:
                        self._assert_no_sessions(socket)
                finally:
                    if parent.poll() is None:
                        parent.terminate()
                        try:
                            parent.wait(timeout=60)
                        except subprocess.TimeoutExpired:
                            for pid in self._children_of(parent.pid, timeout=5):
                                try:
                                    os.kill(pid, signal.SIGKILL)
                                except OSError:
                                    pass
                            parent.kill()
                            parent.wait()

    def test_sigterm_during_game_startup_stops_the_owned_session(self):
        userdir = self.root / "startup-user"
        userdir.mkdir()
        client_path = self.root / "startup-client"
        child = subprocess.Popen(
            [sys.executable, "-c", STARTUP_CHILD], cwd=tmux_game.ROOT,
            env=self._env(FAKE_GAME=str(self.fake_game), GAME_USERDIR=str(userdir),
                          CLIENT_PATH=str(client_path)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        session = f"bn-e2e-lifecycle-startup-{child.pid}"
        try:
            deadline = time.time() + 180
            while time.time() < deadline and not client_path.exists() and child.poll() is None:
                time.sleep(0.05)
            self.assertTrue(client_path.exists(), "the startup child never launched tmux")
            client = int(client_path.read_text())
            stdout, stderr = child.communicate(timeout=180)
        finally:
            _stop_child(child)
        self.assertEqual(child.returncode, -signal.SIGTERM, stderr + stdout)
        self._wait_pid_gone(client)
        for entry in self._entries():
            self._wait_pid_gone(entry["pid"])
        self._wait_no_processes(userdir)
        self.assertTrue(userdir.exists(), "the interrupted game deleted a caller-owned directory")
        self.assertFalse(self._has_session(session),
                         "the in-flight startup left its tmux session")

    def test_interruption_leaves_unrelated_tmux_sessions_running(self):
        unrelated = f"bn-e2e-lifecycle-unrelated-{os.getpid()}"
        userdir = self.root / "idle-user"
        userdir.mkdir()
        go = self.root / "idle-go"
        ready = self.root / "idle-ready"
        socket_dir = self.root / "tmux"
        socket_dir.mkdir()
        env = self._env(FAKE_GAME=str(self.fake_game), GAME_USERDIR=str(userdir),
                        READY_PATH=str(ready), GO_PATH=str(go),
                        TMUX_TMPDIR=str(socket_dir))
        pane_pids = []
        decoy = None
        decoy_pids = []
        child = None
        try:
            subprocess.run(["tmux", "new-session", "-d", "-s", unrelated, "sleep 300"],
                           check=True, timeout=30, env=env)
            panes = subprocess.run(["tmux", "list-panes", "-t", f"={unrelated}:",
                                    "-F", "#{pane_pid}"], capture_output=True, text=True,
                                   timeout=30, env=env)
            pane_pids = [int(value) for value in panes.stdout.split() if value.isdigit()]
            child = subprocess.Popen(
                [sys.executable, "-c", IDLE_CHILD], cwd=tmux_game.ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            owned_session = f"bn-e2e-lifecycle-idle-{child.pid}"
            decoy = f"{owned_session}-decoy"
            subprocess.run(["tmux", "new-session", "-d", "-s", decoy, "sleep 300"],
                           check=True, timeout=30, env=env)
            decoy_panes = subprocess.run(["tmux", "list-panes", "-t", f"={decoy}:",
                                          "-F", "#{pane_pid}"],
                                         capture_output=True, text=True, timeout=30, env=env)
            decoy_pids = [int(value) for value in decoy_panes.stdout.split()
                          if value.isdigit()]
            go.write_text("go")
            deadline = time.time() + 180
            while time.time() < deadline and not ready.exists() and child.poll() is None:
                time.sleep(0.05)
            self.assertTrue(ready.exists(), "the idle child never started its game")
            entries = self._wait_entries(1, child)
            self.assertEqual(len(entries), 1, self.log.read_text())
            self.assertTrue(entries[0]["socket"], "the game did not report its tmux socket")
            child.send_signal(signal.SIGTERM)
            stdout, stderr = child.communicate(timeout=180)
            self.assertEqual(child.returncode, -signal.SIGTERM, stderr + stdout)
            self._wait_pid_gone(entries[0]["pid"])
            self._wait_no_processes(userdir)
            self.assertTrue(userdir.exists(),
                            "the interrupted game deleted a caller-owned directory")
            self._assert_session_gone(entries[0]["socket"], owned_session)
            still_there = subprocess.run(["tmux", "has-session", "-t", f"={unrelated}"],
                                         capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(still_there.returncode, 0,
                             "the interruption stopped an unrelated tmux session")
            decoy_there = subprocess.run(["tmux", "-S", entries[0]["socket"],
                                          "has-session", "-t", f"={decoy}"],
                                         capture_output=True, text=True, timeout=30)
            self.assertEqual(decoy_there.returncode, 0,
                             "a prefix-matching session was stopped")
            for pid in decoy_pids:
                self.assertTrue(_pid_running(pid), "a prefix-matching pane was stopped")
        finally:
            if child is not None:
                _stop_child(child)
            _kill_session(unrelated, env=env)
            if decoy is not None:
                _kill_session(decoy, env=env)
            for pid in pane_pids + decoy_pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
            try:
                listed = subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"],
                                        capture_output=True, text=True, timeout=30, env=env)
            except subprocess.TimeoutExpired:
                listed = None
            if listed is not None:
                for name in listed.stdout.split():
                    if name.startswith("bn-e2e-lifecycle-"):
                        _kill_session(name, env=env)

    def test_sigterm_during_game_close_ignores_a_duplicate_and_stops_the_owned_game(self):
        ready = self.root / "close-ready"
        child = subprocess.Popen(
            [sys.executable, "-c", CLOSE_CHILD], cwd=tmux_game.ROOT,
            env=self._env(FAKE_GAME=str(self.fake_game), READY_PATH=str(ready)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.time() + 180
            while time.time() < deadline and not ready.exists() and child.poll() is None:
                time.sleep(0.05)
            self.assertTrue(ready.exists(), "the close child never created its game")
            state = json.loads(ready.read_text())
            stdout, stderr = child.communicate(timeout=180)
        finally:
            _stop_child(child)
        self.assertEqual(child.returncode, -signal.SIGTERM, stderr + stdout)
        self.assertNotIn("Game.close returned", stderr + stdout)
        self.assertFalse(Path(state["userdir"]).exists(),
                         "the interrupted close kept the owned user directory")
        self.assertFalse(self._has_session(state["name"]),
                         "the interrupted close left its tmux session")

    def test_close_stops_a_group_member_that_ignores_sigterm(self):
        wrapper = self.root / "survivor-game"
        wrapper.write_text(SURVIVOR_GAME)
        wrapper.chmod(0o755)
        go = self.root / "survivor-go"
        ready = self.root / "survivor-ready"
        socket_dir = self.root / "tmux"
        socket_dir.mkdir()
        env = self._env(GAME_WRAPPER=str(wrapper), FAKE_GAME=str(self.fake_game),
                        READY_PATH=str(ready), GO_PATH=str(go),
                        TMUX_TMPDIR=str(socket_dir))
        child = subprocess.Popen(
            [sys.executable, "-c", SURVIVOR_CHILD], cwd=tmux_game.ROOT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        survivor = None
        survivor_start = None
        game_socket = None
        state = None
        try:
            entries = self._wait_entries(1, child)
            self.assertEqual(len(entries), 1, self.log.read_text())
            survivor = entries[0]["pid"]
            survivor_start = _start_time(survivor)
            game_socket = entries[0]["socket"] or None
            self.assertTrue(game_socket, "the game did not report its tmux socket")
            deadline = time.time() + 180
            while time.time() < deadline and not ready.exists() and child.poll() is None:
                time.sleep(0.05)
            self.assertTrue(ready.exists(), "the survivor child never created its game")
            state = json.loads(ready.read_text())
            go.write_text("go")
            stdout, stderr = child.communicate(timeout=180)
        finally:
            _stop_child(child)
            if survivor_start is not None and _start_time(survivor) == survivor_start:
                try:
                    os.kill(survivor, signal.SIGKILL)
                except OSError:
                    pass
        self.assertEqual(child.returncode, 0, stderr + stdout)
        self._wait_pid_gone(survivor)
        self.assertFalse(self._has_session(state["name"], game_socket),
                         "close left the tmux session behind")
        self.assertFalse(Path(state["userdir"]).exists(),
                         "close kept the owned user directory")

    def test_close_leaves_processes_with_a_longer_userdir(self):
        ready = self.root / "prefix-ready"
        child = subprocess.Popen(
            [sys.executable, "-c", USERDIR_PREFIX_CHILD], cwd=tmux_game.ROOT,
            env=self._env(FAKE_GAME=str(self.fake_game), READY_PATH=str(ready)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        state = None
        try:
            deadline = time.time() + 180
            while time.time() < deadline and not ready.exists() and child.poll() is None:
                time.sleep(0.05)
            self.assertTrue(ready.exists(), "the prefix child never started its decoys")
            state = json.loads(ready.read_text())
            stdout, stderr = child.communicate(timeout=180)
        finally:
            if state is not None and child.poll() is None:
                for pid in state["pids"]:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        pass
            _stop_child(child)
        self.assertEqual(child.returncode, 0, stderr + stdout)
        self.assertFalse(self._has_session(state["name"]),
                         "close left the tmux session behind")
        self.assertFalse(Path(state["userdir"]).exists(),
                         "close kept the owned user directory")

    def _quiet_game(self, userdir=None, **kwargs):
        original = tmux_game.find_binary
        tmux_game.find_binary = lambda: self.quiet_game
        try:
            return Game(name="bn-e2e-lifecycle-owned", userdir=userdir, **kwargs)
        finally:
            tmux_game.find_binary = original

    def _decoy(self, userdir):
        decoy = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(120)", "--userdir", str(userdir)])
        self.addCleanup(_reap_process, decoy)
        return decoy

    def test_close_removes_a_harness_userdir(self):
        game = self._quiet_game()
        userdir = game.userdir
        game.close()
        self.assertFalse(userdir.exists(), "a harness-created userdir survived close")

    def test_close_keeps_a_caller_userdir(self):
        userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-caller-"))
        self.addCleanup(shutil.rmtree, userdir, ignore_errors=True)
        game = self._quiet_game(userdir, owns_userdir=False)
        game.close()
        self.assertTrue(userdir.exists(), "close deleted a caller-owned userdir")

    def test_close_removes_a_caller_userdir_marked_owned(self):
        userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-caller-"))
        self.addCleanup(shutil.rmtree, userdir, ignore_errors=True)
        game = self._quiet_game(userdir, owns_userdir=True)
        game.close()
        self.assertFalse(userdir.exists(), "close kept a userdir marked owned")

    def test_close_never_scans_a_caller_userdir(self):
        userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-caller-"))
        self.addCleanup(shutil.rmtree, userdir, ignore_errors=True)
        decoy = self._decoy(userdir)
        game = self._quiet_game(userdir, owns_userdir=False)
        game.close()
        self.assertIsNone(decoy.poll(), "close killed a process on a caller-owned userdir")

    def test_close_scans_an_owned_userdir(self):
        userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-owned-"))
        self.addCleanup(shutil.rmtree, userdir, ignore_errors=True)
        decoy = self._decoy(userdir)
        game = self._quiet_game(userdir, owns_userdir=True)
        game.close()
        self.assertIsNotNone(decoy.poll(), "close left a process on an owned userdir")
        self.assertFalse(userdir.exists(), "close kept an owned userdir")

    def test_userdir_scan_finds_the_game_invocation(self):
        userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-owned-"))
        self.addCleanup(shutil.rmtree, userdir, ignore_errors=True)
        original = tmux_game.find_binary
        tmux_game.find_binary = lambda: self.staying_game
        try:
            game = Game(name="bn-e2e-lifecycle-owned", userdir=userdir, owns_userdir=True)
        finally:
            tmux_game.find_binary = original
        try:
            deadline = time.time() + 30

            def staying_game_pids():
                found = []
                for pid, _started in tmux_game._processes_using(userdir):
                    try:
                        argv = Path(f"/proc/{pid}/cmdline").read_bytes()
                    except OSError:
                        continue
                    if b"staying-game" in argv and b"tmux" not in argv:
                        found.append(pid)
                return found

            while time.time() < deadline and not staying_game_pids():
                time.sleep(0.05)
            self.assertTrue(staying_game_pids(),
                            "the userdir scan missed the game's own command line")
        finally:
            game.close()
        self.assertFalse(userdir.exists(), "close kept an owned userdir")

    def test_sigterm_keeps_the_session_when_keep_asked_for_it(self):
        output = self.root / "keep.log"
        runner = self._start_runner(["--serial", "--keep", "test_wait_keeps_position"], output)
        try:
            entries = self._wait_entries(1, runner, output)
            self.assertEqual(len(entries), 1, output.read_text())
            entry = entries[0]
            runner.send_signal(signal.SIGTERM)
            self.assertEqual(runner.wait(timeout=180), -signal.SIGTERM, output.read_text())
            self.assertTrue(_pid_running(entry["pid"]),
                            "--keep must leave its game running")
            kept = subprocess.run(
                ["tmux", "-S", entry["socket"], "has-session", "-t", f"=bn-e2e-{runner.pid}"],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(kept.returncode, 0, "--keep must leave its tmux session attachable")
            self.assertTrue(Path(entry["userdir"]).exists(),
                            "--keep must keep the user directory")
        finally:
            if runner.poll() is None:
                runner.terminate()
                try:
                    runner.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    runner.kill()
                    runner.wait()
            for entry in self._entries():
                _kill_session(f"bn-e2e-{runner.pid}", socket=entry["socket"])
                try:
                    os.kill(entry["pid"], signal.SIGKILL)
                except OSError:
                    pass
                shutil.rmtree(entry["userdir"], ignore_errors=True)

    def _tiles_run(self, userdir):
        run_dir = userdir / "tiles"
        run_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        xvfb = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        self.addCleanup(_reap_process, proc)
        self.addCleanup(_reap_process, xvfb)
        return playtest.TilesRun(proc=proc, xvfb=xvfb, x11=None, window_id=None, display="",
                                 run=run_dir, frame=None, log=None)

    def test_playtest_attach_handoff_keeps_the_session_and_world(self):
        state_path = self.root / "handoff-state.json"
        output = self.root / "handoff.log"
        with open(output, "w") as stream:
            child = subprocess.Popen([sys.executable, "-c", HANDOFF_CHILD], cwd=tmux_game.ROOT,
                                     env=self._env(FAKE_GAME=str(self.fake_game),
                                                   HANDOFF_STATE=str(state_path),
                                                   HOME=str(self.root / "home")),
                                     stdin=subprocess.DEVNULL, stdout=stream,
                                     stderr=subprocess.STDOUT)
        self.assertEqual(child.wait(timeout=180), 0, output.read_text())
        self.assertIn("Attach with:", output.read_text())
        self.assertTrue(state_path.exists(), "the playtest child never started its game")
        state = json.loads(state_path.read_text())
        session, userdir = state["name"], Path(state["userdir"])
        self.addCleanup(shutil.rmtree, userdir, ignore_errors=True)
        self.addCleanup(_kill_session, session)
        entries = [entry for entry in self._entries() if entry["userdir"] == str(userdir)]
        self.assertEqual(len(entries), 1, self.log.read_text())
        self.addCleanup(_kill_pid, entries[0]["pid"])
        self.assertTrue(self._has_session(session),
                        "the handed-off playtest session did not survive its parent")
        self.assertTrue((userdir / "world.txt").exists(),
                        "the handed-off playtest world was deleted")
        self.assertEqual((userdir / "world.txt").read_text(), "world")
        self.assertTrue(_pid_running(entries[0]["pid"]),
                        "the handed-off playtest game was stopped")

    def test_tiles_handle_discards_only_userdirs_it_owns(self):
        owned = Path(tempfile.mkdtemp(prefix="bn-e2e-tiles-owned-"))
        self.addCleanup(shutil.rmtree, owned, ignore_errors=True)
        game = self._quiet_game(owned, owns_userdir=True)
        game.keep_userdir()
        game.close()
        (owned / "world.txt").write_text("world")
        tiles_run = self._tiles_run(owned)
        handle = playtest.ScenarioHandle(scenario_id="tiles", mode="tiles", scheme="modern",
                                         userdir=owned, save_name="world", tiles=tiles_run,
                                         owns_userdir=True)
        handle.close(keep_userdir=False)
        self.assertFalse(owned.exists(), "the tiles handle kept a userdir it was told to discard")
        self.assertIsNotNone(tiles_run.proc.poll(), "the tiles process outlived the handle")
        self.assertIsNotNone(tiles_run.xvfb.poll(), "the tiles Xvfb outlived the handle")

        kept = Path(tempfile.mkdtemp(prefix="bn-e2e-tiles-kept-"))
        self.addCleanup(shutil.rmtree, kept, ignore_errors=True)
        (kept / "world.txt").write_text("world")
        kept_run = self._tiles_run(kept)
        playtest.ScenarioHandle(scenario_id="tiles", mode="tiles", scheme="modern",
                                userdir=kept, save_name="world", tiles=kept_run,
                                owns_userdir=True).close()
        self.assertTrue((kept / "world.txt").exists(), "close() deleted a tiles world by default")
        self.assertIsNotNone(kept_run.proc.poll())

        caller = Path(tempfile.mkdtemp(prefix="bn-e2e-tiles-caller-"))
        self.addCleanup(shutil.rmtree, caller, ignore_errors=True)
        (caller / "world.txt").write_text("world")
        playtest.ScenarioHandle(scenario_id="tiles", mode="tiles", scheme="modern",
                                userdir=caller, save_name="world",
                                owns_userdir=False).close(keep_userdir=False)
        self.assertTrue((caller / "world.txt").exists(),
                        "close() deleted a caller-owned tiles directory")

    def test_closing_one_game_leaves_a_sibling_on_the_same_userdir_running(self):
        userdir = Path(tempfile.mkdtemp(prefix="bn-e2e-shared-"))
        self.addCleanup(shutil.rmtree, userdir, ignore_errors=True)
        (userdir / "world.txt").write_text("world")
        original = tmux_game.find_binary
        tmux_game.find_binary = lambda: self.quiet_game
        try:
            first = Game(name="bn-e2e-lifecycle-share-a", userdir=userdir, owns_userdir=True)
            self.addCleanup(_kill_session, first.name)
            self.addCleanup(first.close)
            second = Game(name="bn-e2e-lifecycle-share-b", userdir=userdir, owns_userdir=True)
            self.addCleanup(_kill_session, second.name)
            self.addCleanup(second.close)
        finally:
            tmux_game.find_binary = original
        first.close()
        self.assertFalse(self._has_session(first.name), "closing the first game left its session")
        self.assertTrue(self._has_session(second.name),
                        "closing one game stopped the sibling on its user directory")
        self.assertTrue((userdir / "world.txt").exists(),
                        "closing one game deleted the shared user directory")
        self.assertIsInstance(second.screen(), str)
        second.close()
        self.assertFalse(self._has_session(second.name), "closing the second game left its session")
        self.assertFalse(userdir.exists(), "the last owner did not remove its user directory")

    def test_close_leaves_sibling_games_on_the_shared_tmux_server(self):
        socket_dir = self.root / "tmux"
        socket_dir.mkdir()
        previous = os.environ.get("TMUX_TMPDIR")
        os.environ["TMUX_TMPDIR"] = str(socket_dir)
        try:
            first = self._quiet_game()
            self.addCleanup(_kill_session, first.name)
            self.addCleanup(first.close)
            second = self._quiet_game()
            self.addCleanup(_kill_session, second.name)
            self.addCleanup(second.close)
            self.assertNotEqual(first.userdir, second.userdir)
            first.close()
            self.assertFalse(self._has_session(first.name),
                             "closing the game that started the server left its session")
            self.assertTrue(self._has_session(second.name),
                            "closing a game stopped the shared tmux server")
            self.assertIsInstance(second.screen(), str)
        finally:
            subprocess.run(["tmux", "kill-server"], stderr=subprocess.DEVNULL, check=False,
                           timeout=30)
            if previous is None:
                os.environ.pop("TMUX_TMPDIR", None)
            else:
                os.environ["TMUX_TMPDIR"] = previous

    def test_lua_preserves_queued_repeated_text_in_both_schemes(self):
        for scheme in ("modern", "classic"):
            with self.subTest(scheme=scheme):
                game = Game(name="bn-e2e-lifecycle-lua-burst",
                            options={**PROFILE, "CONTROL_SCHEME": scheme})
                try:
                    start_new_game(game)

                    def queue_text(text, delay=0):
                        subprocess.run(
                            ["tmux", "send-keys", "-t", tmux_game._target(game.name),
                             "-l", "--", text], check=True)

                    game.type = queue_text
                    self.assertEqual(
                        game._lua("local p=TripointBubMs.new(100000,222,0) "
                                  "out('bookkeeper',p.x,p.y,'((same))',100000//333)"),
                        ["bookkeeper,100000,222,((same)),300"])
                finally:
                    game.close()

    def test_nested_failure_preserves_active_borrower_then_replaces_profile(self):
        with shared_game("bn-e2e-lifecycle", options=PROFILE,
                         define="LIFECYCLE=1") as outer:
            with self.assertRaises(AssertionError):
                with shared_game("bn-e2e-lifecycle-borrower", options=PROFILE) as inner:
                    self.assertIs(inner, outer)
                    raise AssertionError("nested borrower failed")
            self.assertEqual(outer.lua("out(LIFECYCLE)"), ["1"])
            with self.assertRaises(RuntimeError):
                with shared_game("bn-e2e-lifecycle-invalid", options=PROFILE):
                    self.fail("a retired profile must not gain another borrower")
        with self.assertRaises(CalledProcessError):
            outer.screen()
        with shared_game("bn-e2e-lifecycle-replacement", options=PROFILE,
                         define="LIFECYCLE=2") as replacement:
            self.assertIsNot(replacement, outer)
            self.assertEqual(replacement.lua("out(LIFECYCLE)"), ["2"])
        with shared_game("bn-e2e-lifecycle-reuse", options=PROFILE) as reused:
            self.assertIs(reused, replacement)
        retire(replacement)

    def test_runner_counts_failure_and_reacquires_only_the_retired_game(self):
        seen = []
        generations = []

        def failed_borrower(game):
            seen.append(game)
            game.lua("LIFECYCLE=50 out(LIFECYCLE)")
            with shared_game("bn-e2e-lifecycle-nested", options=PROFILE) as borrowed:
                self.assertIs(borrowed, game)
                raise AssertionError("expected lifecycle test failure")

        def healthy_borrower(game):
            seen.append(game)
            generations.extend(game.lua("LIFECYCLE=(LIFECYCLE or 0)+1 out(LIFECYCLE)"))

        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = run_tests([failed_borrower, healthy_borrower, healthy_borrower])
        self.assertEqual(result, 1, output.getvalue())
        self.assertIsNot(seen[0], seen[1])
        self.assertIs(seen[1], seen[2])
        self.assertEqual(generations, ["1", "2"])

    def test_explicit_game_is_kept_after_failure_and_dead_operations_raise(self):
        game = Game(name="bn-e2e-lifecycle-kept")
        try:
            start_new_game(game)
            game.define_lua("LIFECYCLE=1")

            def failed_test(current):
                self.assertIs(current, game)
                raise AssertionError("expected kept-game test failure")

            def next_test(current):
                self.assertIs(current, game)
                self.assertEqual(current.lua("out(LIFECYCLE)"), ["1"])

            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(output):
                result = run_tests([failed_test, next_test], g=game)
            self.assertEqual(result, 1, output.getvalue())
        finally:
            game.close()
        for operation in (game.screen, game.screen_colors, lambda: game.keys("x"),
                          lambda: game.lua("out('dead')")):
            with self.subTest(operation=operation):
                with self.assertRaises(CalledProcessError):
                    operation()


if __name__ == "__main__":
    unittest.main()
