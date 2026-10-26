# Bright Nights Overhaul changelog

Changes this fork makes on top of [Cataclysm: Bright Nights](https://github.com/cataclysmbn/Cataclysm-BN).
`OVERHAUL.md` explains each feature in detail; `docs/fork/visual-changes.md` shows them.
Upstream's own changes are in `docs/en/game/changelog`.

## 2026-10-26

### Added

- `bin/dev-iterate.sh` (`just dev`) and the `linux-curses-dev` and `linux-tiles-dev` presets: an
  unoptimized game-only build that launches straight into a development save.
- `CATA_HOT_RELOAD` and the `*-hotreload` presets (`bin/dev-iterate.sh --hot`, `bin/hot-reload.sh`):
  a development build that patches edited functions into the running game with jet-live.

## 2026-10-25

### Added

- `Ctrl+F` searches every action by name, shows how each one is reached, and runs the pick.
- `T` toggles auto travel, and the control strip names both it and safe mode.
- The tile inspector sits in the top-left corner.
- Right-drag pans the overmap; the cursor click that used to jump the view still does not pan.
- The tiles build remembers the zoom you left and restores it at launch.
- A CC0 sound audition page (`docs/fork/sound-audition/index.html`) to choose the next pack.
- CC0 interface research from five games in `docs/fork/qol-research/`.

### Changed

- The log reserves eight rows instead of three, and the control strip is at most three rows.
- Zoom stops at its closest and farthest step instead of wrapping to the other end.
- Sound markers on the map age out during multi-turn activities, not only after a player action.

- Space runs the obvious action on the aimed tile — door, pile, stairs, cargo, corpse, vault,
  examine — and lists the rest only for a tie or a destructive choice; with nothing aimed it acts
  on the tile you last pressed toward.
- `v` uses the item you pick by its kind (wield, wear, eat, read, unload, activate) instead of one
  key per verb.
- `g` takes a lone item and opens the picker for a pile; `G` always opens the picker.
- `H` honks the horn while driving, and the attack key `f` smashes a bashable aimed tile when no
  creature stands there.
- Modern reaches mutations `[`, the diary `J` and options `O` directly again.

- The title screen displays a text-only OVERHAUL wordmark beneath Bright Nights in terminal
  and graphical builds.
- The release runbook includes preflight checks and a notes-only correction procedure that
  preserves published tags, binaries and the download table.

### Fixed

- Clearing the last local key no longer prevents using Add global for the same action.
  The new global key takes effect immediately and survives restarting the game; remaining
  local bindings still require removal before a global binding can be added.

### Maintenance

- Build guidance explains preset-specific ccache hits and how to investigate a suspected stale
  object without mistaking compiled-out code for a cache failure.
- The test-quality gates require running documented CLI commands exactly as written and fixing
  parser/documentation mismatches together.
- The vehicle-lock playtest loads a private fixture with closed doors, enabled locks and no
  ignition keys instead of relying on randomized spawn state.
- Lua-console playtests wait for the command editor and a unique execution-completion marker;
  failures report returned values and visible Lua errors instead of silently accepting missing output.
- Target-cycling and tutorial fixtures pin sight and clear unrelated creatures. Door-marker fixtures
  derive roof coordinates after avatar placement, which can shift the loaded map immediately.
- Trait-list playtests preserve the character's original mutations, and the resized help-menu
  check waits for content at the new dimensions before calculating click coordinates.

## 2026-10-24

### Added

- Modern menus accept Space like Enter on the highlighted choice, including No in a confirmation.
  Filters, world names and the Lua console keep literal spaces. The title menu supports mouse
  hover/clicks in terminal and graphical builds and asks before quitting.
- Inventory Tab opens advanced inventory in Modern; Shift+Tab selects categories. A clickable
  advanced-inventory footer hint works in both schemes without changing Classic's keys.
- Space on a loaded vehicle trunk opens pickup directly. Shift+Space toggles a selected vehicle
  curtain or lists nearby curtains.
- Modern status, utility, information and vehicle menus support their existing actions with mouse
  selection, tabs, header labels, hints and scrolling. Custom action lists select on the first click
  and act on the second. Trade marks items without accepting the deal; armor rows remain read-only.
- Known-lock markers appear only after a failed opening attempt, persist in map memory and clear
  when a known door opens, unlocks or is destroyed. Untried locks remain hidden.

### Changed

- The eight Modern Select tile keys are unbound by default; the actions remain rebindable.
  Right-click selects objects or locks hostiles without attacking. Closing an object's action list
  keeps the selection, and hover cannot replace a locked target.
- Modern `p` smashes or pulps in a chosen direction; Classic keeps `s`. Keybinding search accepts
  ordinary letters, including W/S, and resets scrolling after a changed filter.
- The bundled Overhaul soundpack uses dirt footsteps and obstacle-clearing clips instead of
  squeaky carpet clips. Scratch clips remain assigned to missed monster bites.

### Fixed

- Status-effect animation ticks are bounded before narrowing and floor-normalized before frame
  selection, preventing the reproduced negative-index tiles crash.
  Idle polling starts when the first redraw discovers animated overlays, without waiting for another keypress.
- Glass weapon, pry, terrain, furniture, item and bullet-hit events use the shipped glass clips.
- Terrain footsteps recognize worn shoes instead of using a legacy leg index to choose barefoot audio.
- Overmap mouse coordinates follow the displayed map; `m` closes it without starting travel.
- Manually reassigned item digits survive restacking and saving without automatic digit assignment.
  Wearing and wielding refresh the open inventory without losing its selection.
- Synchronous dimension travel releases its swap guard before a subsequent Lua-driven trip.
- Shift+Space consumes its terminal escape sequence once. SDL retains the key-down modifiers
  even when Shift is released before its text event arrives.
- UiList scrollbar clicks use window-relative coordinates instead of the center-relative input point.
- Windowed graphical scaling uses usable monitor bounds, keeping supported 2× windows at their configured size.
- End-to-end tests now launch the current root terminal binary before looking for older build paths.
  Pulping fixtures use eligible corpses, and trunk fixtures spawn one vehicle and clear ground clutter.
- Matching Windows debug-symbol ZIPs are retained as workflow artifacts for crash reports.

## 2026-10-23

### Added

- **Sound & volume** opens from Enter → Misc and from the title-screen Settings: sound and music
  switches plus music, sound-effect and ambient volume. Changes apply at once and save on close.
  Terminal builds explain that audio is unavailable. Music off leaves sounds on.
- Modern uses stairs with PageUp/PageDown, and Space or a click on your own stairs tile uses them.
  The old `<` / `>` bindings still work. Dynamic stair-direction sprites are gone.
- Modern `g` takes everything on your tile without a menu; `Ctrl+G` opens the nearby pickup menu.
- Modern `h` opens body status.
- The Controls strip follows the menu that is open and shows that menu's keys above it; closing the
  menu restores the map keys. `CONTEXT_KEYHINTS` turns this off.
- The tutorial gives you a flashlight with a charged battery, and its weapon lesson spawns the
  zombie it promises. The gun lesson starts from the ordinary reload key and waits for a loaded gun.
- The fork installs beside an upstream Cataclysm-BN: `bin/install-bno.sh` provides `bno` and
  `bno-tiles`, its own menu entry and icon, and `~/.local/share/bright-nights-overhaul` with
  `~/.config/bright-nights-overhaul`. It copies old fork saves and settings once and leaves the
  old directories for an upstream install. The window titles itself **Bright Nights Overhaul -
  version**, so it does not read as upstream.

### Changed

- The needs row is labelled **Body temp** and carries a cold or hot icon; mild warmth and chill no
  longer press the row, so **Needs met** returns for a comfortable character. Rest uses one glyph,
  and every icon row has an ASCII fallback in **Text only** mode.
- The item folds are a recorded balance exception (see `AGENTS.md`): batteries, containers, black
  powder, jewelry, games and variant prices keep their new behaviour, and `OVERHAUL.md` documents
  it. The folds were repaired where they broke play: black powder keeps its misfire, fouling,
  smoke, recycled and price effects, mixed stacks are disassemblable again, every battery spawn is
  full at the new capacity, deleted recipes and loot entries are restored, and fetch missions can
  ask for a variant.
- Local builds use `-g1` and no longer generate Lua docs after every build: the game binary fell
  from 805 MB to 390 MB, a tree from 4.5 GB to 2.3 GB, and a one-file rebuild from 11.0 s to 9.4 s.
  Missing ccache or mold warns and falls back instead of failing. Stale test precompiled headers
  were removed.
- GitHub Actions runs the gameplay suite on one runner, and model playtests run one leg unless a
  dispatch asks for all. Only one job per run writes each compiler cache, and the Linux precompiled
  header is cacheable, so release builds no longer evict their own caches.

### Fixed

- Loading a map kept vehicles from the previously loaded area in its per-level lists, so a reload
  could fire their engine sounds from an old position and open debug assertions.
- A failing game borrowed from another test closed the runner's shared game; later tests then hit
  a missing tmux pane. Games now close after their last borrower.
- The harness waits with the active scheme's wait key: classic `x` opens look-around.
- A release dispatch pins its version tag before building, so a later push cannot invalidate the
  build, and publication no longer needs a personal token.
- Tutorial stair, darkness, targeting and reload lessons name the active scheme's keys instead of
  hard-coded letters.

### Maintenance

- `README.md`, `README.ja.md` and `README.ko.md` link the fork's own releases and screenshots.
- `--dump-stats FOLDED` takes its request file directly, and the comparison tool is invoked with
  named arguments, as `tools/fold_equivalence/README.md` shows.
- The test-quality skill records the harness traps found in these runs, including the vehicle-cache
  reload bug and the borrowed-game lifetime bug.

## 2026-10-22

### Added

- The grouped sidebar puts Weather, Character and Needs on the right and leaves the map clear.
  It is the default for new configurations. Existing saved layouts stay unchanged.
  Select `grouped` in Enter → Misc → Sidebar Options to try it.
- The tiles build includes Material Design Icons and human stance figures from Pinhead (CC0).
  No separate icon-font installation is needed.
- **Windows download with updates**: the fork release workflow prepares a Windows zip
  and a Linux archive with fixed names. On Windows, `Launch Bright Nights.bat` offers each new
  release before the game starts, checks the download's SHA-256, keeps saves, settings and added
  mods, tilesets and soundpacks, and puts the old files back if anything fails. Without internet
  the game just starts. See `docs/fork/playing.md`.

### Changed

- Status lists urgent needs, or one `Needs met` row. An unchosen fighting style takes no row.
- A short sky track replaces the written moon phase, with distinct sun and moon symbols.
- Modern left click uses adjacent doors, items and furniture. Other empty tiles are selected, not walked to.
- Space lists nearby actions in one menu with directions and a highlight for the selected action.
  A corpse underfoot offers Butcher.
- Modern adds `v` for Wield, `@` for character information, `P` for messages, `B` for Butcher
  and `F` for fire mode. Shift selects tiles. Ctrl physically peeks and keeps the selection.

### Fixed

- Tutorial lessons name reachable actions for each control scheme. Item lessons follow successful
  pickups, including Modern `g`, rather than firing before the pickup activity finishes.
- The tutorial teaches opening beside a closed door and closing beside an open door.
- Safe mode shows its blocked state in yellow instead of the enabled state's green.
- Long contextual mouse hints keep the tile inspector's border intact.

### Maintenance

- Regenerated the Modern keyboard diagram with the direct equipment/info shortcuts, contextual
  mouse actions, Shift selection and Ctrl peeking. Key labels stay inside their keycaps.

- `fork-release.yml` builds and publishes a release when a `v*` tag is pushed or a version is
  dispatched, reusing `build.yml` for the Windows MSVC and Linux tiles builds; release notes come
  from this changelog. `fork-updater-test.yml` gates it by updating a mock Windows install from a
  local zip under Windows PowerShell 5.1 and 7. See `docs/fork/releasing.md`.
- Future release builds reuse vcpkg binary packages, host shader tools and compiler caches
  across release refs, with toolchain and dependency checks.
- Pushes and pull requests no longer start gameplay playtests automatically. Release playtests
  are an optional, default-off gate; nightly and manually selected playtests remain available.
  Build-only dispatches can validate the pipeline without creating a tag or release.

## 2026-10-21

### Added

- **World presets**: press `p` on the World Options tab or the in-game Current world page
  (modern scheme) to apply Relaxed, Scarce or Hardcore, or reset the page. Presets only fill in
  existing world options, which stay editable. Requested on r/cataclysmbn. See `OVERHAUL.md`.
- **Stocked River Barges**: a fork mod, on by default in new worlds, that refills the river barges
  upstream left nearly empty and adds the sealed Hermex containers the deck graffiti mentions.
- **Plumbing feedback**: the fluid grid explains refused connections, partial fills, tanks that
  cannot be disconnected and the one-tank water purity rule; failed connections no longer use up
  parts.
- **OpenRouter playtests**: decision-model playtests can use free OpenRouter models, locally from
  `OPENROUTER_ENV_FILE` and nightly in CI from the `OPENROUTER_API_KEY` secret.
- **Compact corner bars**: an Interface option draws the weather and status readings as one-row
  strips at the map corners. The sidebar keeps its panels, and the needs summary appears on the
  status strip only when the row has room.

### Fixed

- Opening vehicle controls while remote-controlling a vehicle could crash (upstream #5413).
- Losing all worn clothes at once kept the Stylish morale bonus and logged a morale inconsistency.
- Disconnecting a fluid grid tank deleted items lying on its tile; splitting a grid could drop
  liquid when a part had no capacity.
- The BrownLikeBears tileset drew battleaxes as nothing, and ChestHole16 drew eight dinosaurs as
  nothing: later tile entries pointed them at empty sprite cells.

### Maintenance

- A key-guess survey (`tests/e2e/keyguess.py`) shows a decision model a real screen with no
  key hints, asks which key reaches a goal, and checks the answer in a fresh game.
- The safe-mode repeat-hint check waits for the first full warning before blocking again: a
  zombie placed from Lua is noticed only after a turn, which made the check flaky on CI.
- The end-to-end suite is split into feature modules; `run.py` is only the runner. It runs in
  parallel by default, has a two-minute `--tier=smoke`, `--list` and `--help`, and rejects unknown
  options. Tests with the same options share one game instead of starting their own, which drops
  game starts from 54 to about 26; three duplicated tests were merged into the tests that already
  covered them. CI uploads per-shard timings that `merge_durations.py` folds into the manifest.
- The reload regression waits for the item picker and each loaded round before sending the next
  key and answers interruption prompts. Fixed delays could leave the cylinder one round short.
- Tiles playtests and screenshot captures apply deterministic options to both config-directory
  modes. CI builds had ignored the XDG-only copy, leaving rain and blinking enabled so frame
  waits timed out. Failed screenshot launches now close their game window before the next shot.
- Refreshed all ten feature screenshots from a verified tiles CI run. The capture script now opens
  Interact through the command hub, reaches the Sidebar Options editor and holds Shift with the
  look direction; captions match the current controls.
- The parallel test runner rejects nonpositive counts and conflicting shard flags, drains each
  worker's output and prints an attachment command for retained games. Private tmux servers also
  work when the runner starts inside another tmux session.
- Manual playtest dispatches no longer cancel an in-flight manual run. Click checks retain their
  original one-second observation window. The frame detector accepts dark map captures with
  either sidebar position and rejects the compact loader and the tested JSON-error popup.
- Auto-exploration and smart-safe-mode fixtures open routes outside the starting shelter and clear
  creatures from the walk radius. The tool-combine fixture clears starter inventory so rolled
  matchbooks cannot change the two items and twelve charges under test.
- Crafting checks read wrapped estimates from the recipe column without neighboring batch rows
  or item details. Vehicle-memory checks disable animated weather and use a private electric
  armored car with a solid rear, avoiding exhaust, cameras and randomly opened doors without
  invalidating sight after driving.
- Legacy-keybindings and map-memory fixtures activate queued NPCs before clearing their arenas,
  so late-arriving companions cannot block movement or interfere with vehicle setup.
- Electric-vehicle HUD checks wait for the engine to start and answer interruption prompts before
  throttling, using the same bounded control helper as the map-memory check.
- HUD resize checks wait for two identical complete-size captures instead of asserting on the
  first Needs row of a partially painted terminal frame.
- Mouse-selection fixtures flush queued actors and clear transient effects before testing. The
  arrow-aim-off check verifies the inspected enemy and reports failures from its isolated game.
- The recraft save/reload fixture replaces unrelated world vehicles with passive bicycles before
  crafting, avoiding recurring idling-engine debug popups in later tests.

## 2026-10-20

### Added

- **Stairs and save tips**: stepping onto stairs names the keys that go up and down, and an early
  tip says that the game saves as you play and when you quit, because new players hunt for a save
  key that does not exist. See `OVERHAUL.md`.

### Fixed

- The weather box widens to fit its widest row. It measured only the date row before, so a long
  weather name could cut the temperature off instead of widening the box.

### Maintenance

- The end-to-end suite supports local parallel runs (`--parallel=4`), per-test timing output
  (`--durations=<path>`) and duration-balanced CI shards. The Lua console and click helpers poll
  for readiness instead of sleeping after every action. Reload and wait fixtures no longer depend
  on earlier wounds or the starting outfit's storage.

- Merged `upstream/main` (34 commits) as `c682cb343a`. The black powder rounds the merge
  re-added to `data/json/uncraft/ammo/rifle ammo.json` are folded again; the new 8 mm uncrafts
  upstream added there are kept.
- The cross-platform build matrix runs weekly and on demand instead of every push. Pushes
  check one dry playtest leg; nightly and manual runs retain the live matrix when model keys
  are configured. Filtered dry dispatches keep their selected surface, and cold builds have
  a 90-minute end-to-end job limit.

## 2026-10-17

### Added

- **Agentic playtests**: a decision model plays a scenario and reports what it meets. One transcript
  line per turn carries the state that preceded the action, and the report names each defect with its
  turn number plus the run's cost. Free models only, from OpenCode and Experiential Labs, with a
  fallback that moves to the next model when a free allowance runs out and compacts the state to fit.
  Scenarios cover the main menu, the tutorial, natural gameplay and a map built around the features
  this fork adds, on the terminal and tiles builds and with classic or modern controls. See
  [`docs/fork/agentic-playtests.md`](docs/fork/agentic-playtests.md) and `OVERHAUL.md`.

### Maintenance

- The end-to-end suite and the playtests run on GitHub Actions:
  `.github/workflows/fork-playtest.yml` runs the deterministic checks on every push, four playtest
  legs on the nightly schedule, and the feature screenshots on demand. The live legs wait for the
  model secrets, the dry leg runs either way.

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

### Maintenance

- Merged upstream `main` (11 commits). The black powder ammo fold survives it: the merged `bp_*`
  recipes and uncrafts are dropped again, the new non-black-powder entries stay, and the black powder
  277 hybrid round keeps its recipe. The new `perk` type arrives with the merge, so Modern reaches
  Perks from **Enter → Misc** like the other actions that have no Modern key.

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
- `bin/install-bno.sh` downloads the Otopack soundpack (music and ambience) through
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

- **Install the fork as a launchable app**: `bin/install-bno.sh` installs launcher
  wrappers (`bno`, `bno-tiles`), desktop entries, an icon and a metainfo file into `~/.local`, plus
  a basepath config at `~/.config/bright-nights-overhaul/basepath` and the `bin/feedback` workflow.

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
