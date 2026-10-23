# Cataclysm: BN - Open Work

## Next actions

- **Main is current** — the modular end-to-end suite, world presets, stocked river barges, fluid
  grid feedback, the remote-control and worn-morale fixes and the compact corner bars option are
  merged with their docs. #17 records measured build-speed options (ccache and mold are wired in
  the presets but off in the built trees).
- **Control-scheme research is parked on `research/controls`** — the unbound, overloaded and
  duplicated binding lists, the decision-model picks and the first key-guess survey (42 trials).
  No binding file changed. The survey's clearest signals: nobody guessed `x` for wait (`.` was the
  pick), nobody guessed `Enter` for the action list, and nobody guessed `h` for wield. Extend the
  survey with `tests/e2e/keyguess.py` before shipping any default.
- **Texture sweep** — `docs/fork/texture-sweep.md` (data on `research/textures`). Two empty-sprite
  bugs are fixed. #19 tracks the default tileset: its MShock-family provenance is unresolved and
  locked doors draw exactly like closed ones. RetroDays and its three derivatives are CC BY-SA 4.0.
- **Before/after playtests** — #20 is future work: paired real screenshots and a control-path
  comparison across revisions, with keys/clicks, menu hops, action counts and in-game time.
  Reuse the existing native harness. Do not treat the partial local screenshot experiment as a gate.
- **Driving dashboard** — #21 is future work: a Project Zomboid-inspired vehicle HUD that fits
  the fork's tiles and terminal graphics, preserves driving controls and keeps the compact readout
  available. Evaluate it with #20's future before/after harness.
