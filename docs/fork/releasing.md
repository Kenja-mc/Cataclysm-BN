# Releasing Bright Nights Overhaul

Releases go to [Kenja-mc/Cataclysm-BN releases](https://github.com/Kenja-mc/Cataclysm-BN/releases).
Players download them there, and the Windows launcher updates itself from the newest one. The
workflow is `.github/workflows/fork-release.yml`; it never touches upstream.

## Cut a release

1. Add the changes to `CHANGELOG-OVERHAUL.md` under today's date and push to `main`. The
   release notes are taken from it.
2. Pick the next version (see below) and push a tag for it:

   ```sh
   git tag -a v0.1.0 -m "Bright Nights Overhaul v0.1.0"
   git push origin v0.1.0
   ```

   Or, without a local tag, run the workflow from GitHub and type the version:

   ```sh
   gh-fork workflow run fork-release.yml --repo Kenja-mc/Cataclysm-BN --ref main -f version=v0.1.0
   ```

3. Watch it with `gh-fork run list --workflow fork-release.yml --repo Kenja-mc/Cataclysm-BN`.
   The Windows build is the slow part; wait for both builds and the updater gate.

Push the one tag by name. Never run `git push --tags`: every clone also has upstream's `v0.5.2`
to `v0.13.0` tags. The workflow refuses any commit without `CHANGELOG-OVERHAUL.md`, so those
tags would only produce failed runs, but they would still clutter the fork.

## Versions

| Part | Raise it when | Example |
| --- | --- | --- |
| `vX.0.0` | saves from the previous release no longer load, or a big change in how the game plays | `v1.0.0` |
| `v0.X.0` | new features, new content, changed controls | `v0.2.0` |
| `v0.0.X` | fixes only | `v0.1.1` |

The first release is `v0.1.0`. Versions only go up: the updater installs a release when its
version is higher than the player's `VERSION.txt`, and only the highest version becomes the
"latest" release. A published version is immutable: a rerun refuses to replace it, because
players already on that version would not receive the rebuilt files. Choose a new patch version.
A failed draft can be retried for the same commit and version.

## What the workflow does

| Job | What it does |
| --- | --- |
| `metadata` | Runs only in `Kenja-mc/Cataclysm-BN`. Checks canonical `v1.2.3` syntax, a fork changelog, matching existing tags, and that the version has not already been published. Queries all release pages before choosing whether this becomes latest. |
| `updater-test` | Runs `fork-updater-test.yml` on Windows: parses scripts with Windows PowerShell 5.1, runs PSScriptAnalyzer, and exercises a local HTTP release with both PowerShell versions. Tests preservation, rollback/replay, unsafe archives/manifests/journals, missing checksums, concurrent updaters and a running-game process. Logs and failing mock installs are uploaded as `windows-updater-evidence`. |
| `build` | Builds the Windows MSVC tiles x64 and Linux tiles x64 packages through `build.yml`, the same reusable build upstream's releases use. No translations, no extra tilesets, no registry mods. |
| `publish` | Downloads the Windows installed directory and Linux tarball from `build.yml`; adds the launcher, `README-FIRST.txt` and `bno-files.txt` to Windows; writes version headers and stable archives plus `.sha256` files. Rechecks the tag immediately before publication and creates a missing dispatch tag at the built SHA. Creates/reuses only a draft, uploads all assets, then publishes. Only the highest version becomes latest. |

Release files keep the same names every time, so these links always point at the newest release:

| File | Link |
| --- | --- |
| Windows zip | `https://github.com/Kenja-mc/Cataclysm-BN/releases/latest/download/BrightNightsOverhaul-windows-x64.zip` |
| Linux archive | `https://github.com/Kenja-mc/Cataclysm-BN/releases/latest/download/BrightNightsOverhaul-linux-x64.tar.gz` |

Each has a `.sha256` file next to it.

The release notes are a download table followed by every dated section of
`CHANGELOG-OVERHAUL.md` on or after the previous release's publication date (only the newest
section for the first release). Including that day avoids omitting same-day fixes, but can repeat
earlier changes from that day. `build-scripts/fork-release-notes.sh CHANGELOG-OVERHAUL.md 2026-10-20` shows what
they would be.

