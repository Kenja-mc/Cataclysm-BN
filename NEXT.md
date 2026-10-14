# Cataclysm: BN - Open Work

## Next actions
- **Push `main` to origin** — 5 local commits (upstream merge through `4fd1dbea60` plus controls/tiles/tests/docs) are verified but unpushed: `asmartin-ai` gets 403 on `Kenja-mc/Cataclysm-BN`. Push as the repo owner, then confirm CI.
- **Apply [AGENTS.md build-docs fix](https://github.com/Kenja-mc/Cataclysm-BN/issues/4)** — Part 1 Build commands contradict the preset/shard-runner workflow actually used.
- **Apply [test-quality e2e gate](https://github.com/Kenja-mc/Cataclysm-BN/issues/5)** — pin or strip rolled world state (weather, NPC/avatar gear, morale) in e2e fixtures.
- **Await user decision on S-pack music adoption** — the Overhaul soundpack was selected as the default only where no existing music exists and redistribution is permitted. See `data/sound/Overhaul/CREDITS.md`.

## Install the fork and give feedback
```sh
./bin/install-cataclysm-bn.sh      # app menu launchers (terminal / tiles), basepath config
cataclysm-bn | cataclysm-bn-tiles  # launch
python3 tests/e2e/playtest.py quick_stack   # set up a scenario, play, Ctrl+B D to detach
bin/feedback "title" -m "note"       # record feedback quickly
```
Full write-up: [`docs/fork/playing.md`](docs/fork/playing.md). Feedback template: [`docs/fork/feedback-template.md`](docs/fork/feedback-template.md).
