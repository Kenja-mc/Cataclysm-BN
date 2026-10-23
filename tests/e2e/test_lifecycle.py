"""Harness lifecycle contracts against real curses games and a private tmux server."""
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from subprocess import CalledProcessError

import fixtures
from fixtures import retire, shared_game
from run import run_tests
from tmux_game import Game, start_new_game


PROFILE = {"SAFEMODE": "false", "SOUND_MARKER_TURNS": "3"}


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
        fixtures._close_all()
        cls.socket_dir.cleanup()
        for key, value in cls.environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def tearDown(self):
        fixtures._close_all()

    def test_nested_failure_preserves_active_borrower_then_replaces_profile(self):
        with shared_game("bn-e2e-lifecycle", options=PROFILE,
                         define="LIFECYCLE=1") as outer:
            with self.assertRaises(AssertionError):
                with shared_game("bn-e2e-lifecycle-borrower", options=PROFILE) as inner:
                    self.assertIs(inner, outer)
                    raise AssertionError("nested borrower failed")
            # Failure must propagate, but the outer caller can still inspect its game.
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
        # Missing panes must raise from tmux I/O, not become empty screens and Lua timeouts.
        for operation in (game.screen, game.screen_colors, lambda: game.keys("x"),
                          lambda: game.lua("out('dead')")):
            with self.subTest(operation=operation):
                with self.assertRaises(CalledProcessError):
                    operation()


if __name__ == "__main__":
    unittest.main()