## The Windows launcher and updater

The files live in `build-scripts/windows-launcher/`:

| File | Purpose |
| --- | --- |
| `Launch Bright Nights.bat` | What players double-click. Runs the updater in Launch mode, then starts `cataclysm-bn-tiles.exe`. |
| `Update Bright Nights.bat` | Runs the updater in Check mode and waits for a key. |
| `bno-update.ps1` | The updater. Windows PowerShell 5.1, ASCII only, no modules. |
| `README-FIRST.txt` | Short player guide shipped in the zip. |
| `test-bno-update.ps1` | The end-to-end test CI runs. Not shipped. |

On Windows the game keeps its user data in its own folder (`main.cpp` passes `"."` as the user
directory because the Windows build sets neither `USE_HOME_DIR` nor `USE_XDG_DIR`). The updater
therefore never touches `save\`, `config\`, `memorial\`, `graveyard\`, `templates\` and `font\`.
In `data\`, `data\mods\`, `data\sound\`, `gfx\`, `mods\` and `sound\` it replaces only what the
release ships and keeps what the player added. `bno-files.txt` lists what each release shipped,
so the next update can remove files a release dropped. Everything it replaces goes to
`.bno-update\backup` first. Rollback keeps these originals until every restore finishes, so a
second interruption can be recovered too. Do not delete this directory if recovery fails.

`PATH_INFO` evidence: `src/path_info.cpp:137-151` defines saves, memorials and portable config;
`:228-242` defines user fonts and graveyards; `:311-333` defines templates, user tilesets, mods
and soundpacks. `src/main.cpp:260-263` selects `"."` when neither home-directory option is
enabled; `CMakeLists.txt:37-45` defaults both options off on Windows.

The updater requires the checksum for network releases, rejects Windows-unsafe ZIP paths,
case-colliding entries and links, validates ownership manifests and recovery journals before
moving files, and refuses junctions/symlinks in an install being updated. A per-install lock
excludes another updater. Running-game detection precedes recovery and is repeated before
installation. Exit code 2 prevents the launcher starting an uncertain install; use the retained
backup for manual recovery if the next launch still cannot restore it.

Test the updater locally with PowerShell 7 (on Linux too):

```sh
pwsh -NoProfile -File build-scripts/windows-launcher/test-bno-update.ps1 -Shell pwsh
```

Also run, from the repository root:

```sh
actionlint .github/workflows/fork-release.yml .github/workflows/fork-updater-test.yml
shellcheck build-scripts/fork-release-notes.sh
build-scripts/fork-release-notes.sh CHANGELOG-OVERHAUL.md
```

On Windows, run `pwsh -NoProfile -File build-scripts/windows-launcher/test-bno-update.ps1 -Shell powershell.exe`
and repeat with `-Shell pwsh`. CI additionally runs the parser, ASCII/CRLF checks and
PSScriptAnalyzer. Failure output prints the retained mock-install directory.

### Windows review limits

Linux PowerShell tests do not exercise Windows PowerShell 5.1, cmd.exe parsing, Windows
file locking, process-image paths, junctions, SmartScreen, or the real MSVC-built game.
`windows-latest` covers script compatibility, file operations and the running-process guard.
The release build compiles the actual game with MSVC. A human must still extract the final
Windows asset, launch it through the batch file, load a save, and confirm input, rendering and
audio. Neither the local mock suite nor CI's mock executable proves those game behaviors.

Checksums detect download corruption; they are not independent signatures and do not defend
against a compromised release account. Keep the install in a writable local folder, not a
shared location another account can modify. The updater cannot prevent a person manually
starting the executable after its final running-process check.
