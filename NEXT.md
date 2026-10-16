# Cataclysm: BN - Open Work

## Next actions

- **Validate before pushing** — run `--check-all-mods` against the current binaries, the complete
  software-GPU unit shards, then `python3 tests/e2e/run.py` serially with no concurrent heavy work.
  Focused scenarios and native HUD/mouse checks do not replace these publication gates. Use
  the `out/build/linux-{curses,full}` preset outputs; reconcile the older instructions in #4.
- **Investigate unverified correctness findings** — inspect the temporary-item invocation
  branches in `src/avatar_functions.cpp` and the player-visible kamikaze diagnostic in
  `src/monattack.cpp`. The completed controls/HUD review does not resolve these older suspicions.

- **Remaining playtest findings** — pickup menu `d`/`a` marking vs WASD navigation in Modern; stairs and save discoverability for new players.
- **Profile next hot paths** — scent/signature recompute and `sounds::process_sounds` during long rests.
- **Apply [AGENTS.md build-docs fix](https://github.com/Kenja-mc/Cataclysm-BN/issues/4)** — Part 1 Build commands contradict the preset/shard-runner workflow. `OVERHAUL.md`'s Unit tests section also uses legacy `build/` paths.
- **Apply [test-quality e2e gate](https://github.com/Kenja-mc/Cataclysm-BN/issues/5)** — pin or strip rolled world state (weather, NPC/avatar gear, morale) in e2e fixtures.
- **Optional S-pack music adoption** — the installer now downloads Otopack separately for music
  and ambience. Adopting S-pack remains a separate decision; see `data/sound/Overhaul/CREDITS.md`.
- **Check redistribution rights before packaging** — resolve the gaps in
  [`asset-credits.md`](docs/fork/asset-credits.md), especially optional Otopack, Sokoban and
  the LARWICK font. Do not bundle optional downloaded audio under the Overhaul pack's CC0 grant.
- **Review retained dirty worktrees before further cleanup** — `../bn-wt-crafting-ui`,
  `../bn-wt-npc-ui` and `../bn-wt-render` contain changes. Recovery archives and retained branch
  references are recorded in
  `/home/kenja/.local/state/cataclysm-bn/worktree-backups/20261015-203130-bb0f4407/manifest.json`.
- **Resolve the harvest inventory limitation** — both GitHub-backed repos lack `issues/`;
  the local helper fails with ENOENT, so the local draft count is unavailable, not zero.
  No new harvest drafts were created; existing policy work remains in #4, #5 and command-post#102.
  See the [maintained harvest summary](../ai-stack/command-post/logs/harvest/summary.md).

## Install the fork and give feedback

See [`docs/fork/playing.md`](docs/fork/playing.md) for install, launch and playtest commands,
and [`docs/fork/feedback-template.md`](docs/fork/feedback-template.md) for feedback.
