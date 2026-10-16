# Bright Nights Overhaul changelog

Changes this fork makes on top of [Cataclysm: Bright Nights](https://github.com/cataclysmbn/Cataclysm-BN).
`OVERHAUL.md` explains each feature in detail; `docs/fork/visual-changes.md` shows them.
Upstream's own changes are in `docs/en/game/changelog`.

## 2026-10-16

### Fixed

- Modern reaches the sidebar options from **Enter → Misc → Sidebar Options**: the key stays
  unbound, and the panels can still be moved, hidden and reordered.
- **Arrow keys aim** is Modern-only, so Classic keeps walking with the arrow keys.
- The classic Lighting panel keeps its **Sound** reading when the weather box shows the light level.
- Classic and compact sidebars stop repeating the status box's need rows; the compact panel keeps
  **Focus**.
- Text-only HUD icons also apply to the vehicle box, and the weather box's **Wind** row lines up
  with the rows above it.
- Hint and welcome text no longer prints "Unbound globally!" when a hint key is unbound.

## 2026-10-15

### Added

- **Options menu key guide and reset:** a two-row guide keeps navigation, help and exit visible
  at 80×25. In Modern, `r` resets the highlighted option and `R` resets the page. A
  **[Reset to default]** button, hover, clicks on rows and page tabs work with the mouse.
- **Arrow keys aim** (Sword of the Stars: The Pit): in Modern the arrow keys move a free targeting
  reticle and `f` attacks what it covers. Options → Interface → Arrow keys aim; off in Classic.
- **Safe click-to-walk** (only when Mouse movement is explicitly enabled): walking further than
  one step needs a second click, and with a hostile in view a far click takes one step.
- **Mouse in inventory and pick-up menus** (Modern): hover highlights, left click picks or marks,
  the wheel scrolls in terminal and tiles builds, and right click opens the item's actions.

### Changed

- Modern map clicks no longer move the avatar. Right click selects/inspects without taking a turn;
  left click attacks the clicked hostile. Modern's firing screen also uses right-select/left-fire.
  **Mouse movement** is off in Modern; Classic retains upstream mouse behavior.
- Modern now uses compact action families: Enter keeps every general action category (Info for
  character/status screens); `i` opens inventory and item context actions such as Wield, Wear,
  Eat, Use and Read. Wield is an equipment action, not a separate primary map key. Inventory's
  visible **F5 Craft** entry works even with an empty inventory.
- Space acts on the RMB/Shift-look selected tile and offers applicable Open, Close, Examine,
  Pickup, Jump and Smash choices. Jump and destructive actions require an explicit choice;
  local `S` selects Smash without conflicting with menu navigation.
- Shift+WASD/QEZC freely moves a look reticle one tile at a time from the player;
  Ctrl+WASD/QEZC physically peeks through the normal action, costing 200 moves and returning
  to the starting position on cancel. Modern curses treats Ctrl+C/Z as game chords rather than
  quit/suspend signals; Classic keeps normal signal behavior.
- Shift+X cycles walk, run, crouch and prone; F2/F3/F4 are unbound. Ctrl+X opens wait/rest;
  lowercase `x` and numpad 5 wait one turn.
- Tab/Shift+Tab freely cycle visible hostiles in distance/position order with wraparound.
  `f` attacks the selected target, using normal gun aiming; bump attacks default to on again.
  Former separate map-menu shortcuts are unbound without removing their actions. Top-row
  numbers no longer move the player; context-local menu bindings and Classic are unchanged.
- Replaced the controls diagram with a complete 104-key ANSI keyboard: standard key widths,
  staggered rows and modifiers, separate navigation/arrow/numpad clusters, and a compact
  modifier-family legend.
- In Modern, `g` in the pick-up menu picks up the marked items, or the highlighted item when
  nothing is marked. Pickup's local Wield and Wear shortcuts remain available.
- The weather, weapon (with stance) and vehicle boxes now also show in the tiles version, drawn
  over the map; the sidebar no longer repeats what they show there either.
- Weather now uses four rows: description, date/time/moon phase, Light and Wind. Compact date
  text and fit-aware width retain the full phase. Watch and thermometer gates remain intact,
  including live inventory changes and unknown underground time without a watch.
  Text-only wind letters now name the same origin as a weather instrument.
- Renamed the weapon box to **Status**, with weapon, style, stance and fixed aligned
  Pain/Thirst/Hunger/Rest/Heat rows. Icons retain labels; healthy values stay explicit.
  Sidebar fields return when boxes cannot fit. Narrow views keep Needs rather than hiding
  them behind an oversized box, and boxes protect the avatar's map center.
- Bundled JetBrains Mono NL Regular (SIL OFL 1.1), with Unifont fallback, as the larger,
  anti-aliased default typeface. Oversized TTF glyphs now fit their cells instead of being
  center-cropped. Existing custom fonts remain supported; asset credits list the new font
  and its license.
- Empty-tile inspection no longer blocks keyboard gun aiming. Direct map clicks still cannot
  redirect to another target. Saved control-scheme switches clear inspection, while canceled
  switches preserve it; Classic's fire command ignores Modern reticles.
- Contextual Space choices no longer expose or act on unseen neighboring terrain.
- Existing saved option values remain preferences, including an explicitly disabled bump attack;
  upgrading an older profile may need that option enabled once.
- `bin/install-cataclysm-bn.sh` downloads the Otopack soundpack (music and ambience) through
  upstream's registry bundler. Downloaded audio and its credits remain outside version control.

### Maintenance

- Simplified installer destination setup and feedback argument handling, removed a forwarding-only
  sidebar panel factory, and reused the vehicle-spawn test helper without changing game behavior.

## 2026-10-14

### Changed

- Merged upstream `main` through `631956df27` (9 commits).
- Ported open upstream fixes ahead of their merge: the bugfix bundle from
  [#10563](https://github.com/cataclysmbn/Cataclysm-BN/pull/10563) (fixes already in the fork kept
  their fork form), read-menu books sorted by level
  ([#10436](https://github.com/cataclysmbn/Cataclysm-BN/pull/10436)), predator mutation texts
  ([#10179](https://github.com/cataclysmbn/Cataclysm-BN/pull/10179)), crash-handler hardening
  ([#9280](https://github.com/cataclysmbn/Cataclysm-BN/pull/9280)) and the UPS toggle mod on
  tools without an activate menu ([#10214](https://github.com/cataclysmbn/Cataclysm-BN/pull/10214)).

### Performance

- Repaints with unchanged vision inputs reuse the last visibility result instead of waiting on
  the GPU again; the line-of-sight cache is invalidated by generation instead of a 131,072-slot
  clear; body temperature scans nearby heat once instead of twice; the fork's HUD panels stop
  rebuilding strings and containers every frame. In an interleaved A/B on one saved town, CPU
  per action fell 4% walking, 7% driving, 4% opening screens, 4% waiting and 12-17% on mouse hover.
- Electric grids stop being processed once all of their area has left the simulated area
  ([upstream #10121](https://github.com/cataclysmbn/Cataclysm-BN/issues/10121)). Grids catch up
  on the elapsed time when you return, as before.

### Added

- Firing with no ranged weapon says so and names the wield key, instead of doing nothing. A gun
  in a melee mode names the firing-mode key instead.

### Fixed

- Pressing center view at the top z-level no longer crashes
  ([upstream #10604](https://github.com/cataclysmbn/Cataclysm-BN/issues/10604)); looking at
  another z-level also invalidates the right level's cache.
- Worlds no longer abort on builds with libstdc++ assertions when a region's city sigma is zero
  ([upstream #10582](https://github.com/cataclysmbn/Cataclysm-BN/issues/10582)).
- Examining an empty tile with autoselect off prints its description again
  ([upstream #9987](https://github.com/cataclysmbn/Cataclysm-BN/issues/9987)).
- E-ink tablet e-copies last the chosen time instead of vanishing at once
  ([upstream #10015](https://github.com/cataclysmbn/Cataclysm-BN/issues/10015)).
- Siphoning from the vehicle screen keeps the camera zoom and position during the target prompt
  ([upstream #9873](https://github.com/cataclysmbn/Cataclysm-BN/issues/9873)).
- Character creation shows the scenario and profession on narrow screens
  ([upstream #10427](https://github.com/cataclysmbn/Cataclysm-BN/issues/10427)).
- Modern list hotkeys `4` and `6` work without stealing horizontal actions from list callers.
  Unmatched filters show `--NO MATCHES--` within the list body.
- Short sidebars share the available rows between the compass and Controls, including enabled
  spacers and panel toggles. The message log and row budget use the same three-row minimum.
- Modern safe mode repeats a short key hint after its first warning, and the Modern wait menu
  offers the existing Sleep action. Classic retains its original entries and warnings.
- A vehicle that hides the tiles behind it no longer blanks them in the terminal: the remembered
  ground is kept where the tiles view already kept it
  ([upstream #10452](https://github.com/cataclysmbn/Cataclysm-BN/issues/10452)).
- The construction menu (`K`) opens on `All` when the Favorite tab has no entries, matching
  crafting. Once a construction is favorited, it opens on Favorite again.

## 2026-10-13

### Changed

- Merged upstream `main` through `4fd1dbea60` (24 commits), including clothing-linked drops,
  animal training fixes and the relic-recharge lifetime fix. Kept the fork's sprite fallbacks
  and corrected NPC hunger-time units.

### Fixed

- The black-powder loot check now distinguishes native black-powder rounds from stack-modified
  rounds. It verifies modifier counts without requiring a second ballistic penalty on .45-70
  handloads. Ammo balance is unchanged.
- Modern list filters accept all WASD letters while arrow keys move between matching entries.
  Menu navigation no longer consumes letters while the player types a filter.
- Sound-marker lifetime checks use an isolated underground scene with normal hearing and an
  unmuffled NPC, removing random weather and equipment dependencies.
- Reload checks follow the save-loading flow rather than shortcut capitalization.

## 2026-10-12

### Added

- **Install the fork as a launchable app**: `bin/install-cataclysm-bn.sh` installs launcher
  wrappers, desktop entries, an icon and a metainfo file into `~/.local`, plus a basepath config
  at `~/.config/cataclysm-bn/basepath` and the `bin/feedback` workflow.

### Fixed

- Launcher crash on desktop launch: the launcher wrapper now reads the basepath config file,
  skipping comment lines, and `cataclysm-bn-tiles` reports "no DISPLAY set" instead of failing
  silently when no display is available.
- Modern menus reserve lowercase WASD for navigation. Conflicting actions use Shift+WASD;
  existing Shift conflicts move to free keys. Main-menu shortcuts and inventory, mutation and
  bionic letters no longer override navigation. Classic controls and text entry stay unchanged.
- Modern list menus now support hover, click-to-select and right-click cancellation, including
  the map's right-click action menu.
- Tiles mouse hit-testing uses the scaled window origin, fixing misaligned hover and clicks
  with a left sidebar at 2x UI scale. Text menus no longer use isometric map projection.

## 2026-10-11

### Added

- **Vehicle box** (terminal view): speed, fuel, azimuth, cruise target, engine state, battery charge
  and aircraft takeoff speed in the same corner-box style as weather and combat. It appears aboard
  a vehicle or during remote control, starts at the bottom right, and replaces the duplicate Vehicle
  sidebar panel. Options → Interface → Vehicle box chooses another corner or restores the old panel.
- **Fork guide and database**: regenerate the pinned guide from this checkout's game data, mods
  and licensed tiles, publish it alongside the docs, and use it as the configurable in-game guide
  default. Dataset versions link to their fork commit; local game-data changes are marked dirty.
- **Upstream feature watch**: daily commit reports in issue #3, with candidate headings for human
  review and a checkpoint that advances only after the complete report is recorded.
- **Future-work tickets**: agentic UI/UX QA in CI (#1) and optional simple co-op (#2).
- **Pixel minimap zoom**: 1x, 2x or 4x, independent of the main map. The optional **Pixel minimap
  item markers** setting shows perceived loot in gold, without revealing hidden or sealed items.
- **Item layering on furniture** (tiles): raise item sprites slightly above furniture, with an
  option to restore the original height.
- **Cliff edge shading** (orthographic tiles): show perceived drops without hiding ground textures
  or revealing unseen openings.
- **Directional stairs** (tiles): orient stairs and ramps toward visible walkable openings,
  keeping oversized sprites anchored to their tile.
- **Item thumbnails in UI** (tiles): real item, variant and corpse sprites in inventory and pickup
  lists, with clipped drawing and no stale thumbnails after filtering.
- **Mood lighting** (tiles): native light tints for lamps and other emitters, without changing
  brightness, range or fuel use. Colored lighting can be turned off in Graphics options.
- **Cursor panning**, off by default: edge hover pans normal play, clicks use the panned view,
  centre/sidebar hover stops scrolling, and keyboard input recenters. Uses the existing Edge
  scrolling speed setting.
- **Monster health bars** (tiles): a small bar under every hurt monster in view, as fuzzy as the
  look-around list shows it. Options → Graphics → Monster health bars turns it off.
- **Enemy edge arrows**: a hostile you can see that sits outside the map window gets an arrow at the
  edge of the view pointing at it, red when it can reach you soon and yellow when it cannot. An
  arrow sits on the edge itself when the hostile is hunting you, one cell in when it is only
  trailing. Options → Interface → Enemy edge arrows turns it off.
- **Smart safe mode**: safe mode, the "spotted" interruption, noise interruptions and auto-explore
  ignore hostiles that cannot reach you soon (fleeing, immobile and not adjacent, or with no route;
  doors they can smash count as open). Ranged and leaping attackers always count; noises from
  monsters that are not hostile never interrupt.
- **Smarter targeting**: aiming starts on the hostile next to you or hunting you, ranks targets
  behind an ally last and warns "Ally in the line of fire".
- **Stances**: `F2` run, `F3` crouch, `F4` prone in the modern scheme; the weapon box shows the
  stance.
- **Contextual interact**: Space does the only sensible action next to you without asking for a
  direction, and lists what each direction does when there are several. `u` opens on the item you
  used last.
- **Follower command palette**: `y`, then `P` selects a nearby follower and edits their combat,
  aiming and behavior rules without dialogue. Bionic settings appear only when relevant.
  Options → Interface → NPC interface restores the original chat menu.
- **Crafting part preview**: distinguish craftable and blocked known producers, show missing units
  and native producer time, and open the producer with `p` in the modern scheme. Larger quantities
  show time and prerequisites per batch. This is not a recursive inventory-allocation plan.
- **Fading sound markers**: the `?` of an unseen sound stays for a few turns and dims (Options →
  Interface → Sound marker turns).
- **Status effect animations** in the tiles version: creatures in view carry a small looping
  overlay for what they are going through — a blood drip that falls, flames, a poison icon, the
  dizzy stars and spiral, a bobbing "zz", a snowflake. Monsters get them too, which they never
  had. Options → Graphics → Status effect animations turns it off.
- 12 sprites the default tileset lacked, from the CDDA tilesets (CC-BY-SA 3.0).
- 132 ASCII item pictures from CDDA (CC-BY-SA 3.0) for 134 items, shown in the item description.
- **Environment in the weather box**: under the weather and time, the weather box lists the season
  and day, light level, moon phase and wind, each value colored as the sidebar colors it.
- **No repeated sidebar rows**: while the weather box is on, the sidebar drops Sky, Light, Date and
  Time (the Location panel keeps Place and coordinates); while the weapon box is on, it drops the
  Weapon panel and moves mana into the box. Turn a box off and its rows come back.
- **Mana** reads `current/max` like weight and volume.
- The **Overhaul soundpack** (Kenney, CC0) for footsteps, melee, impacts, reloads, menus and
  vehicle doors; the Otopack stays the default when it is installed.
- A playtest harness, `tests/e2e/playtest.py`: 14 scenarios that set up a fork feature in a fresh
  game and hand it to you in the terminal or the tiles window.

### Changed

- Smart threat checks run only when needed and reuse route answers within a turn. Group checks
  search routes for at most 12 monsters; unchecked hostiles conservatively stop travel.
  When that budget is exhausted, the group stops travel immediately without spending time on
  route searches that cannot change the decision.
  Benchmarks distinguish the 12-route bounded case from over-budget stops and steady-state scans.
- The playtest harness includes a 120-zombie stress world. Tiles playtests use private options
  instead of changing the player's normal tiles configuration.
- End-to-end games disable desktop URL openers and find the retained curses build directly.
- The modern keyboard diagram is generated from the binding files, includes stance keys and
  Shift actions, and highlights key conflicts instead of silently hiding them.

### Fixed

- The item action menu no longer opens empty after saying you have no usable items.
- Smart safe mode no longer treats a hostile far beyond its distance as close when nothing stands
  between you.
- The tiles version no longer crashes when started with `--world` to load a save directly.
- Weather boxes no longer duplicate wind in roomy sidebar layouts or the clock in narrow classic
  layouts. Narrow classic layouts retain the date and thermometer reading.
- The Controls strip keeps `? all keys` near movement and has room for the existing hints.
- Driving hints show throttle and steering instead of walking controls, then switch back when
  the controls are released. Vehicle readings no longer truncate their values at 80 × 25.

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
