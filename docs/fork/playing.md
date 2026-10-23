# Playing and giving feedback

Each fork release carries a Windows zip and a Linux archive. Linux users can also build from
source.

## Windows: download and update

You do not need to build anything on Windows.

1. Open the [latest release](https://github.com/Kenja-mc/Cataclysm-BN/releases/latest) and
   download `BrightNightsOverhaul-windows-x64.zip`.
2. Right-click the zip, choose **Extract All**, and pick a folder you can write to, such as
   `Documents\Games`. Do not use `C:\Program Files`: the game keeps your saves in its own folder.
3. Open the `BrightNightsOverhaul` folder and double-click **Launch Bright Nights.bat**.

If Windows shows "Windows protected your PC", first confirm you downloaded the zip from the
fork's release page above. This build is unsigned. If you trust that source, choose **More
info**, then **Run anyway**. Do not bypass a warning for a download from an unknown source.

### How updates work

| What you do                                                       | What happens                                                                                                                                                                                                                   |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Start the game with `Launch Bright Nights.bat`                    | It asks GitHub for the newest release. If that is newer than yours, it shows the new version and a link to what changed, then asks `Update to vX now? [Y/n]`. Press Enter to update, or type `n` to play the version you have. |
| Start it with no internet, or GitHub does not answer in 5 seconds | The game starts without asking anything.                                                                                                                                                                                       |
| Double-click `Update Bright Nights.bat`                           | It checks now and tells you the result, also when you already have the newest version.                                                                                                                                         |
| Start `cataclysm-bn-tiles.exe` directly                           | No update check.                                                                                                                                                                                                               |

An update downloads the new zip, checks it against the release's SHA-256 checksum, unpacks it,
and then swaps the game files. Close the game first. If installation fails, the updater attempts
to restore the old files. If the computer turns off during an update, the next launch restores
them before checking for another update. If recovery cannot finish, the launcher does not start
the game: keep `.bno-update\backup` and the error message, close any game or updater process,
then try again. Do not delete the backup while recovery is incomplete.

### Where your files live

The Windows version keeps everything in its own folder, so the whole folder is your install.

| Folder                                          | What it holds                        | After an update                                                 |
| ----------------------------------------------- | ------------------------------------ | --------------------------------------------------------------- |
| `save\`                                         | your worlds and characters           | kept                                                            |
| `config\`                                       | options, key bindings, font settings | kept                                                            |
| `memorial\`, `graveyard\`                       | records of dead characters           | kept                                                            |
| `templates\`                                    | character templates                  | kept                                                            |
| `font\`                                         | fonts you added                      | kept                                                            |
| `mods\`, `data\mods\`                           | mods                                 | your own mods are kept; the release's mods are replaced         |
| `gfx\`                                          | tilesets                             | your own tilesets are kept; the release's tilesets are replaced |
| `sound\`, `data\sound\`                         | soundpacks                           | your own soundpacks are kept                                    |
| everything else (`data\json\`, the `.exe`, ...) | game files                           | replaced                                                        |

To back up your games, copy `save\` and `config\`. To move the game, move the whole folder. Do
not edit files in `data\json\` or other game folders: an update replaces them.

Use unique folder names for your own mods, tilesets and soundpacks: an entry with the same name
as shipped content belongs to the release and is replaced. The updater refuses links/junctions
in an install being updated; use ordinary folders. A second updater or a running game blocks
installation and recovery.

### Music

The release has no music, because the Otopack soundpack does not allow redistribution. To add it,
download the zip from the
[Otopack BN Mk 2 release](https://github.com/NarandBD/Otopack-BN-Mk-2/releases/tag/sorrynotsorry),
copy the `Otopack+ModsUpdates BN` folder from inside it into the game's `sound\` folder, choose it
under **Options → General → Choose soundpack**, and restart. Updates keep it.

While playing the sound-enabled graphical version, open **Enter → Misc → Sound & volume**.
**Sound** controls all audio; **Music** switches music independently and starts on by default.
The three volume rows control music, sound effects and ambience from 0 to 100%. Select a row
with Up/Down and change it with Left/Right; Enter toggles a switch or raises a volume.
Changes take effect at once. Press **Escape** to close the menu and save them.
The terminal version has no audio and shows “Sound is unavailable in this build.” instead.

## Linux: download a release

Download `BrightNightsOverhaul-linux-x64.tar.gz` from the
[latest release](https://github.com/Kenja-mc/Cataclysm-BN/releases/latest), then:

```sh
tar -xzf BrightNightsOverhaul-linux-x64.tar.gz
./BrightNightsOverhaul/cataclysm-launcher
```

The Linux release keeps saves and settings in `~/.cataclysm-bn/`, outside the game folder. There
is no automatic updater on Linux. To update, download the new release, delete the old
`BrightNightsOverhaul` folder (your saves are not in it) and unpack the new one in its place.
`VERSION.txt` in the folder shows the version you have.

## Building from source on Linux

Build the terminal and graphics versions first. The presets need `clang`, `mold` and `ccache`
installed:

```sh
cmake --preset linux-curses
cmake --build --preset linux-curses --target cataclysm-bn
cmake --preset linux-full
cmake --build --preset linux-full --target cataclysm-bn-tiles
```

Then run once from the repository root:

```sh
./bin/install-bno.sh
```

This installs:

- launcher wrappers → `~/.local/bin/bno` (terminal), `~/.local/bin/bno-tiles` (graphics)
- desktop entries → `~/.local/share/applications/` ("Bright Nights Overhaul" for tiles,
  "Bright Nights Overhaul (Curses)" for the terminal version; `--no-curses-entry` leaves the
  terminal version out of the app menu and keeps its `bno` command)
- the app icon and a basepath config at `~/.config/bright-nights-overhaul/basepath`
- the Otopack soundpack (music and ambience) in `data/sound/Otopack+ModsUpdates BN`, downloaded
  with `deno` through upstream's registry bundler. Downloaded audio and its credits stay outside
  version control. Choose it under **Options → General → Choose soundpack**, then restart.
  The game picks it by default only if you never saved another soundpack.

The fork then appears in your app menu next to an upstream Cataclysm-BN install. It uses its
own app id (`io.github.kenja_mc.BrightNightsOverhaul`), commands, saves and settings, so the
two installs do not replace or launch each other. The wrapper resolves the game's data
directory from `BNO_BASEPATH`, the config file, or the current directory.

```sh
bno          # terminal (curses) version
bno-tiles    # tiles version
```

For graphics, launch **Bright Nights Overhaul** from the app menu or run `bno-tiles`.
The `bno` command launches the terminal version, which cannot display tiles.
The graphical version enables tiles by default and selects the bundled UnDeadPeople
tileset (`UNDEAD_PEOPLE_BASE`). Menus are text-based, with item thumbnails in inventory
and pickup lists; check the in-game map to see terrain and creature tiles.
The installed launchers use `~/.local/share/bright-nights-overhaul` for saves. The supplied
graphical build reads settings from `~/.config/bright-nights-overhaul`; the terminal build
reads settings from `~/.local/share/bright-nights-overhaul/config`. Graphics settings
therefore need to be changed in the graphical version.
If you previously disabled tiles in the graphical version, enable **Use tiles** under
**Options → Graphics**; launching it again does not override your saved preference.

The first install copies `~/.local/share/cataclysm-bn` and `~/.config/cataclysm-bn` to the
new locations when these do not exist yet, so existing saves and settings carry over. The old
directories are left unchanged for an upstream Cataclysm-BN install.

Run `./bin/install-bno.sh --uninstall` to remove the fork's launchers and menu entries;
saves and settings stay. To move back to upstream, launch upstream's own
`cataclysm-bn` / `cataclysm-bn-tiles` (or its app-menu entry). To keep playing with the saves
made in the fork, copy `~/.local/share/bright-nights-overhaul` and
`~/.config/bright-nights-overhaul` over the old directories before removing the fork.

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

- **Controls:** WASD + Q E Z C walk and bump-attack; arrow keys aim. Tab/Shift+Tab cycle visible
  hostiles freely in distance/position order with wraparound; `f` attacks the selection using
  normal gun aiming. Enter groups all actions (Info for character/status screens). Ctrl+X opens
  wait/rest; Shift+X cycles walk/run/crouch/prone, with F2/F3/F4 unbound.
- **Inventory:** `i`, then select an item for Wield/Wear/Eat/Use/Read and other context actions.
  `v` opens Wield directly. F5 Craft remains available even when inventory is empty.
  `g` takes everything underfoot without a menu; Ctrl+G opens area pickup, where `g` or Enter
  confirms. Quick stack and sort pile remain in Enter.
- **Select and interact:** Shift+WASD/QEZC selects a tile without spending time.
  Space acts on that selection. Without a selection, it lists nearby actions with directions
  and highlights the tile of the current row. Jump and Smash need explicit choices (`S` for Smash).
  Space offers Butcher for a corpse underfoot. `B` also opens Butcher.
  Ctrl+WASD/QEZC physically peeks for the normal 200 moves, then returns without clearing selection.
  In Modern curses, Ctrl+C/Z are game chords. Classic keeps normal terminal signals.
- **Mouse:** right click selects a map tile. Left click uses an adjacent door, item or furniture,
  attacks a hostile, or selects other tiles. Default Modern clicks do not walk.
  Classic keeps upstream mouse behavior.
- **HUD:** select **grouped** in Enter → Misc → Sidebar Options for the new right-sidebar layout.
  Weather, Character and Needs move off the map. Existing layouts remain selectable.
  Try Text only, Unicode and Icon font. Make sure that urgent needs, limb health and controls
  survive resizing to 80×25. A watch reveals exact time and a thermometer reveals temperature.
  `h` opens body details (also Enter → Info → Body status). `@` opens the character sheet and `P` the log.
  `F` opens fire-mode selection.
  Check vehicle/readout fallbacks at 80×25, driving hints (`ws`/`ad`), and their return to
  `wasd` on release. The new bundled typeface should show readable labels and complete glyphs.
- **Targeting:** gun aiming starts on the reachable hostile and warns about allies in the line of
  fire; check loudness. Map target cycling is selection, not an attack.
- **Crafting:** `i`, then F5; opens on recent recipes, "Missing: …", part producer hints (`p`).
- **Look:** ASCII art, colors, map glyphs, box behavior.
- **Sound:** fade-in markers and music/ambience with the Otopack soundpack selected.

Report bugs and suggestions via `bin/feedback`, and use the [feedback template](feedback-template.md)
when filing anything on GitHub.
