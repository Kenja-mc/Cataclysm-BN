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
| `F`       | attack in a direction           | Tab   | attack the nearest enemy         |
| Enter     | action menu with every action   | `N`   | switch fire mode                 |
| `F1`      | help                            | `?`   | full keybinding list (any screen)|

Walking into an enemy no longer attacks it. It tells you to press `F`, so a stray step never
starts a fight (Options → Interface → Attack by walking into enemies turns bump attacks back on).
Walking into a closed door still opens it.

The mouse works alongside the keyboard in the terminal: click a tile to preview the route, click
again to walk there, and right-click to examine or act on what is there.

When aiming: `f`/Enter fires, `x` aims one step, `u` `i` `o` pick aimed, careful or precise shots
(more care, left to right), `r` switches ammo, `F` or `m` switches fire mode.

On the overmap: `=`/`-` zoom, `R` toggles weather, `x` sets a waypoint.

A **Controls** strip at the bottom of the sidebar always shows the most used keys. It reads the
live keybindings, so it stays correct if you rebind anything.

**Classic controls** are one option away: Options → Interface → Control scheme → Classic restores
the original vi-keys and numpad layout, turns bump attacks back on and makes Y/N prompts want
capitals. Your own key changes are kept in both schemes, because the game now saves only the keys
you changed. The modern layout lives in `data/raw/control_schemes/modern.json` on top of the
untouched upstream keybindings, so other schemes can be added the same way. Quick stack, sort pile
and attack have no key in classic; bind them or use the Enter action menu.

A `keybindings.json` saved by an older version holds every key, so it overrides either scheme.
Delete it from the config folder to follow the scheme again.

Your first new game opens with a short welcome card listing these keys (Options → Interface →
Show welcome card brings it back). Yes/no prompts accept lowercase `y`/`n`, since those letters no
longer move you.

## Look

- **Color theme** (Options → Graphics). The default, *Terminal*, takes your terminal's palette and
  background, so the game follows whatever theme your desktop uses (Omarchy, base16, pywal and so
  on). *Tokyo Night*, *Catppuccin*, *Gruvbox* and *Everforest* are built in for terminals that
  allow palette changes, and *Classic* keeps the original colors.
- On terminals with 16 colors, bright colors get their own color pairs instead of depending on
  bold text being drawn bright, which most modern terminals no longer do. Light and dark variants
  stay distinct and text no longer turns bold at random.
- Rounded window corners in the terminal version (Options → Graphics → Rounded window corners).
  Borders are drawn as real Unicode in UTF-8 terminals, which many terminals render better than the
  old line-drawing character set. Map walls keep square corners.
- Quieter main menu and a clearer pick-up list.

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

- **Advanced inventory (`/`) opens like a loot window**: everything around you on the left, your
  inventory on the right. Upstream's default pointed at the empty tile below you.
- **Crafting (`k`) opens on something useful**: recent recipes, or the first category you can
  craft from, not an empty favorites list.
- **One pick-up list**: `g` shows everything within reach in one list.

- **Fewer battery types.** The light-minus, high-capacity and disposable variants are folded into
  three cells: light (150 charge), medium (750) and heavy (1500). Atomic cells stay as the rare
  long-life option, along with car and storage batteries. That is 9 batteries instead of 19, and
  every device takes the one cell size that fits it. Old saves convert automatically.
- **No duplicate containers.** The plastic 30-gallon barrel, steel keg, medium cardboard box, bag in
  a box and squeeze tube were near-copies of other containers and are merged into them.

- **Black powder handloads stack with factory rounds.** The 75 `bp_*` ammo items are gone. A
  black powder round is the normal round with a *black powder* stack modifier, so 30 factory 9mm
  and 10 handloads make one stack, shown as `9mm JHP (40, 10 black powder)`. Each shot rolls which
  round fires, and only black powder shots hit softer, spread wider and kick less. Loading,
  unloading and splitting keep the right share of handloads; handloads can't be pulled apart for
  smokeless powder. The handloading recipes are still there, listed as `9mm JHP (black powder)`.

- **Jewelry: 292 items down to 9.** Rings, bracelets, earrings, necklaces, lockets, hairpins,
  tiaras, cufflinks and dental grills are one item each. The metal and gem are a variant the piece
  remembers, so you still find a "ruby and gold ring" or a "copper bracelet". Each one keeps its
  own price, material and melt-down parts (the ruby and the gold). Loot tables still name the exact
  piece they used to, and old saves convert. Pieces with a use or a story of their own stay
  separate: watches, badges, medals, holy symbols, wedding, engagement, purity and signet rings.
