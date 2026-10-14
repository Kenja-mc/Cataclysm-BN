# Playing and giving feedback

This fork ships with a ready-to-play install and a small feedback workflow. Everything below
works from a normal terminal or the desktop menu.

## Installation

Run once from the repository root:

```sh
./bin/install-cataclysm-bn.sh
```

This installs:

- launcher wrappers → `~/.local/bin/cataclysm-bn`, `~/.local/bin/cataclysm-bn-tiles`
- desktop entries → `~/.local/share/applications/` ("Cataclysm-BN" for tiles,
  "Cataclysm-BN (Curses)" for the terminal version)
- icon and metainfo, and a basepath config at `~/.config/cataclysm-bn/basepath`

The fork then appears in your app menu. The wrapper resolves the game's data directory from
`CATACLYSM_BN_BASEPATH`, the config file, or the current directory.

```sh
cataclysm-bn          # terminal (curses) version
cataclysm-bn-tiles    # tiles version
```

For graphics, launch **Cataclysm-BN** from the app menu or run `cataclysm-bn-tiles`.
The `cataclysm-bn` command launches the terminal version, which cannot display tiles.
The graphical version enables tiles by default and selects the bundled UnDeadPeople
tileset (`UNDEAD_PEOPLE_BASE`). Menus are text-based, with item thumbnails in inventory
and pickup lists; check the in-game map to see terrain and creature tiles.
The installed launchers use `~/.local/share/cataclysm-bn` for saves. The supplied graphical
build reads settings from `~/.config/cataclysm-bn`; the terminal build reads settings from
`~/.local/share/cataclysm-bn/config`. Graphics settings therefore need to be changed in the
graphical version.
If you previously disabled tiles in the graphical version, enable **Use tiles** under
**Options → Graphics**; launching it again does not override your saved preference.

Run `./bin/install-cataclysm-bn.sh --uninstall` to remove the installation.

## Playtesting

The fork's playtest harness (`tests/e2e/playtest.py`) sets up a scenario and hands you the
game. See `tests/e2e/playtest.py --help` and `OVERHAUL.md` for the full list:

```sh
python3 tests/e2e/playtest.py --list
python3 tests/e2e/playtest.py quick_stack          # your terminal; Ctrl+B D to detach
python3 tests/e2e/playtest.py quick_stack --tiles  # reopen in the tiles window
python3 tests/e2e/playtest.py quick_stack --no-attach  # print the screen and exit
```

Playtests use the terminal version unless you pass `--tiles`. Use that flag when checking
tiles or graphical rendering rather than the terminal map's glyphs.

Each run records a `SESSION.md` in the scenario's data directory (while the game is running) and
archives a copy at `~/.local/share/cataclysm-bn/playtests/<scenario>-<sha>-<date>.md` so the
context (scenario, scheme, commit SHA, checklist, options) is reproducible.

## Recording feedback

**Quick note (one line, no editor):**

```sh
bin/feedback "vehicle box truncation at 80x25" -m "Azimuth readout wraps to the next line on
an 80-char terminal."
```

**Structured entry (opens your editor with a dated skeleton):**

```sh
bin/feedback "quick stack doesn't reach the far rack"
```

Long-form write-ups should follow
[feedback-template.md](feedback-template.md) and be linked from this log.

## What to pay attention to

- **Controls:** WASD + Q E Z C, `F` attack, `n` auto-explore, contextual `Space`, stances
  (F2/F3/F4), quick stack (`Q`) and sort pile (`Z`), driving hints (`ws`/`ad`) and their return to
  `wasd` on release.
- **HUD:** weather/weapon boxes, Body panel (`H`), aligned sidebar, vehicle box at 80×25.
- **Targeting:** starts on the reachable hostile, warns about allies in the line of fire, loudness.
- **Crafting:** opens on recent recipes, "Missing: …", part producer hints (`p`).
- **Look:** ASCII art, colors, map glyphs, box behavior.
- **Sound:** fade-in markers, the Overhaul soundpack behavior.

Report bugs and suggestions via `bin/feedback`, and use the [feedback template](feedback-template.md)
when filing anything on GitHub.
