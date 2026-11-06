# E2E state reuse: feasibility and proposed experiment

## Decision

Investigate reusable saved-game templates first. Treat process-memory snapshots as a separate,
optional experiment for curses tests, not a prerequisite for the test runner. No snapshot support
has been implemented or exercised.

Memory snapshots can avoid process startup, data loading and world creation. They do not remove
UI interactions, screen synchronization or assertions after restore. The current harness already
reuses running games, so a snapshot is not a saving on every test.

## Existing behavior

- [`fixtures.py`](../../tests/e2e/fixtures.py), lines 12–16 and 50–89, caches live games by options,
  terminal size, keybindings, user directory, layout and state-output path. Reuse skips
  `start_new_game`; an exception retires the game. Tests sharing a profile also share mutable
  game state. This is reuse, not a clean baseline restored before each test.
- [`tmux_game.py`](../../tests/e2e/tmux_game.py), lines 382–442, launches the game inside a tmux
  session with a user directory, then captures the pane and sends input through tmux.
  Lines 694–728 navigate initial menus until the game is ready.
- `state_path` is an observation channel, not a restore image. `Game.state()` reads JSON;
  [`test_state.cpp`](../../src/test_state.cpp), lines 287–321, writes selected player, HUD and map
  overlay fields. That is not enough to reconstruct the simulation.
- Saved games have disk state beyond player fields. [`world.cpp`](../../src/world.cpp), lines
  663–715, opens a map SQLite database for the SQLite save format and starts save transactions.
  A template must be produced at a completed save boundary, not by copying live databases
  arbitrarily.

## Options

| Approach                                         | Potential saving                                           | Main constraint                                                              | Recommendation                                 |
| ------------------------------------------------ | ---------------------------------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------- |
| Existing live profile reuse                      | Repeated startup and world creation                        | Mutable state survives between tests                                         | Keep as the benchmark baseline                 |
| Immutable saved-game template, copied per worker | World and character creation                               | Still starts the process and loads data; needs complete, consistent saves    | First experiment                               |
| CRIU process checkpoint                          | Startup, loading and pre-checkpoint setup                  | PTY/session ownership, disk consistency, environment and process bookkeeping | Second experiment, curses only initially       |
| Full VM snapshot                                 | Guest memory and device state within its snapshot boundary | New VM infrastructure; external files and host resources still need a policy | Defer unless process restore proves unsuitable |
| In-process reset API                             | Startup without restoring a process                        | Must reset every relevant global, Lua, UI, RNG and cache state               | Do not introduce solely for this optimization  |

These are feasibility judgments, not measured performance results. Existing test durations do not
separate startup from interaction time, so no speedup estimate is justified yet.

## CRIU constraints

The official [advanced usage documentation](https://criu.org/Advanced_usage) describes these
specific issues:

- A shell job can have a session leader and PTY master outside the checkpoint. `--shell-job`
  handles that case by attaching the restored job to an existing PTY. It does not promise to
  restore tmux's screen model or Python fixture bookkeeping.
- External UNIX sockets need explicit handling; the documented disconnected/reconnected socket
  case is not a blanket guarantee for arbitrary external resources.
- Leaving a checkpointed task running can make its files inconsistent with the image. CRIU
  explicitly calls for a filesystem snapshot restored before process restore in that scenario.
  Memory restore alone is therefore not a test rollback.
- Restoring into a PID namespace can produce a different host PID; CRIU provides `--pidfile`.
  The harness must re-register restored processes with its ownership/cleanup mechanism rather
  than retain stale identities.

For this harness, checkpointing only the game leaves tmux and the Python controller outside the
snapshot. Restoring the whole test controller instead risks replaying runner state and results.
The proposed experiment should isolate one game and its tmux server, leave the coordinator outside,
and explicitly reconstruct the controller's session, PID and Lua-helper bookkeeping. Whether that
boundary works remains untested.

Tiles are a separate feasibility question: do not assume a successful curses restore also restores
SDL, display-server and graphics-device resources. Kernel/capability requirements and CI permission
compatibility must be checked in the target environment before choosing CRIU. Its official
[CLI index](https://criu.org/CLI) documents a `check` action; passing that alone would not prove the
actual game topology can be restored.

Local non-invasive check: `command -v criu` exited 1. CRIU is not available through the current
shell PATH. No install, privilege changes, checkpoint or restore was attempted.

## Future ticket: benchmark reusable E2E starting states

### Scope

Measure before implementing a default. Compare current live reuse, a copied saved-game template,
and optionally one curses process-checkpoint prototype on the same binary and option profile.
Keep ordinary fresh-start coverage for welcome screens, character/world creation and loading.
Those flows must not be bypassed by the optimization under test.

### Measurements

1. Record profile cache hits, misses and retirements in a representative serial run.
2. Separate launch/data load, world creation/load, scene setup and UI/assertion time.
3. Measure template generation and copying or checkpoint creation and restore, including cleanup.
   Report cold and warm runs separately, median and tail latency, image size and failure count.
4. Compare complete wall time with current shared fixtures, not just a fresh process per test.
   Include the extra startup cost of independent batches and workers.

If startup accounts for fraction `f` of total runtime, eliminating all of it cannot improve runtime
by more than `1 / (1 - f)`. Restore costs and template misses reduce that upper bound further.

### Correctness gates

- Capture a baseline only at an idle input boundary, with no save transaction or dialog in flight.
- Mutate inventory, map, options and persisted files, restore, then verify both memory-visible and
  disk-visible state return to baseline. Preserve deterministic RNG behavior intentionally.
- Test repeated restores, two concurrent workers, failure, interruption and cleanup. Prove another
  worker or a user's tmux session is untouched.
- Confirm fresh terminal rendering and Lua helper registration after restore, not just a live PID.
- Key templates/images by actual binary, data/mods, fixture setup, options and relevant environment.
  Reject stale reuse. Process images additionally need a supported kernel/library/path contract.
- Keep templates immutable and worker directories private. For disk templates, copy only after a
  completed save and closed producer; include all required world/player files and configuration.
- Run representative existing E2E assertions unchanged against every candidate. A successful
  restore command or matching screenshot alone is not sufficient proof of isolation.

### Adoption gate

Adopt only after the experiment demonstrates a material end-to-end saving without restore failures
or weaker coverage. Prefer saved-game templates if they deliver comparable savings with fewer
platform requirements. Keep snapshots opt-in until local and CI behavior are both established.
