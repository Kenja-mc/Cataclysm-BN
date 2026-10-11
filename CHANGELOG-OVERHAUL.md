# Bright Nights Overhaul changelog

Changes this fork makes on top of [Cataclysm: Bright Nights](https://github.com/cataclysmbn/Cataclysm-BN).
`OVERHAUL.md` explains each feature in detail; `docs/fork/visual-changes.md` shows them.
Upstream's own changes are in `docs/en/game/changelog`.

## 2026-10-10

### Added

- Auto-explore (`n`): each press walks to the nearest reachable spot that borders ground you have
  not seen, around walls, closed doors, known traps and dangerous fields. It refuses while a
  hostile is in view. No key in the classic scheme; it is in the Enter action menu.
- A keyboard diagram of the modern scheme in `OVERHAUL.md`
  ([`docs/fork/images/controls-modern.svg`](docs/fork/images/controls-modern.svg)).
- The welcome card and Controls strip show the auto-explore key, and a first tip suggests a
  starter goal: find water, food and a weapon, because houses usually have all three.
- **Combine** in the item menu (`C` in the modern scheme): pours partly used tools that nothing
  refills, such as matchbooks, into one. Charges are kept. Duct tape already stacked.
- Gun and ammo info show how loud a shot is (from the same noise the game makes when firing; an
  unloaded gun uses its default ammo).
- 88 items without a sprite in the default tileset now borrow the sprite of a close relative
  (`looks_like`), for example soda syrups, 25/105/155 mm shells and carbon frames.

### Changed

- Modern scheme, tiles: the mouse wheel zooms and `Ctrl+N` toggles the pixel minimap. Their
  upstream keys (`z`, `Z`, `N`) are taken by movement, sort pile and fire mode, which left them
  unreachable.
- The Controls strip lists `look` last, so it is the hint that drops off a full strip.
- Sidebar rows share one label width and column grid in every layout, with one space after each
  colon. The Body panel lists hurt limbs without the stick figure. The standalone Sound panel is
  hidden by default because the Movement row already shows the sound level.
- The crafting menu's full-description search (`d:`) caches each recipe's description, so only
  the first search in a turn is slow (CDDA #77914).

### Fixed

- Picking an entry from the right-click tile menu did nothing.
- Binding a key back to its upstream default in the modern scheme was lost on restart.
  `keybindings.json` now starts with a format marker.
- Clicking "fire at" a monster aimed at the nearest hostile instead of that monster.
- Built-in color themes left the terminal palette changed after quitting; the game now resets it.
- The weather and weapon boxes drew Unicode frames on non-UTF-8 terminals.
- Black powder rounds loaded in a revolver or other integral magazine lost their modifier when an
  older save was loaded.
- A recipe with both a result variant and a stack modifier dropped the modifier from its name.
- Auto-explore said "Nothing left to explore nearby" when the pathfinder refused the nearest
  unexplored spot; it now tries the next nearest ones.
- Running the whole unit suite in one process used unbounded memory after the sound resize test.

## 2026-10-09

### Added

- Weather and weapon boxes on the map, each movable to any corner or off, with Unicode, Nerd Font
  or ASCII icons.
- Body panel in the sidebar inspired by Project Zomboid: limbs coloured by health, wounds beside
  them, `H` for every limb's details.
- Readable map glyphs: trees ♣, pines ♠ and saplings τ instead of the digits 7, 4 and 1 (option).
- The welcome card asks Permadeath or Roleplay (reload the last save on death), like Caves of Qud.
- First-time tips for hunger, thirst, tiredness, wounds, overload, hostiles and night (option).
- The mouse hover hint names the key for the same action; the welcome card mentions the mouse.
- Yes/No prompts are selectable buttons that open on No (Y/N hotkeys are an option).
- Vehicle screen: WASD and QEZC move the cursor; the actions they shadowed moved to Shift.
- Item groups accept a `stack_modifier`, so black powder loot spawns as black powder.
- `docs/fork/visual-changes.md` with screenshots, `AGENTS.md` fork guide in Simplified Technical English.
- End-to-end tests for every new feature (36 tests).

### Changed

- Merged upstream `main` (19 commits); new 7.62x54R 7N1 rounds fold into the black powder modifier.
- Classic control scheme follows upstream in full, even when set only in `options.json`.
- A `keybindings.json` from an older version no longer cancels the control scheme.
- Quick stack and sort pile need a walkable line, not just sight.
- The Hitchhiker's Guide moved from `H` to `J` in the modern scheme.

### Fixed

- Upstream [#10388](https://github.com/cataclysmbn/Cataclysm-BN/issues/10388): manual technique
  menu greyed out kicks for styles that kick with a weapon in hand.
- Upstream [#10117](https://github.com/cataclysmbn/Cataclysm-BN/issues/10117): hacking a card
  reader opened only the nearest doors.
- Upstream [#10353](https://github.com/cataclysmbn/Cataclysm-BN/issues/10353): the rope below a
  vehicle ladder was invisible in the terminal.
- Upstream [#10429](https://github.com/cataclysmbn/Cataclysm-BN/issues/10429): followers overdosed
  on painkillers.
- Upstream [#10415](https://github.com/cataclysmbn/Cataclysm-BN/issues/10415): suppressed small
  guns go "plink!" again.
- Upstream [#9617](https://github.com/cataclysmbn/Cataclysm-BN/issues/9617) and
  [#870](https://github.com/cataclysmbn/Cataclysm-BN/issues/870): item search and list-items fixes.
- Black powder counts stay right through partial vehicle stashes, liquid fills and restacks.
- Old saves: unified batteries are trimmed to their new capacity; folded books stay identified.
- Attack commands never swap places with pets or talk to friends.
- The fluid grid unit test no longer depends on where earlier tests left the map.
- Text formatting rejected argument numbers containing a 9 after the first digit (`%19$s`), an
  upstream bug that a longer welcome card hit.
- Saplings were never flagged `YOUNG` internally, so burnt, fungal and trail map extras skipped them.
- The map in the terminal printed Unicode terrain symbols as a single byte; they now print in full.
- Yes/No buttons without hotkeys showed "[n/a] Yes"; they now read "Yes".

## 2026-10-08

### Added

- Modern control scheme (WASD, QEZC diagonals) merged with Sword of the Stars: The Pit: `F`
  attacks the nearest enemy, Space interacts, `X` waits; classic vi-keys one option away.
- Mouse tile selection: hover to preview the route and action, click to act, right-click for options.
- Quick stack (`Q`) and sort pile (`Z`) instead of loot zones.
- Controls strip in the sidebar and a one-time welcome card.
- Modern terminal look: palette themes (Terminal, Tokyo Night, Catppuccin, Gruvbox, Everforest),
  rounded borders.
- Item consolidation: 19 battery cells to 9, near-duplicate containers merged, jewelry, MRE boxes,
  novels, board games and judo belts folded into item variants that stack like Don't Starve items,
  black powder handloads folded into a stack modifier. Old saves migrate.
- The Limited Zombie Revival mod (sagittarius72, MIT) as an optional mod.
- tmux end-to-end test harness.

### Changed

- Walking into enemies no longer attacks by default (option); walking into doors still opens them.
- Exotic ammo guns are enabled by default.
- Faster loading: item migrations run in one pass and the JSON reader skips faster; the full
  data check went from 734 s to 118 s in testing.

### Fixed

- Crashes: starting an activity near NPCs, recraft after reload (upstream #10083), collapsed office
  tower mapgen (upstream #9875), electromagnetic unit (upstream #9354).
- NPC "Size up stats" hunger (upstream #10447) and repeated mutation attack damage (upstream #1287).
