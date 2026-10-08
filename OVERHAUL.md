# Bright Nights: Overhaul fork

This is a fork of [Cataclysm: Bright Nights](https://github.com/cataclysmbn/Cataclysm-BN) that tries to
make the game easier to pick up. The simulation, content and tone stay the same: same world, same
items, same zombies. The changes are to the controls, the look of the interface and the busywork
around managing items.

Upstream base: `cataclysmbn/Cataclysm-BN@d14e047` (first commit on this branch).

## Controls

Movement is **WASD**, with **Q E Z C** for diagonals. The arrow keys and the numpad still work.
The same keys move the cursor in look mode, targeting and the overmap, and answer every "which
direction?" prompt.

| Key       | Action                          | Key   | Action                           |
| --------- | ------------------------------- | ----- | -------------------------------- |
| `w a s d` | move                            | `x`   | wait a turn (also `.`)           |
| `q e z c` | move diagonally                 | Space | interact / examine               |
| `g`       | pick up from everything nearby  | `,`   | pick up from one tile            |
| `i`       | inventory                       | `u`   | use an item                      |
| `h`       | hold (wield)                    | `W`/`T` | wear / take off                |
| `f`       | fire                            | `r`   | reload                           |
| `t`       | throw                           | `b`   | bash (smash)                     |
| `o` / `O` | open / close                    | `j`   | jump                             |
| `D`       | drop (`Ctrl+D` drops to a side) | `E`   | eat or drink                     |
| `k`       | craft (`&` also works)          | `K`   | construct (`*` also works)       |
| `Q`       | **quick stack** to storage      | `Z`   | **sort the pile** you stand on   |
| `l`       | look around                     | `m`   | map                              |
| Tab       | attack nearest enemy            | Enter | action menu with every action    |
| `F1`      | help                            | `?`   | full keybinding list (any screen)|

When aiming: `f`/Enter fires, `x` aims one step, `u` `i` `o` pick aimed, careful or precise shots
(more care, left to right), `r` switches ammo, `F` or `m` switches fire mode.

On the overmap: `=`/`-` zoom, `R` toggles weather, `x` sets a waypoint.

A **Controls** strip at the bottom of the sidebar always shows the most used keys. It reads the
live keybindings, so it stays correct if you rebind anything.

Players with an existing `keybindings.json` keep their own bindings. Delete that file from the
config folder to get the new defaults.

## Look

- **Color theme** (Options → Graphics). The default, *Terminal*, takes your terminal's palette and
  background, so the game follows whatever theme your desktop uses (Omarchy, base16, pywal and so
  on). *Tokyo Night*, *Catppuccin*, *Gruvbox* and *Everforest* are built in for terminals that
  allow palette changes, and *Classic* keeps the original colors.
- On terminals with 16 colors, bright colors get their own color pairs instead of depending on
  bold text being drawn bright, which most modern terminals no longer do. Light and dark variants
  stay distinct and text no longer turns bold at random.
- Rounded window corners in the terminal version (Options → Graphics → Rounded window corners).

## Items and storage

Upstream expects you to set up loot zones and run a sorting activity to keep a base usable. Here
that is optional:

- **Quick stack (`Q`)**, as in Terraria and Hytale. Everything you carry goes into storage in line of sight
  nearby (shelves, lockers, counters, vehicle cargo) that already holds the same item, or mostly
  the same kind of item. Loose piles on the ground are left alone. Worn, wielded and favorited (`*` in the
  inventory) items always stay with you. It costs the time it takes to walk over and put things
  down.
- **Sort pile (`Z`)**. Dump a haul in one place, stand on it and press `Z`. Each item goes to the
  nearby storage that already holds the same thing or mostly the same category, or to a loose pile
  of exactly the same item. Put one example of
  each kind of thing where you want it to live, and everything else follows.
- **Bigger crafting reach.** Crafting and construction pull from items within 12 tiles (upstream:
  6), so a workshop with stocked shelves works like a Hytale workbench next to chests. You can
  change it under Options → Debug → Crafting range.

Zones and the loot-sorting activity are still there for anyone who wants them. They just have no
default key.

## Building

Same as upstream; see `docs/en/dev/guides/building`. The terminal version:

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCURSES=ON -DTILES=OFF -DSOUND=OFF -DTESTS=OFF
ninja -C build cataclysm-bn
./cataclysm-bn
```

## End-to-end tests

`tests/e2e/run.py` starts the terminal build inside tmux, creates a character and plays through the
new controls, quick stack and sort pile by sending real key presses and reading the screen. It
needs `tmux` and a built `cataclysm-bn` binary at the repo root:

```sh
python3 tests/e2e/run.py
```
