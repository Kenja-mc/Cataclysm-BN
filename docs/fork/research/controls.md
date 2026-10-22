# Modern control scheme: research notes

Status: research only. Nothing here changes `data/raw/control_schemes/modern.json` or any other
binding file. This branch (`research/controls`) holds the evidence for a later decision.

Sources:

- `controls-research/control-schemes-survey.md`: cross-game survey of 50+ top-down games.
- `controls-research/cbn-control-map.md` and `controls-research/proposed-modern-keymap.md`.
- The effective modern scheme: `data/raw/keybindings/*.json` overlaid with
  `data/raw/control_schemes/modern.json` on `(category, id)`; an overlay entry replaces the whole
  binding list (`src/input.cpp:314-319`), and an action missing from a category falls back to the
  `default` context (`src/input.cpp:588-619`).

## The three lists

Full tables: [`controls-lists-audit.md`](controls-lists-audit.md) (scout audit, all categories)
and [`controls-lists-raw.md`](controls-lists-raw.md) (script output).

| List | Count | Most consequential rows |
|---|---|---|
| Unbound in modern | 124 rows, 110 in gameplay (`DEFAULTMODE`) | Every item verb (wield, wear, eat, read, drop, take off, unload, apply), craft, construct, open and close door, smash, jump, pick up one tile, advanced inventory, control vehicle, save, sleep |
| Overloaded (one key, several controls in one context) | 15 identical-key groups, 50 case pairs | `VEHICLE` `f` = fold vehicle and toggle fridge; `INVENTORY_ITEM` `h` = wield and unwield; `TARGET` `Return` = fire and confirm; `DEFAULTMODE` `Tab` = next target and next tab; the 9 gameplay case pairs `w/W a/A s/S d/D q/Q e/E z/Z c/C x/X` (move vs look, pause vs move-mode cycle) |
| Duplicated (one control, several keys) | 144 controls | Intended: movement on WASD + arrows + numpad; zoom on wheel and `=`/`-` |

The case pairs are one physical key plus Shift: a Shift slip turns a step into a camera nudge.

## Decision model, first pass

`keymap_ask.py` builds the decision state from the survey's cross-game pattern table and
recommendations, the survival and base-building section of the survey, and the current modern
bindings for the actions in question. It asks `jev-latest` 32 choice questions with 3-4 scored
options each. Raw answers: [`jev-decisions-2026-10-22.json`](jev-decisions-2026-10-22.json).

Stability: the same questions with the options shuffled twice gave the same pick on 31 of 32
questions ([`jev-shuffles-2026-10-22.json`](jev-shuffles-2026-10-22.json)). The unstable one is
pause: `x` in the first order, `Esc` in both shuffles.

| Question | Pick | Confidence | Runner-up (probability) |
|---|---|---|---|
| Look layer | `Alt`+WASD | 0.59 | capital WASD 0.12 |
| Pick up | `g` one tile, `G` all | 0.58 | `g` all 0.17 |
| Drop | `Ctrl`+`D` | 0.55 | panel only 0.19 |
| Wield | `h` in the item panel | 0.48 | action menu only 0.19 |
| Wear | `W` in the item panel | 0.40 | action menu only 0.26 |
| Eat | `Ctrl`+`E` | 0.53 | `N` 0.21 |
| Apply / use | `Ctrl`+`A` | 0.28 | `U` 0.41 |
| Read | `R` | 0.73 | `Ctrl`+`R` 0.12 |
| Take off | `T` | 0.76 | action menu only 0.12 |
| Unload | `Ctrl`+`U` | 0.45 | action menu only 0.23 |
| Craft | `C` | 0.34 | action menu only 0.28 |
| Advanced inventory | `I` | 0.67 | action menu only 0.14 |
| Save and quit | main menu only | 0.59 | `Ctrl`+`S` 0.16 |
| Wait a turn | `.` | 0.40 | `Ctrl`+`X` 0.35 |
| Jump | `j` | 0.41 | `Ctrl`+`Space` 0.33 |
| Center view | `Home` | 0.23 | `:` 0.35 |
| Vehicle controls | `V` | 0.64 | `Ctrl`+`V` 0.21 |
| Doors | `o` toggles | 0.67 | `o` toggle plus `Ctrl`+`C` 0.19 |
| Smash | unbound | 0.61 | `Ctrl`+`V` 0.20 |
| Autoattack | unbound | 0.34 | `Tab` 0.33 |
| Pause | `x` | 0.30 | `Esc` 0.37 |
| Examine | `Space` | 0.97 | `Ctrl`+`E` 0.01 |
| Directional attack | unbound | 0.31 | `Ctrl`+direction 0.36 |
| Overmap pan | WASD | 0.28 | `H/J/K/L` 0.24 |
| Quicksave | `F5`/`F9` | 0.10 | `Ctrl`+`S`/`Ctrl`+`L` 0.40 |
| Quick stack | `Ctrl`+`G` | 0.33 | unbound 0.36 |
| Status screens | classic capitals (`M`, `P`, `@`, `#`, `p`, `[`) | 0.53 | one journal hub 0.20 |
| Zoom | wheel plus `=`/`-` | 0.35 | wheel only 0.40 |
| Movement menu | `"` | 0.14 | unbound 0.31 |
| Fire mode | unbound | 0.73 | `F` 0.13 |
| Classic verb layer | restore every verb whose letter is free | 0.52 | common verbs only 0.24 |
| Gamepad | menus only | 0.23 | full profile 0.31 |

The pick is always the most probable option. Confidence is lower than that probability: it
falls when the runner-up is close. Eleven rows have confidence under 0.35 (apply, craft, center
view, autoattack, pause, directional attack, overmap pan, quicksave, quick stack, movement menu,
gamepad); they are not decisions and need survey data before anyone ships them.

## Free keys in gameplay

Checked against the effective modern scheme, case-sensitive. Free in `DEFAULTMODE`:
`N U R T H V O J I G B P M . " & * ( - = + \ ] $ F , ; : @ # ) [ _ /`, `Home`, `Space`,
`Tab`. `Return` and `Esc` are taken (`action_menu`, `main_menu`). Taken capitals: `C` (look
south-east) and `X` (cycle movement mode), plus the rest of the look layer. Taken chords:
`Ctrl`+`W A S D Q E Z C` (peek), `Ctrl`+`P` (perks), `Ctrl`+`X` (wait several minutes).

## Next: survey data

`tests/e2e/keyguess.py` (on `main`) shows a decision model a real screen with the Controls panel
off, states a goal, and asks which key it would press. It then presses the key on a fresh game and
checks the goal through the game state. That turns the picks above into measured guesses on real
screens. Results go here when the first full run is in.
