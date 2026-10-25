---
name: test-quality
description: Write or review Cataclysm-BN tests that avoid flakes, use deterministic fixtures, and clean up global state.
---

# Test Quality

Use when adding or changing automated tests.

## Gates

- Test one behavior contract, not incidental implementation details.
- Before committing a new CLI, script or option, run its documented command exactly as written
  in a fresh shell and retain the observed output in the change's verification evidence.
  Check that documented flags are accepted and missing or invalid arguments name the problem.
  A parser failure such as `Failed parsing parameter …` means the documented entrypoint is broken;
  fix the parser or documentation in the same change, not just the invocation used for testing.
- Drive modal transitions one key at a time and wait for the next prompt. In the keybinding
  editor, a second Escape can dismiss the save confirmation and silently discard the new binding.
- Reject capture fixtures that raised debug assertions or used invalid item IDs. Repeated item
  names do not prove duplicate rendering: verify instance counts and worn/carried membership
  before attributing the rows to a UI bug.
- Use deterministic fixtures from `data/mods/TEST_DATA` for data with random, balance, or evolving behavior.
- E2E fixtures run against a freshly rolled world, so pin or strip rolled state before asserting on sound,
  volume, or morale. Three observed `tests/e2e/run.py` failures were fixture-side, not game bugs: a surface
  Strong Gale roll put ambient near 8600 mdB while the shout arrived at about 31 dB (`set_omt_weather_override`
  selects the weather type only, not wind); the farmer's rolled mouth gear cut `get_shout_volume` from about
  81 dB to 46 dB, below even the fixed underground threshold; and a fresh character crashed with
  `Morale "Stylish" is inconsistent` until the fixture cleared morale alongside bionics, mutations, and items.
  Use `test_sound_marker_fading` as the reference: isolated `Game` session, strip avatar and source-creature
  state, move the fixture underground where ambient is fixed, then assert.
- Avoid assertions that rely on probability, wall-clock time, locale, file order, or current global options unless the test pins them.
- Reproduce reported flakes with the failing `--rng-seed` before accepting the fix.
- When CI test jobs fail, inspect the job log for the exact test command, filters, shard split, user-dir, order-sensitive included tests, `--rng-seed`, and backend flags. Run that same shard command on the final rebased HEAD before declaring the fix validated; do not substitute a narrower tag filter or a different full-test command.
- Before pushing test fixes that touch global state, NPCs, maps, overmaps, player position, RNG, options, or fixtures, run both the relevant focused test and the CI-equivalent shard/full command that can expose state bleed from earlier tests.
- Keep Lua/C++ integration tests on real bound objects when the binding behavior is under test.
- Expected `DebugLog(DL::Error, ...)` still makes the test process fail even when assertions pass. Use
  `capture_debug_errors_during` for the injected failure only and assert its exact messages; never clear
  the global observed-error flag or disable the test runner's error check.
- A shard split is a fixture-isolation test. Moving tests between shards changes which tests share a game;
  re-partitioning exposed two order-dependent failures the old split hid. Run the full suite locally after
  any change to `durations.json` or `shard_of()`.
- A pooled game is keyed by its option set. `fixtures.shared_game` keys the pool on the options it was
  created with, so a test that changes an option from inside the game leaves a game that no longer matches
  its key; `fixtures.retire` now drops the game on an option change or a test failure.
- A failed test must not close a game it borrowed. A test borrowing the runner's own profile through
  `fixtures.shared_game` retired the runner's main game, and every later main-game test timed out on a
  missing tmux pane. Shared games now count active borrowers and close after the last one exits, the runner
  borrows per test, and tmux I/O raises on a missing pane (`tests/e2e/test_lifecycle.py`).
- Each test process needs its own tmux server. Four parallel shards on one server starve each other of
  input; `run.py` points `TMUX_TMPDIR` at a fresh directory, which must exist or tmux falls back to `/tmp`.
- A hover stillness is not a poll. Edge panning runs on game timeouts, so `hover()`'s one-second pause is
  the pan; replacing it with `settle_screen` panned one step short (`test_cursor_panning_return_center`,
  45 -> 44).
- Do not call `pos()` inside a combined Lua snippet. It prints through `out`, so the position arrives as
  the first marker line and the real value second; call it in its own snippet.
- `durations.json` must come from the CI runners. Local times are about 10x faster and mis-assign tests;
  refresh from the `e2e-durations-shard-*` artifacts, then re-check the spread (8.3%).
- A merge that adds a data type needs a rebuilt test binary. `--target cataclysm-bn` leaves `cata_test`
  stale, and the shards then report an unrecognized JSON object for data the game accepts.
- `Game.close()` deletes the private user directory. The tiles harness kills the tmux session instead, and
  reads the save name before teardown.
- `gh` resolves the repository from the git remotes and may pick `upstream` for this clone; pass
  `--repo Kenja-mc/Cataclysm-BN`.
- A shifted key needs the modifier in the key event. `Shift_L` plus `bracketright` sends `}`, while
  `bracketright` alone sends `]`.
- Static screenshots need two identical world-view frames so they do not capture loading artwork.
  Animated scenarios instead require a drawn world and compare the affected creature regions across
  frames; weather or an unrelated animation changing the whole image is not proof.
- After an upstream merge, grep the whole item family, not only the conflicted files; a re-added line
  merges cleanly and silently.
