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

- [ ] WASD movement + Q E Z C diagonals, F attack, Space interact, C character, X wait/rest
- [ ] Arrow keys and numpad movement still work
- [ ] `n` auto-explore avoids walls/closed doors/traps and refuses to start near hostiles
- [ ] Contextual `Space` action (single sensible action, or lists directions)
- [ ] Stances (F2 run, F3 crouch, F4 prone) show in the weapon box / Movement row
- [ ] `Q` quick stack to nearby matching storage; items in hand stay with you
- [ ] `Z` sort pile routes items to the right storage
- [ ] `y` talk, `Tab` attack in direction, `F1` help, `?` all keys
- [ ] **Vehicle box reads at 80×25:** azimuth, speed, fuel, battery visible
- [ ] **While driving:** `ws throttle` / `ad steer` hints; **on release:** `wasd move` returns

### HUD & sidebar

- [ ] Weather box (top-left): icon, time, temperature, season/day, light, moon, wind
- [ ] Weapon box: weapon, ammo, style, stance, mana
- [ ] Body panel lists injured limbs; `H` opens full limb details
- [ ] Aligned sidebar rows (single label column, space after colon)
- [ ] Sound panel hidden by default (Movement row already shows sound level)
- [ ] Box icons / positions configurable via Options > Interface

### Targeting & combat

- [ ] Aiming starts on the reachable hostile; allies in the line of fire are warned
- [ ] `f` fires, `r` switches ammo, `F`/`m` fire mode
- [ ] Gun info shows loudness (`Loudness: N (loud|very loud|…)`)
- [ ] Mouse hover/click on map tiles: hints name the action and key

### Items & variants

- [ ] Black powder rounds stack with factory rounds (`10 black powder`)
- [ ] Folded containers / batteries / jewelry: fewer distinct items, old saves convert
- [ ] Combine tools (matchbooks) merge charges
- [ ] Advanced inventory (`/`) shows local items left, inventory right

### Crafting

- [ ] Opens on recent recipes / first craftable category
- [ ] Panel starts with "Missing: …"; `[parts:known]` / `(can make)` tags
- [ ] `p` jumps to the producer that can make one batch now
- [ ] 12-tile crafting reach (changed from upstream's 6)

### Look

- [ ] ASCII art item descriptions (`--enable-ascii-art` / options)
- [ ] Readable map glyphs (trees ♣ / pines ♠), color theme, rounded corners
- [ ] Weather/weapon/body boxes render correctly

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
