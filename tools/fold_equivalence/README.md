# Fold equivalence check

The fork folds duplicate items into one id with a migration, sometimes adding an item variant or a
stack modifier. Folding may change balance (an accepted exception, see `AGENTS.md`), but it must not
break play: a spawned item has to keep the charges, contents, effects and salvage the player saw
before.

This check compares every removed item against the item its migration produces, using the game's
own loader and save code rather than a hand-written `copy-from` resolver.

## What the files are

| Path | Role |
|---|---|
| `tools/fold_equivalence/extract.py` | Static pass: resolves `copy-from`, diffs spawn references, recipes, craftability and magazine compatibility. |
| `tools/fold_equivalence/fold_data.py` | Shared JSON loading and resolution helpers. |
| `tools/fold_equivalence/compare.py` | Compares two runtime dumps field by field; exits non-zero on any difference. |
| `tests/fold_equivalence/baseline.json` | Mainline dump for the merge-base, recorded once with `--dump-stats FOLDED`. |
| `tests/fold_equivalence/allowlist.json` | Deliberate differences. Empty means every difference is reported. |
| `src/fold_dump.cpp` | The in-game dump: `--dump-stats FOLDED <requests-or-baseline.json>`. |

## Run it

Both sides load core data plus the mods the folds live in (for example `exotic_ammo`), spawn each
request the way map generation would, and record the item's properties and its save JSON.

```sh
# static: removed ids, migrations, spawn references, recipes
python3 tools/fold_equivalence/extract.py --mainline /path/to/mainline --fork . \
  --requests /tmp/fold_requests.json --report /tmp/fold_static.json --markdown /tmp/fold_static.md

# runtime: fork dump against the recorded mainline baseline
out/build/linux-curses/src/cataclysm-bn --basepath ./ --dump-stats FOLDED \
  tests/fold_equivalence/baseline.json > /tmp/fold_fork.json
python3 tools/fold_equivalence/compare.py tests/fold_equivalence/baseline.json /tmp/fold_fork.json
```

`compare.py` prints one line per differing field (old id, new id, view, field, mainline, fork) and
exits 1 while differences remain. `fresh` and `save-migrated` views are checked separately: the
first proves new spawns, the second proves old saves survive the migration.

Re-record the baseline after merging upstream and after any intentional fold change:

```sh
git -C /path/to/mainline worktree add /tmp/mainline-base <merge-base>
# in that tree, apply the fold dump support from this repo's src/fold_dump.*, src/dump.cpp and
# src/init.* hook, then:
cmake -S /tmp/mainline-base -B /tmp/mainline-base/build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/mainline-base/build --target cataclysm-bn -j
/tmp/mainline-base/build/src/cataclysm-bn --basepath /tmp/mainline-base/ --dump-stats FOLDED \
  /tmp/fold_requests.json > tests/fold_equivalence/baseline.json
```

Accepted balance changes stay visible in the report; classify them in the commit message instead
of allowlisting them. Only presentation (name, description, color, symbol) is ignored by
`compare.py`.