- Keep parking inside the loaded map. `park()` moved creatures to `here(45 + k % 15, 45 + k // 15)`, so the
  y offset grew every fifteen parks; after a few hundred parks a creature sat out of bounds and
  `Sound with description [ hmm ] attempted to propagate from out of bounds location` opened a modal that
  swallowed keys and failed four later tests. The ring is now bounded to 15x12 tiles inside the map.
- Identify a popup sound's source type before blaming creature fixtures. `map::load` kept vehicles from the
  previously loaded area in its per-z vehicle lists, so after save, quit and reload their idle engine sounds
  ([ hmm ], [ vroom! ]) fired the out-of-bounds sound popup. The game now clears those lists; regression
  test `loading_a_map_rebuilds_active_vehicle_membership` in `tests/map_test.cpp`.
- Read a row and its index from the same capture. `test_readable_map_glyphs` captured the screen, then
  called `Game.find('@')`, which reads a fresh screen; one line of scroll made the assertion look at the
  wrong row. Compute the index from the captured string.
- Do not prove a blocked move with the clock. The safe-mode test compared `minutes_of_day` before and after,
  but the sidebar shows an approximate time when the starting outfit has no capacity and the watch tumbles
  to the floor. Assert the avatar's position instead, and use `empty_inventory` for deterministic gear.
- Pin sight for any check that must see a creature. The starting shelter can be very dark even at 08:00;
  the hostile-tip test enables `DEBUG_NIGHTVISION` temporarily and asserts `sees` before checking the tip.
  Clear rolled monsters first, as with the sound fixture.
- Verify the executable from the final linker line. A development curses tree linked into the repo
  root while old binaries remained under `out/build/linux-curses`; running the latter fabricated
  input regressions and invalidated early data checks.
- Default worlds include `no_reviving_zombies`, so their zombie corpses cannot be pulped. Use a
  corpse with `zombify_into` (the pulp-key fixture uses a bear), or explicitly select a revival-enabled
  mod profile; do not change the pulping assertions to accept terrain smashing.
- Spawn one fixture vehicle. Debug vehicle spawn refuses an occupied tile before opening the
  prototype picker. `empty_inventory` also drops clothing on the ground: clear it when testing cargo
  alone, pin sight after stripping mutations, and assert that a dropped item actually left inventory.
- A curtain cannot close through its occupant. Test from a neighboring tile and account for the
  spawned curtain's initial open state. Time-spending actions clear tile selection; reselect the
  same known screen cell when testing a second action.
- Lua reads close the active game menu. Inspect clocks and objects before opening it or after the
  real cancellation/action path, never in the middle of a mouse-selection assertion.
- Classic UiLists ignore mouse input. Shared setup helpers must use the displayed Classic hotkey;
  use Modern clicks only when that scheme enables them.
- The minimum terminal is `80x25`, including modal resize paths. For report overflow, load a private
  heading-only mod through the normal JSON loader instead of shrinking below that limit.
- The multiline Lua editor supports Ctrl+Y submission; native probes use it consistently. Wait
  for the editor to close and a real result line, not merely code echoed in its history.
- Native chord probes must release modifiers promptly. Holding Shift until after input processing
  hides bugs that consult current global modifier state instead of the key-down event.
- For native scaling tests, stored `TERMINAL_X/Y` use base-font cells. Multiply the desired visible
  columns/rows by `SCALING_FACTOR`; keep the physical-window assertion at visible cells × font × scale.
- Check Lua argument types at the binding source: `Creature:sees` takes bubble coordinates, not a
  creature; `get_skill_level` returns an integer, while `get_skill_level_object` returns the trainable object.
- Lowering a skill preserves its highest-level history. `train()` doubles recovery below that level;
  assert the fixture's starting skill after training, before exercising the UI.
- Native tutorial checks must start Tutorial from the title screen. A Lua-saved tutorial is not an
  ordinary reloadable fixture: its null scenario fails load and loses the built-in game mode.
- Nightvision does not supply reading light; use a real emitter. A stripped avatar has no cargo
  volume: wield the book or supply storage before a real turn can drop it.
- Native vehicle previews use tiles, not the curses text grid. Derive click targets from the
  rendered tile pitch; text-cell coordinates do not carry over. Keep raw captures when OCR fails.
- Undamaged cars still randomize door openness. Establish a closed target through the real close
  UI before testing an opening, and wait for the direction prompt before sending its key.
- For native footsteps, pin both current and destination terrain and verify worn foot coverage.
  Use `body_part_foot_l.id()`, not a legacy enum cast to a dynamic body-part index. Quiet pry-break
  noise can be masked by a storm; use quiet acoustics without changing the game's sound volume.
- Parking leaves creatures active; they can return during a long activity. If hostiles are not part
  of that contract, clear loaded monsters and settle before starting it. Inspect the whole failure
  screen for interruption dialogs instead of lengthening the timeout or dismissing the warning.
- NPC responses depend on prices and opinions. Trade click tests must prove unchanged ownership
  after cancellation, not assume a particular empty-offer rejection sentence.
- Run an isolated suite with `bin/playtest-container.sh e2e [test-name ...]`.

## Cleanup

- Restore global state with `restore_on_out_of_scope` for calendar, options, globals, and singleton state.
- Use `clear_map()` and explicit player placement when map contents matter.
- Do not leave creatures, items, hooks, worlds, temp files, or option changes that can affect later tests.
- Prefer new `TEST_DATA` fixtures over mutating base-game data in the test body.
- Revert formatter-only hunks by changing indentation alone; preserve `else` and `catch` separators.
