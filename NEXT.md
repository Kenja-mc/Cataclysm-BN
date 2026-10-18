# Cataclysm: BN - Open Work

## Next actions

- **Future tickets stay open** — #1 (agentic UI/UX QA in CI) and #2 (two-player co-op) are designed
  future work, neither implemented nor closable. #3 is the upstream feature-watch tracker; its
  checkpoint matches `upstream/main` and every candidate is still unchecked.
- **Next upstream merge** — the 2026-10-16 merge is `1a883dd7b5`. Merge `upstream/main` again from the
  issue #3 checkpoint and repeat the fold: drop the `bp_*` ammo recipes and uncrafts that the merge adds
  back (`data/json/uncraft/ammo/22.json`,
  `50bmg.json`, `tankammo.json`, `data/json/uncraft/ammo/rifle ammo.json`,
  `data/json/recipes/ammo/rifle.json`, `data/mods/exotic_ammo/uncrafts/ammo.json`), keep the new
  non-`bp_` entries, and re-check the `277_hybrid` recipe and the `Enter → Misc` action list.
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
- **Release workflows stay disabled** — Nightly Release, Experimental Release and Manual release are
  off; `gh workflow enable "<name>"` re-enables them. The nightlies need an initial `YYYY-MM-DD` tag
  and an `experimental` release before they can pass, and `docs.yml` chains off Experimental Release.
- **Watch the CI runs** — the detached service `bn-playtest-watch` writes the conclusions of the
  `fork-playtest` run to `/home/kenja/.local/state/cataclysm-bn/playtest-watch.log`. If the service is
  gone after a restart, read the runs straight from GitHub with
  `gh run list --workflow fork-playtest.yml --repo Kenja-mc/Cataclysm-BN`.
- **CI state** — `fork-playtest.yml` plans cleanly: it names the legs, and without the model secrets it
  runs one dry leg plus the end-to-end suite in four shards, because a single runner cannot finish all
  140 checks inside a two-hour job. The tiles jobs need ImageMagick, which the runners ship as the 6.x
  binaries rather than the 7.x `magick` shim; `tests/e2e/tiles.py` accepts either. The `matrix`
  workflow's red `clang, curses` job is a pre-existing cache-save error: with a warm ccache every
  compile is a hit, so the directory the action wants to save never appears.
- **CI/CD overhaul series** — issue #12 tracks #6 to #11: decision-model playtesting, the fork suite in
  CI, a prepared build container, known failures, a performance gate and the release path. Issue #13
  lists the end-to-end harness traps to write into the test-quality skill.
- **Audit follow-ups** — the weather box measures only its date row when fitting, so a long weather
  name truncates the temperature instead of widening the box; `sdl_font.cpp` now scales oversized
  glyphs rather than cropping, which needs one manual visual check for configs still holding
  `FONT_WIDTH=8`/`FONT_HEIGHT=16`; the Controls strip can be squeezed off an 80x25 sidebar when the
  rolled messages make the Log panel taller, which is why the small-terminal e2e checks pin the Log
  off; `has_thermometer` scans the inventory on every draw because a per-turn cache showed a
  freshly picked-up thermometer a turn late.
- **Remaining playtest findings** — pickup menu `d`/`a` marking vs WASD navigation in Modern; stairs and save discoverability for new players.
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
  issues, comment or read secrets. Use `gh-fork` (in `~/.local/bin`) or prefix a call with
  `GH_TOKEN=$(gh auth token --user Kenja-mc)`, and always pass `--repo Kenja-mc/Cataclysm-BN`.
- **Model secrets** — `XPL_SK_AGENT` and `OC_SK_AGENT` are still not repository secrets, verified
  with the admin token, so the agentic playtest legs stay on the dry path until they are added.
  Experiential Labs also needs a saved card with one settled charge of $1 or more, and its credit
  overflow switch left off: without both, a call past the free allowance bills credits.

## Install the fork and give feedback

See [`docs/fork/playing.md`](docs/fork/playing.md) for install, launch and playtest commands,
and [`docs/fork/feedback-template.md`](docs/fork/feedback-template.md) for feedback.
