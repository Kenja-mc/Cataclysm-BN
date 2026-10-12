# Cataclysm: BN - Open Work

## Next actions
- **Await user decision on S-pack music adoption** — the Overhaul soundpack was selected as the default only where no existing music exists and redistribution is permitted. See `data/sound/Overhaul/CREDITS.md`.

## Install the fork and give feedback
```sh
./bin/install-cataclysm-bn.sh      # app menu launchers (terminal / tiles), basepath config
cataclysm-bn | cataclysm-bn-tiles  # launch
python3 tests/e2e/playtest.py quick_stack   # set up a scenario, play, Ctrl+B D to detach
bin/feedback "title" -m "note"       # record feedback quickly
```
Full write-up: [`docs/fork/playing.md`](docs/fork/playing.md). Feedback template: [`docs/fork/feedback-template.md`](docs/fork/feedback-template.md).

## Tool caveats
- `bash` tool is failing with a schema error ("Service mode does not accept async or timeout; use ready.timeout for readiness"); use eval (Python) for anything requiring the shell.