- **Books, games and belts.** The same treatment applies to 30 novels and other light reading,
  which become one *paperback* ("western novel", "Murdered by the Grapevine", "book of poetry").
  Eight board and tabletop games become two items, and seven judo belts become one. Professions
  still start with the exact piece (the black belt, the gold necklace).
- **Jewelry stacks.** Different rings share one stack, like items in Don't Starve: "3 rings".
  Each ring still keeps its own name, gem, metal and price, so a stack is worth what its pieces
  are worth. With a tileset, each piece shows the sprite of the item it used to be.
- **Food of any freshness stacks**, with its rot averaged, as in Don't Starve. Rotten food never joins
  fresh food. Options → General → Freshness similarity threshold brings back the stricter
  upstream rule (0.25).
- **One MRE.** The 26 MRE boxes are one *MRE*. The entree is a variant
  (`MRE - Chili & Beans`), and opening it still gives that entree.

Zones and the loot-sorting activity are still there for anyone who wants them. They just have no
default key.

## Firearms

The guns and calibers CDDA cut over the years (5.45x39, 5.7x28, 4.6x30, 7.62x25, 9x18, .454,
.460, .500 S&W, .38 Super, .270 Win and .700 NX, with the AK-74M, AN-94, FN P90, Five-seveN, MP7,
PPSh-41, Tokarev, Makarov, S&W 500, Raging Bull and friends) live in Bright Nights' *Exotic ammo
types* mod. It is now on by default for new worlds, so they spawn in normal loot. Leave it off
when creating a world if you prefer fewer calibers.

## Stack modifiers (for modders)

Variants that differ only by a uniform tweak do not need their own item type. Define the tweak
once and let stacks count how many of their units carry it:

```json
{
  "type": "stack_modifier",
  "id": "black_powder",
  "name": { "str": "black powder" },
  "damage": 0.8,
  "armor_penetration": 0.5,
  "dispersion": 1.2,
  "recoil": 0.76,
  "blocks_disassembly": true
}
```

- A recipe marks its output with `"result_stack_modifier": "black_powder"`.
- A `MIGRATION` with `"stack_modifier": "black_powder"` turns an old item id into the base item
  with every unit modified, so saves keep their handloads.
- Stacks merge regardless of modifiers; counts add up on merge and split proportionally.
- The shot multipliers apply per round fired. Other kinds of modifier can reuse the same counting
  and only need their own effect hook.

## Item variants (for modders)

For items that differ only in looks, price, material and the parts they break down into, give the
item type variants instead of new item types:

```json
{
  "type": "item_variants",
  "id": "jewelry_ring",
  "variants": [
    {
      "id": "ruby_gold_ring",
      "name": { "str": "ruby and gold ring" },
      "description": "…",
      "weight": 50,
      "price_multiplier": 0.33,
      "material": [ "gold", "gemstone" ],
      "components": [ [ "gold_small", 2 ], [ "ruby", 1 ] ]
    }
  ]
}
```

- `"cosmetic": true` lets items of different variants stack. A stack of mixed pieces is named
  after the item type.
- A variant's `color` sets its glyph color in the terminal (a black belt is drawn black).
- A variant's `looks_like` names the tileset sprite to use (the variant id by default). If the
  tileset lacks it, the item type's sprite is used.
- A new item picks a variant by `weight` and keeps it.
- Name, description, price and material follow the variant.
- Disassembling a found piece yields the item type's own recipe plus the variant's `components`.
  A crafted piece yields what it was made from.
- Profession item lists can name it too: `{ "item": "judo_belt", "variant": "judo_belt_black" }`.
- An item group entry can name the variant: `{ "item": "jewelry_ring", "variant": "gold_ring" }`.
- A recipe can make a variant: `"result": "jewelry_ring", "result_variant": "gold_ring"` (with an
  `id_suffix` when several recipes share a result).
- A `MIGRATION` with `"variant": "gold_ring"` maps an old item id onto the right variant.

## Bug fixes

- Starting any activity (crafting, for example) next to NPCs crashed: a range-for loop iterated a
  temporary that was already destroyed.
- Repeating the last craft crashed after save, quit to menu and reload in one session
  ([upstream #10083](https://github.com/cataclysmbn/Cataclysm-BN/issues/10083)).
- Generating the collapsed office tower crashed
  ([upstream #9875](https://github.com/cataclysmbn/Cataclysm-BN/issues/9875)).
- The electromagnetic unit crashed when pulled metal hit a monster
  ([upstream #9354](https://github.com/cataclysmbn/Cataclysm-BN/issues/9354)).
- Character creation's overview no longer draws stats on top of their labels in the terminal.

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
