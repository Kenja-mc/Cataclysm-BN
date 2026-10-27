# Bright Nights: Overhaul fork

This is a fork of [Cataclysm: Bright Nights](https://github.com/cataclysmbn/Cataclysm-BN) that tries to
make the game easier to pick up. The simulation, content and tone stay the same: same world, same
items, same zombies. The changes are to the controls, the look of the interface and the busywork
around managing items.

Branched from `cataclysmbn/Cataclysm-BN@d14e047`; last merged upstream `main`: `631956df27`.

Screenshots: [docs/fork/visual-changes.md](docs/fork/visual-changes.md). Changes by date:
[CHANGELOG-OVERHAUL.md](CHANGELOG-OVERHAUL.md).

## Controls

Modern uses a few control families instead of a separate primary key for every menu. **WASD**
walks, with **Q E Z C** for diagonals; the numpad also walks. Walk into an enemy to attack it.
The same direction keys move cursors in look mode, targeting and the overmap, and answer
direction prompts. Top-row numbers do not move you on the map.

- **Enter — general actions.** All existing action categories remain available here, including
  construction, storage, talking and equipment. **Info** holds body status, missions, morale and
  the other status screens; **`@`** opens the character sheet and **`P`** the message log directly.
  **Misc → Sidebar Options** moves, hides and reorders the sidebar panels.
- **`i` — inventory and equipment.** Select an item to open its context menu for **Wield**,
  **Wear**, **Eat**, **Use**, **Read** and other item actions. The menu shows its local shortcuts.
  **`v`** wields from the map: it lists what you can wield. Press **F5 Craft** inside inventory to
  craft, even when the inventory is empty.
  **Tab** opens advanced inventory from this screen; **Shift+Tab** switches category selection.
  The footer's advanced-inventory hint is clickable in both schemes; Classic keeps its keys.
- **Space — the obvious action.** With a tile selected (mouse hover or click, arrow aim, or a
  Select tile key), Space runs that tile's most obvious action without asking, in this order:
  **open or close a door**, **pick up a pile**, **use stairs**, **loot a vehicle cargo part**,
  **butcher a corpse**, **vault a climbable obstacle**, **examine**, then **smash**. The rest of the
  tile's actions stay in one menu, which appears only for a genuine tie or a destructive choice, so
  Space never auto-smashes. Vaulting a lone climbable obstacle such as a half-height sandbag runs at
  once; the aim names the target. With no tile selected, Space acts on the tile you last pressed
  toward, and falls back to the nearby list ("Interact with what?") only before you have moved.
  **Shift+Space** toggles the selected vehicle curtain, or names nearby curtains when nothing is
  selected. Clicking your own stairs uses them, and a loaded vehicle trunk opens pickup directly.
- **`f` — attack anything.** `f` fires at a creature as before; on an aimed tile with no creature it
  smashes what is bashable there instead (a web, a corpse, a door that will not open), so one key
  attacks creatures and breaks obstacles. Smashing still spends its normal moves and can ruin a
  brittle weapon.
- **Select keys — unbound by default.** Tile selection is a mouse action. The eight **Select tile**
  actions stay in the keybindings menu: binding them (for example to Shift+WASD/QEZC) moves the
  selection marker one tile per press, starting at your position and accumulating. The Mouse View
  box describes the selected tile. Selecting spends no time.
- **Ctrl+direction — peek.** Ctrl+WASD/QEZC physically peeks from the neighboring tile through
  the normal peek action. It costs the usual **200 moves**, unlike selecting; canceling returns you
  to your starting position, and the current selection is kept.
- **Shift+X — movement mode.** Cycle walk, run, crouch and prone. F2/F3/F4 are unbound on the map.
- **Tab / Shift+Tab — targets.** Cycle forward/backward through visible hostiles, ordered by
  distance then position, wrapping at either end. Selection takes no time; **`f`** attacks the
  selected target, using the normal aiming screen with a gun. **`F`** changes the fire mode.

**Ctrl+X** opens wait/rest; **`x`** or numpad 5 waits one turn. In a Modern terminal build,
**Ctrl+C** and **Ctrl+Z** are game chords (diagonal peeks), not terminal quit/suspend signals.
**Classic** retains upstream controls and normal terminal signal behavior.

**Arrow keys aim**, as in The Pit (Options → Interface → Arrow keys aim; on in Modern, off in
Classic). An arrow key puts a targeting reticle on the nearest hostile you can see, or on your own
tile, and further arrow keys move it over tiles you can see. This takes no time. The reticle tile is
highlighted and the Mouse View box says what is there. `f` then attacks what the reticle covers:
a melee swing with a melee weapon when it is next to you, otherwise the normal aim screen opens
on that creature. An empty tile rejects a melee attack without spending time; with a gun in a
firing mode, `f` instead opens normal manual aiming. An unreachable creature is rejected without
spending time. Esc, walking or any action that takes time removes the reticle; Esc does not open
the main menu while a reticle is up.
Turn the option off to walk with the arrow keys again.

In **Modern**, lowercase WASD also navigates menus. Menu actions that used those letters move to
Shift+WASD, including sorting, adding rules and dropping. Context-local shortcuts remain local:
for example, inventory and pickup offer Wield and Wear alongside the map's `v` wield key.
Generated shortcuts and inventory, mutation and bionic letters leave navigation keys
free. Text fields still accept normal typing; **Classic** retains the upstream controls.

In ordinary Modern menus, **Space** confirms the highlighted choice just like Enter; it never
means an unconditional Yes. Spaces stay literal in filters, world names and the Lua console.
The title menu supports mouse hover and clicking; Quit asks for confirmation.

Where a Shift shortcut was already occupied, the other menu action moves:

| Menu             | Action                        | Key             |
| ---------------- | ----------------------------- | --------------- |
| Item actions     | Disassemble                   | `B`             |
| Item actions     | Hitchhiker's Guide            | `J`             |
| Armor layers     | Sort layers                   | `O`             |
| Bionics          | Toggle safe fuel              | `F`             |
| Vehicle controls | Atomic lights / doors / scoop | `B` / `U` / `R` |

![Modern control scheme](docs/fork/images/controls-modern.svg)

Regenerate the diagram from the binding files with `python3 build-scripts/gen_controls_svg.py`.
The diagram uses standard ANSI key widths and row stagger, including unbound keys and modifiers.
Arrow/navigation and numpad clusters appear separately below the main keyboard for readable labels.
Modifier families appear in a small legend rather than on every direction key; the generator
reports conflicting bindings.

`n` **auto-explores**: each press walks you to the nearest spot you can reach that borders ground
you have not seen yet, on your current floor. It goes around walls, closed doors, known traps and
dangerous fields rather than through them, so open a door yourself to explore past it. It refuses to
start while a hostile is in view, it stops like any other auto-travel (danger, or any keypress), and
when nothing unexplored is left nearby it says "Nothing left to explore nearby." The classic scheme
gives it no key; bind one yourself, or pick it from the Enter action menu, which lists every action.

**Smart safe mode** (Options → Interface, on by default): safe mode, the "spotted" interruption and
auto-explore ignore a hostile that cannot get to you soon: one that is fleeing, one that cannot move
and is not next to you, or one with no route to you within twice the safe-mode distance (a zombie
behind a fence or in a sealed room; a door it can open or smash counts as open). A monster with a
ranged or leaping attack, such as a turret or a spitter, always counts, and so does anything next
to you. While you craft, read or wait, a noise from such a monster, or from one that is not
hostile, does not stop you to ask "Heard …!".

In the Modern control scheme, only the first blocked step prints the full "Spotted …" safe-mode
warning. Further blocked steps repeat a short `Safe mode: ! off, ' ignore` line, because the long
warning's repeat counter can wrap out of view. Classic keeps the upstream warning.

Threat checks are lazy and cached for a turn. A group gets at most 12 route searches; unchecked
hostiles still stop travel rather than being treated as harmless. A large sealed horde can
therefore cause an extra safe-mode stop. Changes to passability discard the cached answers.

The welcome card also explains mouse selection, and a first tip suggests a starter goal: find water,
food and a weapon, because houses usually have all three.

| Key / family         | Action                                                             |
| -------------------- | ------------------------------------------------------------------ |
| `w a s d`, `q e z c` | move; bump an enemy to melee attack                                |
| Numpad               | move; numpad 5 waits one turn                                      |
| Ctrl+direction       | physical peek (normal 200-move cost)                               |
| Tab / Shift+Tab      | next / previous visible hostile                                    |
| `f`, `F`, `r`, `t`   | attack selected target / fire mode / reload / throw                |
| `p`                  | smash or pulp in a chosen direction                                |
| Space                | nearby or selected-tile actions, including explicit Jump and Smash |
| Shift+Space          | toggle a selected vehicle curtain, or choose one nearby            |
| `g` / Ctrl+G         | take everything underfoot / choose items nearby            |
| `i`, `v`, `/`        | inventory / wield / advanced inventory                             |
| `i`, then F5         | craft (also works with empty inventory)                            |
| `@`, `P`, `B`        | character sheet / message log / butcher                            |
| Enter                | all action groups; Info contains character/status screens          |
| Shift+X              | cycle walk / run / crouch / prone                                  |
| `x` / Ctrl+X         | wait one turn / wait or rest a while                               |
| `m`, `n`             | map / auto-explore                                                 |
| `M`                  | world: missions, factions, zones, scores                           |
| PageUp / PageDown    | stairs up / down (also `<` / `>`)                           |
| `h`                  | health and wounds                                          |
| `!` / `'`            | safe mode / ignore enemy                                           |
| F1 / `?`             | help (opens on a first-ten-minutes page) / full keybinding list   |
| Esc                  | cancel selection, or main menu when no selection is active         |
| F12 / backtick       | developer debug menu / Lua console                                 |

Walking into an enemy attacks it in both control schemes. Options → Interface → Attack by walking
into enemies can disable this; in Modern, select a target and press `f` for a deliberate attack.
The separate map shortcuts for Craft, Open and Jump are unbound, not removed actions:
use inventory, Space or Enter. Modern **`p`** smashes terrain or pulps a corpse in a chosen
direction; Classic keeps **`s`**. Walking into a closed door still opens it. Text that names a key,
such as tutorial pop-ups and help pages, names the way to reach an unbound action instead, for
example "i → item → Activate". In Modern, the tutorial's lessons describe Modern's own way of
doing each thing (clicking, Space, selecting with the mouse), and the door lessons now appear for
the right door: the opening lesson next to a closed door, the closing lesson next to an open one.

The wait menu (**Ctrl+X** in Modern; `|` in Classic) lists 5, 30 minutes, 1, 2, 3 and 6 hours, a custom duration,
times of day and the next weather change. In Modern it also offers **Sleep** on `$`, using the
same sleep confirmation and alarm prompts as the sleep action. Classic keeps its old entries.

**Mouse tile selection**, inspired by Sword of the Stars: The Pit, works in the terminal too.

- **Hover:** previews a tile in the Mouse View box without changing a locked target or its marker.
- **Right click:** locks a hostile without attacking. On an object or door it opens the action list
  without running an action; closing the list keeps the tile selected.
- **Left click:** does the main action of the clicked tile next to you: opens or closes a door,
  picks up items, or examines furniture, without walking. On a hostile it attacks: an adjacent
  melee swing, or the normal ranged aiming flow with a gun. Anywhere else it only selects the tile;
  it never walks there. The hover hint names what a left click will do.
- **Firing screen:** right click targets, the wheel cycles targets, and left click fires in Modern.
  Classic retains its upstream left-select/right-fire mapping.
- **Keyboard movement only in Modern.** **Options → Interface → Mouse movement** is off;
  single clicks, double clicks and distant clicks do not move the avatar, including through the
  legacy handler when Mouse tile selection is off. Classic keeps upstream mouse movement.
- **Safe click-to-walk**, when using a movement-enabled scheme: with Mouse tile selection and
  Safe click-to-walk on, long travel needs a second click, visible threats limit a distant click
  to one step, and a known trap/dangerous field asks for confirmation.

Modern custom action lists use two clicks: the first focuses/selects a row, the second performs
its existing keyboard action. Tabs, filters and content changes reset that pairing. Trade's second
click only marks an item; Enter or Accept still confirms the deal. Advanced-inventory clicks do
not transfer items. Armor rows stay read-only; body-part names and header arrows switch tabs.
The health report stays a scrollable text report with Close.

Inventory hover highlights an item, left click picks it (or marks it in multi-item menus), and the
wheel scrolls. Right click on an inventory item opens its actions; right click outside cancels.

**Quick pickup and area pickup.** In Modern, `g` takes all ground and vehicle-cargo items on your
own tile without a menu, using the normal pickup activity and its capacity handling. Ctrl+G opens
the area pickup menu; `g`, Enter or Space picks up marked items, or the highlighted item if none
are marked. Escape cancels.
Inside pickup, local shortcuts act on the highlighted item: `h` wields it and `W` wears it.
With the mouse, hover highlights a row, left click marks or unmarks it, and the wheel moves through
the list. Right click lists Pick up, Wield and Wear; each acts on that item alone. The footer shows
the bound keys. Classic keeps the upstream menu, including Enter doing nothing with no marked items.

**Options menu.** A two-row key guide keeps navigation, help and exit visible at 80×25. In Modern,
`r` resets the highlighted option to its default and `R` resets the whole page after a Yes/No
question. Hover selects a row, left click advances the value, right
click goes back one value, clicking a page tab switches to it and **[Reset to default]** at the
bottom right resets the highlighted option. Classic keeps the upstream keys; `r` and `R` have no
key there but can be bound.

When aiming: `f`/Enter fires, `x` aims one step, `u` `i` `o` pick aimed, careful or precise shots
(more care, left to right), `r` switches ammo, `F` or `m` switches fire mode. With **smarter
targeting** (Options → Interface, on by default), aiming starts on a hostile that is next to you or
already hunting you, targets behind an ally come last, and the aim panel says "Ally in the line of
fire: …" when someone friendly stands in the way.

On the overmap: `=`/`-` zoom, `R` toggles weather, `x` sets a waypoint. In the tiles version's
main view the mouse wheel zooms. Pixel minimap controls remain available through Enter rather
than a separate primary map key.

In the vehicle screen, WASD and Q E Z C move the cursor like everywhere else. The actions those
letters used to start moved to Shift: `W` crew, `A` label, `S` siphon, `D` unload, `E` rename,
`C` change tire, and `Z`/`X` zoom in and out.
Clicks select vehicle parts and overview rows or use the displayed action and tab labels. The
existing hints and mouse wheel scroll the descriptions and parts list.

A **Controls** strip at the bottom of the sidebar shows the most used keys. `? all keys` stays
near the movement hints, and five rows keep the other hints visible. It reads live keybindings,
so action hints stay correct if you rebind them. On a terminal too short for five rows the strip
keeps its first row or two instead of vanishing, so the core keys stay on screen.
The compass gives up rows first. Hidden panels do not reserve space, and sidebar spacers count
toward the available height.
While driving, the movement hints become `ws throttle` and `ad steer`. Releasing the controls
restores the walking hints. With **Menu key hints** on (Options → Interface), opening a menu
switches the Controls strip to that menu's registered keys. A one-line Controls footer is drawn
over the bottom row of the active in-game menu, including inventory, pickup, crafting, look-around,
aiming and the action menu. It is inactive on the title screen and while game data is unloaded.
Closing the menu restores map keys. Hints include Ctrl-only bindings and
follow rebinding. Hide the Controls panel to hide both displays, or turn Menu key hints off to
keep the old map-only strip. This also applies in Classic when its Controls panel is enabled;
it does not change Classic bindings.

**Follower commands**: open Chat from Enter (or interact with a nearby follower), then `P` opens the command palette. Choose a follower
when more than one is nearby. Change engagement, aiming, gun use, movement and item rules
without entering dialogue; bionic reserve and recharge appear only for followers with bionics.
Rules belong to the selected follower, and the palette can copy another follower's rules.
Options → Interface → NPC interface turns it off and keeps the original chat commands.

**Classic controls** are one option away: Options → Interface → Control scheme → Classic restores
the original vi-keys and numpad layout and makes Y/N prompts want capitals. Bump attacks default
to on in both schemes. Upgrades keep saved option choices: if an older profile has
**Attack by walking into enemies** off, enable it under Options → Interface. Your own key changes
are kept in both schemes, because the game now saves only the keys you changed. The modern layout
lives in `data/raw/control_schemes/modern.json` on top of the untouched upstream keybindings, so
other schemes can be added the same way. Quick stack, sort pile,
directional attack, auto-explore and body status have no key in classic; bind them or use the Enter action
menu. Modern groups actions under Enter, inventory and Space; right clicks select,
Ctrl+direction peeks, Ctrl+X waits/rests and Shift+X cycles movement modes. The Select tile keys
ship unbound; bind them in the keybindings menu if you want them.

`keybindings.json` starts with a format marker and holds only the keys you changed, including a
key set back to its upstream default. A file saved by an older version, without the marker, held
every key: entries in it that only repeat upstream's default are ignored, so it cannot undo the
scheme.

Clearing the last local key leaves an action unbound in that context. Choosing **Add global**
afterward removes that empty override so the new global key works immediately and after restart.
An action with remaining local keys still requires removing them before adding a global binding.

**Contextual interact** (Options → Interface → Contextual interact, on by default in Modern):
Space acts on the tile selected by right click (or a bound Select tile key) and lists its applicable
actions, including Open, Close, Examine, Pickup, Butcher, Jump and Smash. On your own tile it also
offers Ascend and Descend, using the same mount, vehicle and rope checks as the stair keys. Without a selected tile,
Space gathers the actions of every tile around you into one list, named by direction, and
highlights the tile of the highlighted row; a single safe action runs directly. Jump and Smash
always need an explicit choice; Smash uses local `S` so `s` remains menu navigation. It never
auto-attacks. Use item actions through inventory or the general Enter menu.

**Stances**, as in Quasimorph: **Shift+X** cycles walking, running, crouching and prone in Modern;
the Status box shows the current mode as a figure. F2/F3/F4 no longer select stances on the map. The
movement mode menu remains in Enter; Classic keeps its upstream movement controls.

Your first new game opens with a short welcome card listing these keys (Options → Interface →
Show welcome card brings it back). Like Caves of Qud's Classic and Roleplay modes, it then asks how
death works: _Permadeath_ (the default) or _Roleplay_, which offers to reload your last save when
you die. Autosave is on, so that save is recent. This only sets upstream's Options → General →
Prompt on character death, so you can change it later.

The first time your character gets hungry, thirsty, tired, hurt, overloaded, sees a hostile, steps
onto stairs or meets the night, a one-line tip in the message log says what to do and names the key.
The stairs tip uses the keys that are actually bound, so Modern and Classic both read correctly, and
one early tip says that the game saves for you, since new players look for a save key that does not
exist. Each tip shows once per character; Options → Interface → Show first-time tips turns them off.

With mouse tile selection, the hover hint names what a left click on that tile does, such as
"left: open the door", and that a right click selects. When mouse movement is explicitly enabled,
hints name the suggested click action and its key instead.

Yes/No prompts are selectable buttons. They open on **No**: move with the arrow keys (or `y`/`n`),
press Enter or click a button to answer, and Esc always cancels. Options → Interface → Answer Yes/No
prompts with Y and N makes `y`/`n` answer at once instead; the classic control scheme turns that on.

## Look

The terminal version stays pure text. The tiles version adds effects that only make sense with
pictures, and uses the bundled default tileset (MSX++ UnDeadPeople).

- **Color theme** (Options → Graphics). The default, _Terminal_, takes your terminal's palette and
  background, so the game follows whatever theme your desktop uses (Omarchy, base16, pywal and so
  on). _Tokyo Night_, _Catppuccin_, _Gruvbox_ and _Everforest_ are built in for terminals that
  allow palette changes, and _Classic_ keeps the original colors.
- On terminals with 16 colors, bright colors get their own color pairs instead of depending on
  bold text being drawn bright, which most modern terminals no longer do. Light and dark variants
  stay distinct and text no longer turns bold at random.
- Readable map glyphs (Options → Graphics): trees are ♣, pines ♠ and saplings τ instead of the digits
  7, 4 and 1 that newcomers read as numbers.
- Rounded window corners in the terminal version (Options → Graphics → Rounded window corners).
  Borders are drawn as real Unicode in UTF-8 terminals, which many terminals render better than the
  old line-drawing character set. Map walls keep square corners.
- Quieter main menu and a clearer pick-up list.
- **Status effect animations** (tiles view only). Every creature in sight — you, NPCs, monsters —
  carries a small looping overlay for a state it is in: a blood drip that falls down while it
  bleeds, flames while it burns, a poison icon while it is poisoned or sick, the dizzy stars and
  spiral while it is stunned or dazed, a bobbing "zz" while it sleeps, and a snowflake while it
  is cold. Monsters never got these; the overlays are the ones the tileset already draws on
  characters. They loop in real time even while you stand still, starting without another keypress.
  Options → Graphics → Status effect animations turns them off.
- **Fading sound markers**: the `?` for a sound you heard but cannot see stays for a few turns and
  dims as it ages, so you can see where noises came from (Options → Interface → Sound marker turns;
  1 gives the upstream behaviour, where it vanishes after your next action).
- **Monster health bars** (tiles view): a small bar under every hurt monster in view, using the same
  coarse reading the look-around list gives rather than exact hit points. Options → Graphics →
  Monster health bars turns it off.
- **Enemy edge arrows**: when a hostile you can see is outside the map window — the view is offset
  or zoomed, or it is simply past the edge — an arrow at the edge of the view points at it, red when
  it can reach you soon and yellow when it cannot. The arrow sits on the edge itself when the
  hostile is hunting you, one cell in when it is only trailing. Only hostiles you can already see
  get an arrow, so it shows nothing new about the world, only where to look. Options → Interface →
  Enemy edge arrows turns it off.
- **Cursor panning**, off by default: hold the mouse at the map edge to pan during normal play.
  Hover and clicks follow the panned view. Returning to the middle or moving into the sidebar
  stops scrolling; pressing a key recenters the view without making hover consume a turn.
  Options → Interface → Cursor panning enables it; Edge scrolling chooses the speed or disables it.
- **Pixel minimap zoom** (tiles): choose 1x, 2x or 4x under Options → Graphics without changing
  the main map's zoom. **Pixel minimap item markers**, off by default, adds gold dots for loot you
  can currently see. Items behind walls or inside sealed furniture do not get markers.
- **Item layering on furniture** (tiles): items sit slightly above tables and other furniture,
  using the same item, corpse and variant sprites as the map. Turn it off under Options → Graphics
  to restore the original sprite height.
- **Cliff edge shading** (orthographic tiles): a narrow dark edge marks a visible drop into open
  air without covering the ground texture. Hidden openings are not revealed. Options → Graphics →
  Cliff edge shading restores the original view.
- **Item thumbnails in UI** (tiles): inventory and pickup rows show the item's real sprite,
  including jewelry variants and corpses. Filtering clears old thumbnails, and sprites stay inside
  their list window. Options → Graphics → Item thumbnails in UI turns them off.
- **Mood lighting** (tiles): atomic lamps cast green light, blue glowsticks cast blue light, and
  candles and fuel lanterns cast warm light. Other colored emitters use the same native lighting
  path. Brightness, range, fuel use and game rules are unchanged. Options → Graphics → Colored
  lighting turns the tints off.
- **Fuller default tileset**: 12 sprites the bundled tileset lacked (atlatl, sewing machine,
  concrete ramps, treetops and others) come from the CDDA tilesets (CC-BY-SA 3.0, credits in
  `gfx/MSX++UnDeadPeopleEdition/fork_fill_CREDITS.md`).
- **More item pictures in the terminal**: 132 ASCII pictures from CDDA (CC-BY-SA 3.0) for 134
  items such as ammo, jars, bags and batteries, at the end of the item description like upstream's
  own (Options → Graphics → Enable ASCII art in item descriptions).
- **Window scaling** uses the selected monitor's usable desktop bounds. A supported 2× window
  no longer shrinks to the minimum size during startup.
- **Overhaul soundpack**, the default when the Otopack is not installed: footsteps, melee swings
  and hits, bullet impacts, reloads, bites, bionic zaps, menus and vehicle doors from Kenney's CC0
  packs. It has no music: gunshots, deaths and ambience stay silent rather than use a sound that
  does not fit. Sources in `data/sound/Overhaul/CREDITS.md`. Music and ambience come from the
  Otopack, which upstream release builds include. A source checkout downloads it separately:
  `bin/install-bno.sh` uses `build-scripts/bundle-registry-mods.ts` and keeps the pack's
  credits with its files. Pick it under Options → General → Choose soundpack.
  With shoes on, footsteps follow the ground type; moving through obstacles has its own clearing sound.

- **Grouped right sidebar**, based on the Opus HUD proposal, keeps the map free of HUD boxes.
  Weather, Character and Needs form titled groups. The sidebar also keeps limb health, wounds,
  movement, stats, load, location, messages, compass and controls. Vehicle readings join it when
  needed. The Location group keeps its 5×5 overmap chunk. The larger pixel minimap remains an
  optional **Map** panel in Sidebar Options. Below 40 rows, the groups lose their borders and
  titles, and urgent needs wrap to save space.
  New configurations use this layout. Existing saved layouts stay unchanged. Select **grouped**
  in **Enter → Misc → Sidebar Options** to try it, or choose a previous layout to restore map boxes.
  **Options → Interface → Sidebar position** keeps the sidebar on the right or moves it left.
  Corner positions and Compact corner bars do not apply to grouped. **Box icons** still selects
  the icon style of its Weather, Character, Needs and Vehicle groups.
- **Optional Weather and Status map boxes** remain available in the other sidebar layouts.
  Weather has four rows: an icon and description, season/day with time and a short sky track,
  Light, and Wind. The sky track shows the sun crossing the day, or at night the moon in its
  current phase crossing the night, so the night's moonlight can be judged at a glance; it is
  hidden underground. The box widens to fit its widest row, so a long weather name, a
  temperature or a translated date is never cut off.
  A watch reveals exact time; without one, time is approximate above ground and unknown below.
  A thermometer adds outdoor temperature. Wind letters name its origin; arrows show its flow.
  Status shows weapon and ammo, stance, and the fighting style once one is chosen. Below them
  it lists only the needs that call for attention (**Pain, Thirst, Hunger, Rest, Body temp**), one
  row each, or a single **Needs met** row when all are fine. Only a very hot or very cold body
  presses the Body temp row: mild warmth and chill stay in the detailed panels. Relevant mana
  remains `current/max`. Heat and cold each carry their own row icon; Rest uses one glyph.
  With icons the rows carry no labels; **Text only** keeps a label on every row. Normal gameplay
  descriptors and colors remain intact; Body temp describes body comfort, not the outdoor
  temperature.
  Options → Interface → Weather box / Status box moves or disables each box. Box icons selects
  **Text only**, Unicode or **Icon font**. The graphical version bundles the icon font: Material
  Design Icons and human stance figures for walking, running, crouching and lying prone (Pinhead,
  CC0), and uses it by default. A terminal needs a [Nerd Font](https://www.nerdfonts.com/) for
  it. Boxes avoid each other and the avatar's map center. A cramped Status box falls back to
  loadout-only or the sidebar; Needs disappear from the sidebar only when the box can carry them
  in Status. Weather, weapon and mana sidebar fields likewise return when their box cannot
  fit or is disabled, including immediately after changing options or resizing.
  **Compact corner bars** (Options → Interface) draws Weather and Status as one-row strips
  instead of the larger boxes. The Weather strip holds the same readings on one line.
  The Status strip holds weapon, chosen style, stance and mana, with urgent needs when they fit.
  The sidebar keeps the panels that the full boxes hide, so a short strip loses no reading.
- **Readable default typeface:** bundled JetBrains Mono NL Regular with Unifont fallback,
  anti-aliased at size 18, with 11 × 24 UI cells and square 24 × 24 map/overmap text cells.
  Oversized TTF glyphs shrink to fit their cells instead of losing strokes, including fallback
  symbols. Existing custom font files remain supported. Graphics options control cell dimensions,
  size and blending. [Font credits and licenses](docs/fork/asset-credits.md#fonts).
- **Vehicle box** appears when you board a vehicle or control one remotely. It shows
  azimuth (degrees clockwise from north), current speed, cruise target, engine state, the selected
  engine's fuel percentage and battery charge. Aircraft keep their takeoff-speed readout. Low fuel
  and battery readings change color; empty fuel still reads `0%`. In the grouped layout it stays
  in the sidebar. In other layouts it starts at the bottom right and stacks with boxes in the same
  corner. Options → Interface → Vehicle box moves the map box or turns it off. The Vehicle
  sidebar panel steps aside only when the box fits; disabling it or losing room restores that
  panel. Native tiles readouts are unchanged.
  Speed, azimuth and fuel values stay readable at the minimum supported 80 × 25 terminal size.
- **Body panel** (inspired by Project Zomboid's health screen): the sidebar lists every hurt limb
  and what is wrong with it (bleeding, infected, bitten, broken, bandaged, disinfected).
  **`h`** in Modern, or **Enter → Info → Body status**, opens the full view with every limb's health and what to do
  about wounds. Hide it like any panel from the sidebar options. The Hitchhiker's Guide remains
  available through Enter and item context menus.
- **Aligned sidebar**: every row uses one label width and one column grid, with a space after each
  colon, in every sidebar layout. The separate Sound panel starts hidden, because the Movement row
  already shows the sound level; turn it back on from the sidebar options.
- Gun and ammo info show **loudness**: the noise of one shot and a word for it (quiet, loud, very
  loud, deafening). An unloaded gun shows its default ammo, like the other stats.

## Sound & volume

Open **Enter → Misc → Sound & volume** to toggle **Sound** and **Music** separately, or adjust
**Music volume**, **Sound effect volume** and **Ambient volume** from 0 to 100%. Music starts on;
it needs a soundpack with music. Up/Down selects a row, Left/Right changes it, and Enter toggles a
switch or raises a volume. Changes apply immediately; **Escape** closes the menu and saves them.
The terminal build instead shows “Sound is unavailable in this build.”; Escape closes that notice.

## Items and storage

Upstream expects you to set up loot zones and run a sorting activity to keep a base usable. Here
that is optional:

- **Quick stack (Enter action menu)**, as in Terraria and Hytale. Everything you carry goes into storage within reach (a walkable straight line, dark or not)
  nearby (shelves, lockers, counters, vehicle cargo) that already holds the same item, or mostly
  the same kind of item. Loose piles on the ground are left alone. Worn, wielded and favorited (`*` in the
  inventory) items always stay with you. It costs the time it takes to walk over and put things
  down.
- **Sort pile (Enter action menu)**. Dump a haul in one place, stand on it and choose Sort pile. Each item goes to the
  nearby storage that already holds the same thing or mostly the same category, or to a loose pile
  of exactly the same item. Put one example of
  each kind of thing where you want it to live, and everything else follows.
- **Bigger crafting reach.** Crafting and construction pull from items within 12 tiles (upstream:
  6), so a workshop with stocked shelves works like a Hytale workbench next to chests. You can
  change it under Options → Debug → Crafting range.

- **Advanced inventory (Enter action menu) opens like a loot window**: everything around you on
  the left, your inventory on the right. Upstream's default pointed at the empty tile below you.
- **Crafting (`i`, then F5) opens on something useful**: recent recipes, or the first category
  you can craft from, not an empty favorites list. **Construction (Enter action menu)** does the
  same: an empty Favorite tab opens on `All` instead.
- **One pick-up list**: `g` shows everything within reach in one list.
- **Combine** (item menu, `C` in the modern scheme): partly used tools that hold their own charges
  and that nothing refills, such as matchbooks, pour into one, as in Project Zomboid. Every charge
  is kept and the emptied copies go away. Duct tape, thread and other counted items already stack.
- The crafting menu's full-description search (`d:`) remembers each recipe's description for the
  turn, so refining a search no longer rebuilds every item (from CDDA #77914).
- **Crafting part preview**: the panel starts with missing materials. `[parts:make]` marks a
  missing component with a known producer that can make one batch now; `[parts:known]` marks a
  known producer blocked by its materials, tools or qualities. `p` in the modern scheme opens the
  producer recipe. The selected recipe shows the missing units, producer prerequisites and native
  time estimate; charged outputs and byproducts count towards the units. Above 50 producer batches,
  it shows the batch count and time and prerequisites per batch instead of a misleading total.
  This is an immediate-producer preview, not a recursive plan or a promise that the inventory can
  supply every batch. Options → Interface → Crafting part chains restores the original panel.

- **Fewer battery types.** The light-minus, high-capacity and disposable variants are folded into
  three cells: light (150 charge), medium (750) and heavy (1500). Atomic cells stay as the rare
  long-life option, along with car and storage batteries. That is 9 batteries instead of 19, and
  every device takes the one cell size that fits it. Old saves convert automatically.
- **No duplicate containers.** The plastic 30-gallon barrel, steel keg, medium cardboard box, bag in
  a box and squeeze tube were near-copies of other containers and are merged into them.

- **Black powder handloads stack with factory rounds.** The 75 `bp_*` ammo items are gone. A
  black powder round is the normal round with a _black powder_ stack modifier, so 30 factory 9mm
  and 10 handloads make one stack, shown as `9mm JHP (40, 10 black powder)`. Each shot rolls which
  round fires, and only black powder shots hit softer, spread wider and kick less. They also keep
  their handload misfire chance, black powder fouling and muzzle smoke, and cost half as much as
  factory rounds. Loading, unloading and splitting keep the right share of handloads. Both mixed
  and pure handload stacks disassemble using the base round's recipe and return plain components,
  including smokeless powder where that recipe supplies it. The handloading recipes are still
  there, listed as `9mm JHP (black powder)`.
  Rounds already defined as black powder, such as the .45-70 handload, keep their own ballistics
  without an extra modifier; applying both would reduce their damage twice.

- **Jewelry: 292 items down to 9.** Rings, bracelets, earrings, necklaces, lockets, hairpins,
  tiaras, cufflinks and dental grills are one item each. The metal and gem are a variant the piece
  remembers, so you still find a "ruby and gold ring" or a "copper bracelet". Each one keeps its
  own price, material and melt-down parts (the ruby and the gold). Loot tables still name the exact
  piece they used to, and old saves convert. Pieces with a use or a story of their own stay
  separate: watches, badges, medals, holy symbols, wedding, engagement, purity and signet rings.
- **Books, games and belts.** The same treatment applies to 30 novels and other light reading,
  which become one _paperback_ ("western novel", "Murdered by the Grapevine", "book of poetry").
  Eight board and tabletop games become two items, and seven judo belts become one. Professions
  still start with the exact piece (the black belt, the gold necklace).
- **Jewelry stacks.** Different rings share one stack, like items in Don't Starve: "3 rings".
  Each ring still keeps its own name, gem, metal and price, so a stack is worth what its pieces
  are worth. With a tileset, each piece shows the sprite of the item it used to be.
- **Food of any freshness stacks**, with its rot averaged, as in Don't Starve. Rotten food never joins
  fresh food. Options → General → Freshness similarity threshold brings back the stricter
  upstream rule (0.25).
- **One MRE.** The 26 MRE boxes are one _MRE_. The entree is a variant
  (`MRE - Chili & Beans`), and opening it still gives that entree.

Zones (`Y`) and the loot-sorting activity are still there for anyone who wants them; loot sorting
just has no key in the modern scheme.

## Firearms

The guns and calibers CDDA cut over the years (5.45x39, 5.7x28, 4.6x30, 7.62x25, 9x18, .454,
.460, .500 S&W, .38 Super, .270 Win and .700 NX, with the AK-74M, AN-94, FN P90, Five-seveN, MP7,
PPSh-41, Tokarev, Makarov, S&W 500, Raging Bull and friends) live in Bright Nights' _Exotic ammo
types_ mod. It is now on by default for new worlds, so they spawn in normal loot. Leave it off
when creating a world if you prefer fewer calibers.

## Optional mods

**Limited Zombie Revival** (by sagittarius72, MIT) is bundled and can be picked when creating a world.
Zombies still rise, but weakened according to how mangled the corpse was, helpless for a moment
after rising, and only a limited number of times. It's a middle ground between upstream revival and
switching it off.

**Stocked River Barges** is a fork mod that new worlds enable by default; untick it under World
Mods to keep upstream's barges. Upstream thinned river barges ("cargo ships") to about one crate
per 52 tiles. The mod restores full holds with the same crate types, stocks the crew quarters'
trash cans, counters and sinks, and adds a few of the sealed Hermex containers the deck graffiti
warns about (military, rare or science loot). Sunken cargo ships were already full and are
unchanged.

## World presets

World creation offers ready-made settings for players who do not want to tune each world option.
On the World Options tab, or on the Current world page of the in-game options, press **p**
(modern scheme) and pick a preset. A preset first resets the page to the defaults and then sets a
few existing options; every value stays visible and editable afterwards:

- **Relaxed**: more loot and usable vehicles, fewer and weaker monsters that evolve more slowly,
  fewer NPCs.
- **Scarce**: 0.8x loot, 0.65x guns and ammo, fewer and more damaged vehicles. These are the
  values players on the r/cataclysmbn difficulty thread recommend.
- **Hardcore**: half the loot, more and tougher monsters that evolve faster, more NPCs, rare and
  wrecked vehicles, wandering hordes, crowd crush and a start surrounded by zombies (Black Road).
- **Default (reset page)**: the plain defaults.

Experience speed and skill rust are global Debug options, not world options, so presets do not
change them. Mods can add presets with the `WORLD_PRESET` JSON type
(`docs/en/mod/json/reference/options.md`). The classic scheme has no preset key.

## Plumbing (fluid grids)

Upstream's fluid grid connects tanks, sinks, showers and pumps inside one overmap tile. The fork
keeps its rules and makes failures explain themselves:

- The plumbing kit says why a connection cannot be made (another overmap, already connected, not
  connected) and only uses up parts and tools when the connection succeeds.
- Its report lists each stored liquid with the grid's total and capacity.
- Pouring or filling more than the grid holds says how much went in; the rest stays in your
  container.
- A tank that cannot be disconnected says whether the rest of the grid lacks room or cannot hold
  that liquid, and what to do.
- Mixing clean and tainted water in a single-tank grid explains that one tank holds only one kind.
- Disconnecting a tank no longer deletes items lying on its tile, and splitting a grid keeps every
  milliliter.

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
  "price": 0.5,
  "price_postapoc": 0.5,
  "ammo_effects": [ "RECYCLED", "BLACKPOWDER", "MUZZLE_SMOKE" ],
  "remove_ammo_effects": [ "NEVER_MISFIRES" ]
}
```

- A recipe marks its output with `"result_stack_modifier": "black_powder"`.
- A `MIGRATION` with `"stack_modifier": "black_powder"` turns an old item id into the base item
  with every unit modified, so saves keep their handloads.
- Stacks merge regardless of modifiers; counts add up on merge and split proportionally, with
  random rounding of fractional shares. Disassembly consumes the same proportional share and
  returns the base recipe's plain components; modifiers do not block disassembly.
- `damage`, `armor_penetration`, `dispersion` and `recoil` are multipliers, defaulting to `1`.
  They apply only to the selected modified round, not the whole mixed stack.
- `ammo_effects` adds ammo-effect ids; `remove_ammo_effects` removes them. Both default to empty
  lists. Removals happen before additions. The selected round's effects are used for misfires,
  cycling and fouling before firing, and for projectile effects such as muzzle smoke. A failed
  firing attempt does not consume a round or its modifier count.
  Ammo effect tooltips label how many rounds have each effect when a stack is mixed.
- `price` and `price_postapoc` are per-modified-unit multipliers, both defaulting to `1`.
  Prices weight plain and modified units by their actual counts, including rounds loaded in
  magazines. A stack of 30 factory rounds and 10 half-price handloads costs as much as 35 factory
  rounds, not 20 or 40.
- A unit carries at most one stack modifier; different modifiers describe separate units.

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
      "material": ["gold", "gemstone"],
      "components": [["gold_small", 2], ["ruby", 1]]
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
- Variant-specific fetch missions use `item_variant` and consume only matching variants.
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
- NPC "Size up stats" said "Hungry" for well-fed followers; the check was inverted
  ([upstream #10447](https://github.com/cataclysmbn/Cataclysm-BN/issues/10447)).
- A missed mutation attack reprinted the previous hit's damage
  ([upstream #1287](https://github.com/cataclysmbn/Cataclysm-BN/issues/1287)).
- An item made of no materials matched every "made purely of" (`M:`) search filter
  ([upstream #9617](https://github.com/cataclysmbn/Cataclysm-BN/issues/9617)).
- The list-items view described the stack's first item even when another group of the same item was
  selected ([upstream #870](https://github.com/cataclysmbn/Cataclysm-BN/issues/870)).
- Suppressed small-calibre guns go "plink!" again; the sound bands now match the newer loudness scale
  ([upstream #10415](https://github.com/cataclysmbn/Cataclysm-BN/issues/10415)).
- Starting as a delinquent logged an error: the super soaker's water was handed over still in its
  bottle (introduced upstream by #10533).
- Manual technique selection greyed out kicks for styles that keep kicking with a weapon in hand,
  such as Taekwondo ([upstream #10388](https://github.com/cataclysmbn/Cataclysm-BN/issues/10388)).
- Hacking a card reader opened only the doors within three tiles; it now opens the whole door
  line, like swiping the ID card ([upstream #10117](https://github.com/cataclysmbn/Cataclysm-BN/issues/10117)).
- The rope hanging below a vehicle ladder was invisible in the terminal
  ([upstream #10353](https://github.com/cataclysmbn/Cataclysm-BN/issues/10353)).
- Text formatting rejected argument numbers such as `%19$s` (the digit 9 was missing from the
  parser); saplings were never flagged `YOUNG`, so map extras that burn or infect trees skipped them.
- Followers in pain no longer take painkillers until they overdose
  ([upstream #10429](https://github.com/cataclysmbn/Cataclysm-BN/issues/10429)).
- Fixes from an adversarial review of the fork itself:
  - A `keybindings.json` saved by an older version (which stored every key) no longer undoes the
    control scheme; only keys you really changed count.
  - Quick stack and sort pile need a walkable straight line to a shelf, so nothing gets stashed
    through a window, bars or a fence.
  - Black powder counts stay right when a stack only partly fits in a vehicle trunk or container,
    and when stacks merge in your inventory. Black powder loot spawns as black powder again.
  - Old saves: unified batteries are trimmed to the new cell's capacity, and books folded into
    one item stay identified.
  - Classic really is upstream: setting it in `options.json` alone also turns bump attacks on,
    Y/N hotkeys on and one-click mouse movement off, and the extra "in the way" message is modern-only.
  - Attack commands never swap places with a pet or start talking to a friend; walking into an
    enemy under relaxation gas is refused before it costs any time.
- Fixes from a second adversarial review:
  - Picking an entry from the right-click tile menu did nothing; clicking "fire at" a monster
    aimed at the nearest hostile instead.
  - Built-in color themes left the terminal palette changed after quitting.
  - Black powder rounds loaded in a revolver lost their modifier when an older save was loaded.
- Loading is faster: item migrations finalize in one pass over item groups, and the JSON reader
  skips strings and whitespace straight from the stream buffer. In testing, the core data load and
  check went from 734 s to 118 s, and a new game starts in about 18 s.
- In the modern scheme the wait menu's "4 2 hours" and "6 6 hours" entries did nothing: `4` and `6`
  are the default left and right menu keys, and that swallowed the hotkey before the entry was
  looked up. An entry hotkey now wins over the horizontal keys. (Classic menus never register
  left and right, so `4` and `6` already worked there; the alarm menu's keys were broken the same
  way in the modern scheme and work now too.)
- Driving a vehicle that blocks the view painted the tiles it hid behind it black in the terminal;
  the memory of the ground stays where the tiles view already kept it
  ([upstream #10452](https://github.com/cataclysmbn/Cataclysm-BN/issues/10452)).
- Opening vehicle controls while remote-controlling a vehicle read part `-1` of its part list and
  could crash; it now opens the remote vehicle's controls
  ([upstream #5413](https://github.com/cataclysmbn/Cataclysm-BN/issues/5413)).
- Dropping or losing worn clothes all at once (death, a dropped inventory) kept the Stylish morale
  bonus, and the morale self-check later reported `Morale "Stylish" is inconsistent`.

## Playtesting

`tests/e2e/playtest.py` builds a situation for a fork feature in a fresh game and hands the game to
you:

```sh
python3 tests/e2e/playtest.py --list                 # the scenarios
python3 tests/e2e/playtest.py crafting               # play it in this terminal (tmux; Ctrl+B D leaves)
python3 tests/e2e/playtest.py status_effects --tiles # reopen the same game in the tiles window
python3 tests/e2e/playtest.py safe_mode --no-attach  # print the screen and close
```

Each run starts a new game in `/tmp/bn-playtest/<scenario>/` with the curses binary, runs the
scenario's Lua next to the player and prints what to check. `--scheme classic` tries the classic
keys. `--tiles` saves, then opens the save in `cataclysm-bn-tiles`.
The `stress` scenario puts 120 zombies around reinforced glass for checking smart safe mode and
edge-arrow responsiveness. The tiles launch uses a private `XDG_CONFIG_HOME` under the scenario
directory, so playtesting does not overwrite your normal tiles options.

A decision model can play a scenario by itself:

```sh
python3 tests/e2e/agent_playtest.py --scenario fork_features --models text --turns 30 \
        --report-dir /tmp/playtest-fork
```

With an OpenRouter key, the free OpenRouter models play instead; the key is read from the
environment or from a `KEY=VALUE` file and is never printed:

```sh
OPENROUTER_ENV_FILE=~/.config/free-pool/env python3 tests/e2e/agent_playtest.py \
        --scenario fork_features --mode curses --models openrouter-text --turns 30 \
        --report-dir /tmp/playtest-fork
```

The nightly GitHub Action uses the `OPENROUTER_API_KEY` repository secret for its live legs
(`openrouter-text` in the terminal build, `openrouter-vision` with screenshots in tiles).

It reads the state each turn, picks one action from the keys the current screen accepts, sends it and
writes one transcript line per turn plus a report naming any defect it found. `--dry-run` needs no
API key and opens no socket, so it doubles as the wiring check. Free models only: the pools, the free
daily allowances and what the console needs are in
[`docs/fork/agentic-playtests.md`](docs/fork/agentic-playtests.md). The deterministic suite below
stays the gate; a model run adds evidence, it never replaces a check.

## Building

Same as upstream; see `docs/en/dev/guides/building`. The presets need `clang`, `mold` and `ccache`
(`pacman -S --needed clang mold ccache`). The terminal version:

```sh
cmake --preset linux-curses
cmake --build --preset linux-curses --target cataclysm-bn
out/build/linux-curses/src/cataclysm-bn --basepath .
```

## Upstream merges

The fork follows upstream `main` with plain merges. When upstream adds black powder ammo
(`bp_*`) or items the fork folded into variants, fold them the same way: the new items become
migrations so old saves keep working, and loot entries keep the black powder `stack_modifier`.

The **Upstream feature issues** workflow runs daily or on manual dispatch. It reads upstream
`main` only and files one issue per clear feature: a non-merge conventional `feat:` or
`feature:` commit outside the `balance` scope. Issues are labelled `upstream-candidate` and
grouped by the upstream PR reference — including PRs merged with a merge commit — so several
commits of one feature share a ticket. Every other new commit, including `feat(balance)`, stays in
[the review tracker](https://github.com/Kenja-mc/Cataclysm-BN/issues/3) as a checklist row.
Commits at or below the fork's upstream merge base are already merged and are skipped.

Feature issues and checklists are not approvals: reject balance changes and choose useful UI,
control or item-folding changes manually. Closing a feature issue records rejection; later commits
for it are listed in the tracker, and the watcher never reopens or refiles it. Every write carries
a stable marker, so a failed run is safe to rerun; the tracker checkpoint advances a batch at a
time, only after that batch's issues and rows exist. CI never writes to the upstream and never
ports code automatically. Close the tracker to stop reporting; the workflow then exits without
writing and the daily job stays green. The tracker's CI-owned description is refreshed in place
when the workflow changes, leaving human notes alone. `--dry-run` prints the pending issues and
rows without writing, and `--self-check` runs offline before any API call: it covers
classification, PR grouping (including merge commits), deduplication, untrusted text, the merge
gate, the closed-feature fallback, the stop switch, tracker description migration, truncated
comparisons and partial-failure reruns.

## Future work

- [Agentic UI/UX QA in CI](https://github.com/Kenja-mc/Cataclysm-BN/issues/1): review real
  terminal and tiles captures with human triage; deterministic end-to-end checks remain the gate.
- [Build speed](https://github.com/Kenja-mc/Cataclysm-BN/issues/17): enable the ccache and mold
  wiring the presets already carry, then evaluate a game PCH, a faster test build type and one
  shared `_deps` checkout. Measured options and target numbers are in the issue.
- [Simple seamless co-op](https://github.com/Kenja-mc/Cataclysm-BN/issues/2): evaluate the BN
  co-op port and related projects before choosing an implementation. No multiplayer behavior is
  enabled by this ticket.

## Unit tests

Upstream's Catch2 suite (`cata_test`) must pass. Upstream CI runs it in file shards on a software
GPU, and the vision tests only agree with that setup, so run it the same way: Xvfb and the software
Vulkan ICD (Lavapipe, from `vulkan-swrast`) must be installed, and `VK_DRIVER_FILES` must point at
the ICD, then

```sh
cmake --preset linux-curses
cmake --build --preset linux-curses --target cata_test
Xvfb :99 &
DISPLAY=:99 VK_DRIVER_FILES="$HOME/.local/lavapipe/usr/share/vulkan/icd.d/lvp_icd.json" \
  build-scripts/run-linux-test-shards.ts --mode file-tags out/build/linux-curses/tests/cata_test -- --gpu-backend=software
```

Without the ICD the `20-visibility` shard fails to create a GPU device. For one shard or test case,
run `out/build/linux-curses/tests/cata_test` directly with `CATA_TEST_COMPUTE_ACCELERATION=cpu` and
a Catch2 filter. Running every test in one process is not supported upstream either: some tests
leave the map shifted for the next one.

The hidden `[benchmark][smart_safemode]` cases measure 12 blocked route searches and the
over-budget conservative stop separately. Monster-list timings are steady-state scans; they do
not include the first-sighting safety check. Arrow timings include fresh-turn route work.

## End-to-end tests

`tests/e2e/run.py` starts the terminal build inside tmux, creates a character and plays through the
fork features by sending real key presses and reading the screen. It needs `tmux` and a built
`cataclysm-bn` binary. The harness looks in `out/build/linux-curses/src`, then the repo root, then
the legacy `build/src`.

Each feature has its own module under `tests/e2e/` with a `TESTS` list; `run.py` is only the
runner and registry. A test that takes the shared game `g` runs on the runner's main game. A test
that needs other options borrows a game for its option profile from `fixtures.py`, which keeps one
game per profile for the whole process, because each new game costs about 12 seconds.

```sh
python3 tests/e2e/run.py                 # whole suite, parallel (up to 4 processes)
python3 tests/e2e/run.py --tier=smoke    # one test per module, about 2 minutes
python3 tests/e2e/run.py --list          # every registered test, its module and recorded time
python3 tests/e2e/run.py wasd_ jewelry   # only tests whose name contains a substring
python3 tests/e2e/run.py --serial --keep # one process; leave the main game open afterwards
```

Do not run unrelated heavy work alongside the suite. Each process uses a private tmux server,
world and user directory. `--shard=I/N` runs one of N shards (CI uses four); tests are assigned
longest first to the lightest shard using `tests/e2e/durations.json`, then run in suite order.
Use the `--parallel=N`, `--shard=I/N`, `--durations=PATH` and `--tier=` forms with `=`; unknown
options are errors. Test-name filters that match nothing are errors; empty shards skip game
startup.

`--durations=<path>` writes only this run's passing tests' elapsed seconds. CI uploads one such
file per shard; `python3 tests/e2e/merge_durations.py <shard files> --write` merges them into the
checked-in manifest, so the shard split follows CI's timings instead of a fast local machine's.
Refresh the manifest only from a successful full run, and rerun the suite afterward: updated
timings change which tests share a game.

CI playtests do not start automatically on pushes or pull requests. Nightly and manual runs
use `.github/workflows/fork-playtest.yml`; manual runs can select the suite, model playtests
and screenshots independently. Releases offer a default-off `run_playtests` checkbox. When
selected, the shared `.github/workflows/fork-e2e.yml` suite must pass before publication.

The tiles checks also need the tiles binary, ImageMagick's `magick`, Xvfb, the X11/XTest libraries
and a software Vulkan driver:

```sh
python3 tests/e2e/tiles.py minimap --vk-icd /path/to/lvp_icd.json
python3 tests/e2e/rendering.py --vk-icd /path/to/lvp_icd.json
python3 tests/e2e/lighting.py --vk-icd /path/to/lvp_icd.json
python3 tests/e2e/hud_tiles.py --vk-icd /path/to/lvp_icd.json
```

Run these sequentially with no other heavy work. They use private displays, saves and options;
their artifacts show the actual native ON/OFF pixels, not mocked widgets.
The shared curses inventory fixture has debug storage independent of random starting clothes.
The checks also isolate reload inventories and use an unseen NPC call for sound-marker lifetime,
so earlier weapons, automatic over-capacity drops and wind-masked footsteps do not change the fixture.
The targeting fixture starts with a real bound, loaded gun; the separate reload check drives
the reload UI. Lua setup refuses to type into the game if its console did not open.

## Performance checks

In a native debug world with all recipes unlocked, opening the weapon category (528 entries)
took 20.9 ms with the part preview and 21.7 ms without it. Warm medians over five further opens
were 14.6 and 15.5 ms. These include tmux input/capture overhead; they do not establish that the
preview is faster. The 250-producer-batch case showed the native 7 minute 30 second per-batch
estimate without expanding a recursive plan.

Smart threat checks limit fresh route work to 12 searches and reuse turn results. The native
benchmark measured 100 sealed searches at 73.7 ms, the bounded 12-search case at 6.59 ms, and
100 conservative over-budget stops at 607 ns. A warm monster-list scan measured 104 µs with the
option off and 108 µs with it on. A new turn still pays for fresh routes; the warm number does
not describe first sighting. No additional unmeasured refactor was justified by the runtime and
menu audits.

## Fork guide

The [fork guide](https://kenja-mc.github.io/Cataclysm-BN/guide/) uses this repository's item,
recipe, terrain, monster and mod data, rather than upstream's database. `J` opens it in the modern
scheme; Options → Interface → Hitchhiker's Guide URL can still point to another guide.
The documentation workflow rebuilds the guide when game data, tiles or guide scripts change.
Each dataset identifies its source commit; local exports with modified game data are marked
`-dirty`. `stable`, `nightly` and `latest` resolve to the same current fork snapshot, not three
different game releases. Moving aliases fetch current data before showing cached copies;
offline cached data remains available. Tile sheets retain their supplied credit and license files.
The GPL-3.0 guide app publishes its license and the modified corresponding source alongside the
site, including the fork's source-link, routing, cache freshness and sitemap changes.

To build it locally, install Deno, Node.js, pnpm and ImageMagick, then run `deno task guide:data`
and `deno task guide:build`. The app is pinned to
[`ushkinaz/cbn-guide@2bb50621`](https://github.com/ushkinaz/cbn-guide/tree/2bb50621d52e5ed7707631cb60b9a5d128b8670b).
`DATA_BASE_URL` can override the deployed dataset URL for a private preview.
