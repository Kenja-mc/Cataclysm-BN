# Feedback template

Use this when writing up playtest observations for the fork. One file or issue per topic is easiest
to triage; reference the session commit SHA (shown by `--version` in the game's Info screen).

## Header

```
# <short title>

- **Date:** YYYY-MM-DD
- **Commit SHA:** (e.g. 55609ada07 — check the game's `--version`)
- **Branch:** main
- **Scheme:** modern (or classic)
- **Variant:** curses (terminal) / tiles
- **Terminal:** <name / size>  or  **OS:** <name, version> (tiles)
- **Reproducible:** yes / no / unclear
- **What you were doing:** <one line of context>
```

## What to check (mark [x] passed, [–] broken, [!] not tried)

### Controls

- [ ] WASD + Q E Z C and numpad movement, bump attacks; top-row numbers do not walk on the map
- [ ] Enter groups every action category; Info opens character/status screens; Ctrl+X opens wait/rest
- [ ] `i` selects items for Wield/Wear/Eat/Use/Read; Wield is equipment, not a primary map key
- [ ] Inventory shows F5 Craft and opens crafting even when empty
- [ ] Shift+direction moves a free reticle from the player, accumulating one tile per press
- [ ] Ctrl+direction physically peeks for 200 moves and returns to the starting position on cancel
- [ ] Modern curses Ctrl+C/Z are game chords; Classic still quits/suspends through normal signals
- [ ] Tab/Shift+Tab cycle visible hostiles freely by distance/position, wrapping in both directions
- [ ] Arrow keys move the aim reticle; `f` attacks the selection, with normal gun aiming
- [ ] Map right click selects freely; left click attacks; no Modern single/double/near/far click walks
- [ ] Modern aiming RMB selects without firing; LMB fires; Classic keeps upstream mouse buttons
- [ ] `n` auto-explore avoids walls/closed doors/traps and refuses to start near hostiles
- [ ] Space uses the RMB/Shift-look tile and offers applicable Open/Close/Examine/Pickup/Jump/Smash
- [ ] Jump and Smash require an explicit choice, not automatic action dispatch
- [ ] Shift+X cycles walk/run/crouch/prone; Status / Movement row agree; F2/F3/F4 are unbound
- [ ] Enter's Quick stack sends items to nearby matching storage; worn/wielded/favorite items stay
- [ ] Enter's Sort pile routes items to the right storage
- [ ] Chat and other former global menu actions remain in Enter; F1 help, `?` all keys, `<`/`>` stairs
- [ ] **Vehicle box reads at 80×25:** azimuth, speed, fuel, battery visible
- [ ] **While driving:** `ws throttle` / `ad steer` hints; **on release:** `wasd move` returns

### HUD & sidebar

- [ ] Weather box: four rows for icon/description, date/time, Light and Wind; instrument gates intact
- [ ] Status box: weapon/ammo, style, stance, fixed Pain/Thirst/Hunger/Rest/Heat rows, relevant mana
- [ ] Text only and Unicode modes keep labels and meaning; no missing glyphs with bundled defaults
- [ ] Narrow/short views restore sidebar facts; toggles and resize work without another action
- [ ] Body panel lists injured limbs; Enter → Info → Body status opens full limb details
- [ ] Aligned sidebar rows (single label column, space after colon)
- [ ] Sound panel hidden by default (Movement row already shows sound level)
- [ ] Box icons / positions configurable via Options > Interface

### Targeting & combat

- [ ] Aiming starts on the reachable hostile; allies in the line of fire are warned
- [ ] On the map, `f` attacks the selected target; inside aiming, `f` fires, `r` switches ammo, `F`/`m` fire mode
- [ ] Gun info shows loudness (`Loudness: N (loud|very loud|…)`)
- [ ] Mouse hover/click on map tiles: hints name the action and key

### Items & variants

- [ ] Black powder rounds stack with factory rounds (`10 black powder`)
- [ ] Folded containers / batteries / jewelry: fewer distinct items, old saves convert
- [ ] Combine tools (matchbooks) merge charges
- [ ] Advanced inventory (Enter action menu) shows local items left, inventory right

### Crafting

- [ ] `i`, then F5 opens crafting on recent recipes / first craftable category, even with empty inventory
- [ ] Panel starts with "Missing: …"; `[parts:known]` / `(can make)` tags
- [ ] `p` jumps to the producer that can make one batch now
- [ ] 12-tile crafting reach (changed from upstream's 6)

### Look

- [ ] ASCII art item descriptions (`--enable-ascii-art` / options)
- [ ] Readable map glyphs (trees ♣ / pines ♠), color theme, rounded corners
- [ ] Weather/Status/body boxes render correctly with the larger, anti-aliased default typeface

### Sound & UI polish

- [ ] Fade-in sound markers (`?`) appear behind walls and dim over time
- [ ] Yes/No prompts are selectable buttons; Esc cancels
- [ ] Welcome card and first-time tips appear (on by default)

### Bugs

```
## Bug report

**What happened:**
**Expected:**
**How to reproduce:**
**Screenshots / log:**
```

### Suggestions

```
## Suggestion

**Idea:**
**Why it helps:**
```

## Other observations

Notes about pacing, confusion points, or anything not covered above.
