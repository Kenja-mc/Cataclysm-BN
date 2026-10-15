# Cataclysm: BN - Open Work

## Next actions

- **Validate and push local work** — run the software-GPU unit shards and full serial e2e suite
  before pushing. Both game builds, the test-binary build and `--check-all-mods` pass.
  Tutorial-control work passes 32 live-game scenarios plus native tiles HUD checks at both
  sidebar origins. Preserve the separate Xvfb display fix in local history.
- **Normal correctness review** — the completed review covered complexity only. Investigate the
  temporary-item invocation branches in `src/avatar_functions.cpp` and the player-visible
  kamikaze diagnostic in `src/monattack.cpp`; reviewer suspicions are not verified defects.

- **Remaining playtest findings** — pickup menu `d`/`a` marking vs WASD navigation in Modern; stairs and save discoverability for new players.
- **Profile next hot paths** — scent/signature recompute and `sounds::process_sounds` during long rests.
- **Apply [AGENTS.md build-docs fix](https://github.com/Kenja-mc/Cataclysm-BN/issues/4)** — Part 1 Build commands contradict the preset/shard-runner workflow actually used.
- **Apply [test-quality e2e gate](https://github.com/Kenja-mc/Cataclysm-BN/issues/5)** — pin or strip rolled world state (weather, NPC/avatar gear, morale) in e2e fixtures.
- **Optional S-pack music adoption** — the installer now downloads Otopack separately for music
  and ambience. Adopting S-pack remains a separate decision; see `data/sound/Overhaul/CREDITS.md`.

## Install the fork and give feedback

See [`docs/fork/playing.md`](docs/fork/playing.md) for install, launch and playtest commands,
and [`docs/fork/feedback-template.md`](docs/fork/feedback-template.md) for feedback.
