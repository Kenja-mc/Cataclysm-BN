# Cataclysm: BN - Open Work

## Next actions

- **Future tickets stay open** — #1 (agentic UI/UX QA in CI) and #2 (two-player co-op) are designed
  future work, neither implemented nor closable. #3 is the upstream feature-watch tracker; its
  checkpoint matches `upstream/main` and every candidate is still unchecked. #14 asks for number-key
  rows with item thumbnails in list menus (SotS: The Pit style); #15 covers the README download
  badges that still point at upstream releases. #16's duration-based shards, readiness polling and
  local parallel runner are merged. Keep the issue open: its remaining phases are the slow-test
  key-delay audit and prepared save fixtures, and the observed CI shard spread is still 29.6%,
  above its 10% target.

  - **E2E runtime verified**: the final local parallel run passed 141/141 in 593 seconds.
    [CI run 39625972735](https://github.com/Kenja-mc/Cataclysm-BN/actions/runs/39625972735)
    passed all 141 tests in four jobs, with the slowest job taking 15m12s including its build.
    Total CI test time was 2610.5 seconds; the two mouse tests took 190.6 seconds combined.
    Reloading waits for each menu and loaded round. Its fixture clears earlier wounds and morale;
    the sleep fixture has storage so its watch cannot fall out of a full starting outfit.
    Data checking reported no errors. All five upstream unit shards exited 0 using software
    Vulkan; one test failed as expected and translation checks skipped missing MO files.
  - **CI workflow changes merged**: the cross-platform matrix runs weekly and on dispatch.
    Pushes check one dry playtest leg; filtered dry dispatches retain their requested surface.
    The end-to-end cap is 90 minutes because a cold build alone took 37 minutes. The final
    modern keyboard-and-mouse tiles dispatch passed both dry scenarios. Live model legs and
    nightly triage remain unverified without model secrets.
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
  `sudo usermod -aG docker kenja` first.
- **Restore the build tools** — `ccache`, `mold` and `astyle` are missing on this machine, so the
  preset build stops at the first compile (`ccache: command not found`) and `--target format`
  reports `Artistic Style executable was not found`. Install with
  `pacman -S --needed ccache mold astyle`. The commits below were built and gated with them
  disabled (`-DCATA_CCACHE=OFF -DCMAKE_C_COMPILER_LAUNCHER= -DCMAKE_CXX_COMPILER_LAUNCHER= -DLINKER=`),
  so no astyle pass has reformatted the tree.
- **Local tiles binary is stale**: it reports `60e711cc78` and rejects current data. Rebuild it
  from a clean source tree before local tiles verification; the tiles checks above used CI's
  freshly built binaries. The uncommitted HUD experiment remains untouched.
- **Release workflows stay disabled** — Nightly Release, Experimental Release and Manual release are
  off; `gh workflow enable "<name>"` re-enables them. The nightlies need an initial `YYYY-MM-DD` tag
  and an `experimental` release before they can pass, and `docs.yml` chains off Experimental Release.
- **Watch the CI runs** — the detached service `bn-playtest-watch` writes the conclusions of the
  `fork-playtest` run to `/home/kenja/.local/state/cataclysm-bn/playtest-watch.log`. If the service is
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
  lists the end-to-end harness traps to write into the test-quality skill.
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
  See the [maintained harvest summary](../ai-stack/command-post/logs/harvest/summary.md).

## Accounts and credentials

This repository belongs to the `Kenja-mc` GitHub account. The workstation's active `gh` account is
a different one, so both the identity and the push credential are pinned per repository.

- **Commits** — `.git/config` sets `user.name` and `user.email` to `Kenja-mc`, so the global identity
  never applies here.
- **Push** — `.git/config` sets a `credential.https://github.com.helper` that reads the Kenja-mc
  token from the gh keyring at push time, so `git push origin main` needs no flags and no inline
  helper. Nothing global changes and no token is written to disk.
- **gh** — the active account is `asmartin-ai`, which has pull-only access here: it cannot open
  issues, comment or read secrets. Use `gh-fork` (in `~/.local/bin`), which sets the Kenja-mc token
  for one call and refuses to change anything in `cataclysmbn/Cataclysm-BN`. Always pass
  `--repo Kenja-mc/Cataclysm-BN`. Do not prefix a call with a raw `GH_TOKEN` instead: that path has
  no guard.
- **Never touch the upstream** — `cataclysmbn/Cataclysm-BN` is a source to merge from and nothing
  else. Six CI issues were filed there by mistake, closed as off-topic, and the account was blocked
  for it, so the guards are deliberate. `git config core.hooksPath .githooks` enables the pre-push
  hook, `git remote set-url --push upstream DISABLED-fetch-only` blocks the push at the remote, and
  `gh-fork` blocks the API path; a fresh clone needs the first two again. Fetching and merging
  upstream are unaffected.
- **Model secrets** — `XPL_SK_AGENT` and `OC_SK_AGENT` are still not repository secrets, verified
  with the admin token, so the agentic playtest legs stay on the dry path until they are added.
  Experiential Labs also needs a saved card with one settled charge of $1 or more, and its credit
  overflow switch left off: without both, a call past the free allowance bills credits.

## Install the fork and give feedback

See [`docs/fork/playing.md`](docs/fork/playing.md) for install, launch and playtest commands,
and [`docs/fork/feedback-template.md`](docs/fork/feedback-template.md) for feedback.