- **Future tickets stay open** — #1 (agentic UI/UX QA in CI) and #2 (two-player co-op) are designed
  future work, neither implemented nor closable. #3 is the upstream feature-watch tracker; its
  checkpoint matches `upstream/main` and every candidate is still unchecked. #14 asks for number-key
  rows with item thumbnails in list menus (SotS: The Pit style). After the first fork release,
  make sure that #15's README download links resolve to the fork assets. #16's duration-based shards,
  readiness polling and local parallel runner are merged. Keep the issue open for its slow-test
  key-delay audit and prepared save fixtures.

  - **Shard timings and the gate** — `tests/e2e/durations.json` holds CI-measured times
    ([run 39740016172](https://github.com/Kenja-mc/Cataclysm-BN/actions/runs/39740016172): 723 /
    760 / 749 / 702 s, 8.3% spread, inside the 10% target). After changing the timings or
    `shard_of()`, refresh them from the `e2e-durations-shard-*` artifacts and run the full suite
    locally: a new split changes which tests share a game, and two order-dependent failures
    appeared only that way.
  - **Pooled games and vision** — `fixtures.retire` drops a shared game when a test changes an
    option in-game or fails, because the pool is keyed on the options it was created with. Tests
    that assert on what the player saw need `DEBUG_NIGHTVISION` and no rolled monsters: the start
    shelter can be very dark.
  - **Nightly-only failures** — the 2026-10-22 schedule was the first run of the live playtest
    legs and it found four bugs that push runs cannot see. `save_and_quit` retried nothing, so a
    menu the model left open swallowed the single Escape; it now repeats Escape until the row is
    on screen. The shard job failed on a tumbled watch (the sidebar then shows an approximate
    time, so the safe-mode test now asserts the avatar's position) and on an out-of-bounds sound
    assertion from an unbounded parking ring, whose modal popup then failed four later tests.
    CI run 39803692613 is green. Treat a red schedule as evidence, not noise.
  - **CI workflow changes merged**: the cross-platform matrix runs weekly and on dispatch.
    Pushes check one dry playtest leg; filtered dry dispatches retain their requested surface.
    The end-to-end cap is 90 minutes because a cold build alone took 37 minutes. Live legs run on
    free models inside the nightly schedule, and both the legs and the triage job now pass.
- **Next upstream merge** — the 2026-10-20 merge is `c682cb343a` (34 commits, base
  `5196022810`). It resolved five conflicts: `tankammo.json` and `generic/casing.json` keep
  upstream's `stackable`/`damage_states` and the fork's `looks_like`; `rifle ammo.json` keeps the
  new 8 mm uncrafts and drops every `bp_` entry the merge re-added; `handle_action.cpp` keeps the
  fork's mouse path with upstream's remembered-terrain autowalk condition; `newcharacter.cpp`
  keeps the fork's scene vehicle text. Merge `upstream/main` again from the issue #3 checkpoint and
  repeat the fold: drop the `bp_*` ammo recipes and uncrafts that the merge adds back
  (`data/json/uncraft/ammo/22.json`, `50bmg.json`, `tankammo.json`,
  `data/json/uncraft/ammo/rifle ammo.json`, `data/json/recipes/ammo/rifle.json`,
  `data/mods/exotic_ammo/uncrafts/ammo.json`), keep the new non-`bp_` entries, and re-check the
  `277_hybrid` recipe and the `Enter → Misc` action list.
- **Feature screenshots refreshed**: all ten captures from green CI run 39625972735 are published
  in `docs/fork/images/features/`. The HUD weather boxes, wounded body panel, Interact command
  list, shifted look selection and actual Sidebar Options editor were visually checked.
  The generator applies options to both compile-time config-directory modes and cleans up
  failed launches. Its modifier keys are sent as chords, not separate taps.
- **Community difficulty thread** — [`docs/fork/reddit-1x5xk5g-proposals.md`](docs/fork/reddit-1x5xk5g-proposals.md)
  collects what r/cataclysmbn asked for after one post about Bright Nights becoming easy. Most of it is
  balance work, which the fork rules leave out of scope.
- **Containers need root** — `bin/playtest-container.sh` runs the fork end-to-end suite and playtest
  scenarios in an unprivileged bubblewrap user namespace, which is the strongest isolation this host
  allows: the docker socket is root-only, `sudo` asks for a password, and the rootless extras
  (`rootlesskit`, `slirp4netns`, `fuse-overlayfs`) are absent. A docker image needs
  `sudo usermod -aG docker "$USER"` first.
- **Restore the build tools** — `ccache`, `mold` and `astyle` are missing on this machine, so the
  preset build stops at the first compile (`ccache: command not found`) and `--target format`
  reports `Artistic Style executable was not found`. Install with
  `pacman -S --needed ccache mold astyle`. The commits below were built and gated with them
  disabled (`-DCATA_CCACHE=OFF -DCMAKE_C_COMPILER_LAUNCHER= -DCMAKE_CXX_COMPILER_LAUNCHER= -DLINKER=`),
  with file-scoped formatting before each build.
- **Cut the first fork release** — `fork-release.yml` and its gate `fork-updater-test.yml` are in
  place but have never run. Dispatch `v0.1.0` as described in `docs/fork/releasing.md`, then check
  the Windows zip on a real Windows machine: SmartScreen, `Launch Bright Nights.bat`, and an
  update to `v0.1.1`. Upstream's release workflows stay disabled:
  nightlies need an initial `YYYY-MM-DD` tag and an `experimental` release, and `docs.yml` chains
  off Experimental Release.
- **Watch the CI runs** — the detached service `bn-playtest-watch` writes the conclusions of the
  `fork-playtest` run to `~/.local/state/cataclysm-bn/playtest-watch.log`. If the service is
  gone after a restart, read the runs straight from GitHub with
  `gh run list --workflow fork-playtest.yml --repo Kenja-mc/Cataclysm-BN`.
- The `matrix` workflow's red `clang, curses` job is a pre-existing cache-save error: with a warm
  ccache every compile is a hit, so the directory the action wants to save never appears.
- **Two CI traps worth remembering** — a leg matrix built from a job output must go on `matrix:` as the
  whole `{"include": [...]}` object; putting that object under `matrix.include` leaves `include` as an
  object instead of a list, and GitHub then creates **no job at all** and says nothing, which looks
  exactly like a job-level `if` that was false. Second, the two-core runners are far slower than this
  machine: suite tests take 58 to 145 seconds each there, so any harness check that samples the screen
  after a fixed key delay is a coin flip. The Lua console wait and the safe-mode hint now wait for the
  text they need instead of guessing.
- **The CI build keeps debug assertions on** — a game-side debugmsg opens a modal "An error has
  occurred!" popup that swallows every key, which stalls the harness and then fails every later test in
  that game. Seen with `Morale "Stylish" is inconsistent: lhs 7 != rhs N/A`, `morale.cpp:860`, which is
  game logic and therefore out of this fork's scope. `tmux_game.dismiss_error_popup` answers the popup
  and reports its text, and the suite calls it around every test so one assertion cannot poison five.
- **Vehicle-memory fixture** — the trailing sample starts at row 6, beyond the vehicle's rear.
  Weather animation is disabled; its private electric armored car has a solid rear because even
  mint-condition spawns randomly open doors. It avoids exhaust and camera vision, and every sampled
  cell must be hidden from direct sight. A transparent van and a camera-equipped tank were rejected.
  No redraw delay or post-drive cache invalidation is used.
- **Native vehicle reload warning** — an idling combustion engine reported out-of-bounds sounds
  after a same-session save/reload. The recraft fixture replaces unrelated vehicles before its
  first craft; this isolates the crafting regression, not a repair of the native vehicle lifecycle.
- **CI/CD overhaul series** — issue #12 tracks #6 to #11: decision-model playtesting, the fork suite in
  CI, a prepared build container, known failures, a performance gate and the release path. Issue #13
  holds thirteen end-to-end harness traps with their symptoms and fixes; the remaining work is to
  write them into the Gates section of `.agents/skills/test-quality/SKILL.md`.
- **Audit follow-ups** — `sdl_font.cpp` now scales oversized
  glyphs rather than cropping, which needs one manual visual check for configs still holding
  `FONT_WIDTH=8`/`FONT_HEIGHT=16`; the Controls strip can be squeezed off an 80x25 sidebar when the
  rolled messages make the Log panel taller, which is why the small-terminal e2e checks pin the Log
  off; `has_thermometer` scans the inventory on every draw because a per-turn cache showed a
  freshly picked-up thermometer a turn late.
- **Remaining playtest findings** — the pickup menu keeps `d`/`a` as mark/unmark: the menu has no
  horizontal movement to steal, the hint bar names both keys, and `test_wasd_menu_navigation` pins
  the behavior, so changing it is an owner decision rather than a fix. Stairs and save
  discoverability are handled by the new first-time tips.
- **Profile next hot paths** — scent/signature recompute and `sounds::process_sounds` during long rests.
- **Optional S-pack music adoption** — the installer now downloads Otopack separately for music
  and ambience. Adopting S-pack remains a separate decision; see `data/sound/Overhaul/CREDITS.md`.
- **Check redistribution rights before packaging** — resolve the gaps in
  [`asset-credits.md`](docs/fork/asset-credits.md), especially optional Otopack, Sokoban and
  the LARWICK font. Do not bundle optional downloaded audio under the Overhaul pack's CC0 grant.
- **Resolve the harvest inventory limitation** — both GitHub-backed repos lack `issues/`;
  the local helper fails with ENOENT, so the local draft count is unavailable, not zero.
  No new harvest drafts were created; existing policy work remains in #3 and command-post#102.
  New harness lessons went to the open #13 tracker instead, which owns the test-quality traps.
  See the [maintained harvest summary](../ai-stack/command-post/logs/harvest/summary.md).

## Accounts and credentials

Use native Git and GitHub credentials authorized for `Kenja-mc/Cataclysm-BN`. Keep repository
identity and credentials separate from global defaults; never put tokens in tracked files.

- **Commits** — check the repository-local `user.name` and `user.email` before committing.
  Use the fork maintainer's public GitHub identity and no-reply email.
- **Push** — confirm that `origin` points to `Kenja-mc/Cataclysm-BN` and use the existing native
  credential helper. Do not change global authentication or embed a token in a command.
- **GitHub API** — use `gh-fork` and always pass `--repo Kenja-mc/Cataclysm-BN`. The wrapper
  refuses upstream writes. Do not bypass it by supplying a raw `GH_TOKEN`.
- **Never touch the upstream** — `cataclysmbn/Cataclysm-BN` is a source to fetch and merge from,
  not a submission target. `git config core.hooksPath .githooks` enables the pre-push guard;
  `git remote set-url --push upstream DISABLED-fetch-only` disables upstream pushes. A fresh
  clone needs both guards. Fetching and merging upstream are unaffected.
- **Model credentials** — keep live credentials in the harness's native authentication or
  GitHub Actions secrets, not this repository. Look up current playtest models and secret
  requirements in `.github/workflows/fork-playtest.yml` and `docs/fork/agentic-playtests.md`.

## Install the fork and give feedback

See [`docs/fork/playing.md`](docs/fork/playing.md) for install, launch and playtest commands,
and [`docs/fork/feedback-template.md`](docs/fork/feedback-template.md) for feedback.
