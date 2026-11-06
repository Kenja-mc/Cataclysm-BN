# Releasing Bright Nights Overhaul

Releases go to [Kenja-mc/Cataclysm-BN releases](https://github.com/Kenja-mc/Cataclysm-BN/releases).
`.github/workflows/fork-release.yml` publishes prerelease candidates after package, unit/data and
Windows updater checks pass. `.github/workflows/fork-promote.yml` promotes a candidate to stable
only after the full deterministic E2E suite passes on its exact source SHA. Neither writes upstream.
The Windows launcher uses `releases/latest`, so it continues to offer stable releases only.

## Candidate preflight

Before publication, review the exact source commit and version together. The commit must be the
intended fork commit on `main`, with a dated product entry in `CHANGELOG-OVERHAUL.md`.
For a versioned release, choose an unused canonical `vMAJOR.MINOR.PATCH`. Publishing pins its tag
before building; a later push to `main` cannot change the built commit.

Review the fork identity: titles and notes say Bright Nights Overhaul, and links target
`Kenja-mc/Cataclysm-BN`. Check that the changelog describes the selected source and that generated
notes include the expected dated sections. The download table must match the Windows zip and
Linux tarball, each with its `.sha256` file, under the names below.

Local checks follow the changed paths and affected behavior in `AGENTS.md`: build affected
targets, run targeted regression/smoke checks, and validate changed data. Docs-only changes need
no gameplay run. Do not require a full local E2E run before pushing or publishing a candidate.
The full suite gates nightly stable promotion instead.

For data-loader or validation changes, reproduce the Linux release data gate locally:

```sh
out/build/linux-curses/src/cataclysm-bn --basepath ./ --userdir /tmp/chk/ --check-all-mods
python3 build-scripts/test_mod_validation.py out/build/linux-curses/src/cataclysm-bn
```

The regression command requires valid mod data to exit zero and invalid mod data to exit nonzero.
CI runs it after `--check-all-mods` so data validation cannot pass merely by printing an error.

When reviewing candidate artifacts and affected entrypoints:

- Compare the selected SHA and version with each package's `VERSION.txt` and executable's `--version`.
- Launch the actual title screen and check that the window title identifies Bright Nights Overhaul.
- Exercise affected commands in `tools/*/README.md` and developer documentation as written, with
  private user directories.
- Report the checks actually completed; a targeted run is not a full-suite pass.

Inspect release notes locally, optionally passing the previous stable release's publication date:

```sh
build-scripts/fork-release-notes.sh CHANGELOG-OVERHAUL.md
build-scripts/fork-release-notes.sh CHANGELOG-OVERHAUL.md 2026-10-20
```

## Publish a candidate

Pushes to `main` allocate the next patch version above the highest existing canonical
`vMAJOR.MINOR.PATCH` fork tag, including reserved candidates. Eligible tags point to commits on
`main` ancestry containing `CHANGELOG-OVERHAUL.md`; bundled upstream tags do not count.
With no eligible tags, allocation starts at `v0.1.0`. Serialized release runs reserve the chosen
tag at the exact source commit before building. Package builds, Windows and Linux unit tests,
Linux data validation and updater checks must pass before the candidate becomes visible as a
prerelease. All assets are uploaded before publication; stable and its updater remain unchanged.

To choose a version explicitly:

1. Add the product changes to `CHANGELOG-OVERHAUL.md` and push to `main`.
2. Choose the next version and push only its tag:

   ```sh
   git tag -a v0.3.0 -m "Bright Nights Overhaul v0.3.0"
   git push origin v0.3.0
   ```

   Or dispatch from the intended commit with the version:

   ```sh
   gh-fork workflow run fork-release.yml --repo Kenja-mc/Cataclysm-BN --ref main -f version=v0.3.0
   ```

3. Watch `gh-fork run list --workflow fork-release.yml --repo Kenja-mc/Cataclysm-BN`.
   A successful run publishes a prerelease candidate, not a stable release.

Push the tag by name, never `git push --tags`: clones also contain upstream tags.
Only fork commits with `CHANGELOG-OVERHAUL.md` are eligible. GitHub's job token can refuse to tag
an older commit whose workflow files differ from the default branch; push that exact tag with
existing maintainer credentials instead. No extra personal access token is required.

## Promote a candidate to stable

`fork-promote.yml` runs nightly at 04:17 UTC and can also be dispatched from `main`:

```sh
gh-fork workflow run fork-promote.yml --repo Kenja-mc/Cataclysm-BN --ref main
```

It selects the newest published prerelease backed by a completed successful `fork-release` run,
requires its tag's exact commit to belong to `main`, and pins the source SHA, release identity,
assets and build evidence before calling the full deterministic `fork-e2e.yml` suite.
The suite runs eight independent shards (`--shard=I/8`), each serial within its own runner.
All eight must pass their pinned-checkout, lifecycle and gameplay checks; fail-fast is disabled
so a failed shard does not discard the others' evidence. Logs are retained as `e2e-suite-log-I`.
Manual `fork-playtest` runs, model playtests and screenshots are evidence only, not promotion gates.

After a complete E2E pass, promotion rechecks the trusted package/unit/data/updater evidence,
tag, asset identities and hashes. The candidate must be strictly newer than the current stable
commit in `main` ancestry and have a higher semantic version than every existing stable release.
An older run therefore cannot replace a newer stable release. Promotion changes the same GitHub
release from prerelease to stable and makes it latest. It does not rebuild, re-upload assets or
move the tag: players receive the candidate artifacts associated with the tested SHA.

A failed, timed-out, cancelled or incomplete suite never promotes. Missing or changed evidence,
tags or assets also block promotion. The previous stable release and `releases/latest` remain
unchanged. Advancing `main` while the suite runs never substitutes a different commit.

## Validate builds without publishing

Use an unpublished version label and disable publication to check workflow changes or warm caches:

```sh
gh-fork workflow run fork-release.yml --repo Kenja-mc/Cataclysm-BN --ref main \
  -f version=v0.2.1 -F publish=false
```

This runs both package builds, unit/data checks and the Windows updater gate and retains CI
artifacts. It creates neither a tag nor a GitHub release and cannot become a promotion candidate.
Repeat the same commit and label to inspect cache reuse; one successful run alone does not prove it.

## Correct notes without rebuilding

For an authorized notes-only correction, preserve the published tag and every binary asset:
do not dispatch `fork-release.yml`, push or move a tag, or rebuild/re-upload files. From the
reviewed checkout containing the changelog correction, generate the dated sections using the
previous release's publication date (omit the date for a first release):

```sh
build-scripts/fork-release-notes.sh CHANGELOG-OVERHAUL.md 2026-10-20 > /tmp/bno-changelog-notes.md
gh-fork release view v0.2.0 --repo Kenja-mc/Cataclysm-BN --json body --jq .body > /tmp/bno-release-notes.md
```

Review both files. In `/tmp/bno-release-notes.md`, retain the existing download table and replace
only the authorized changelog text with the generated correction. The generator prints dated
sections, not the download table. Then apply the reviewed description:

```sh
gh-fork release edit v0.2.0 --repo Kenja-mc/Cataclysm-BN --notes-file /tmp/bno-release-notes.md
```

This changes only the description, not the immutable build or tag. Commit the changelog correction
separately; do not check out the old tag and thereby discard the post-tag correction.

## Versions

| Part     | Raise it when                                                                         | Example  |
| -------- | ------------------------------------------------------------------------------------- | -------- |
| `vX.0.0` | saves from the previous release no longer load, or a big change in how the game plays | `v1.0.0` |
| `v0.X.0` | new features, new content, changed controls                                           | `v0.2.0` |
| `v0.0.X` | fixes only                                                                            | `v0.1.1` |

The first versioned release is `v0.1.0`. Versioned labels only go up. A published candidate is
immutable: choose a new version or commit rather than replacing its files. Promotion changes
release status, not its tag or assets. A failed unpublished build can be retried for the same
commit and label; once its tag exists, rerun the failed workflow jobs rather than moving the tag.

Automatic and manually versioned candidates both use canonical semantic versions, so existing
Windows updaters remain compatible. The updater installs only a higher version from the stable
`releases/latest` endpoint and validates the downloaded package's version before installation.
The exact source SHA is retained in package provenance and promotion evidence; it is not a
replacement for the semantic version.

## What the workflow does

| Job            | What it does                                                                                                                                                                                                                                                                                           |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `metadata`     | Runs only in `Kenja-mc/Cataclysm-BN`. Selects the exact source SHA and candidate label, checks fork identity and tag consistency, and refuses to replace a published candidate. Publishing pins a missing tag before builds; build-only runs never create tags.                                        |
| `updater-test` | Runs `fork-updater-test.yml` on Windows: checks Windows PowerShell 5.1 parsing and PSScriptAnalyzer, then exercises preservation, rollback/replay, unsafe archives/manifests/journals, checksums, concurrency and a running game with both PowerShell versions. Retains `windows-updater-evidence`.    |
| `build`        | Builds Windows MSVC tiles x64 and Linux tiles x64 packages through reusable `build.yml`, with unit tests and Linux data validation required. No translations, extra tilesets or registry mods.                                                                                                         |
| `publish`      | Packages the Windows launcher, `README-FIRST.txt` and `bno-files.txt`, version headers, platform archives and checksums. Requires successful build/unit/data/updater evidence and an unchanged source tag. Uploads every asset to a draft, then publishes it as a prerelease without making it latest. |

The Windows build also retains a `windows-tiles-x64-msvc-pdb` workflow artifact. Download it
with the matching release when investigating a crash; symbols from another build do not match.

Stable assets keep the same names, so these links always point at the latest promoted stable release:

| File          | Link                                                                                                      |
| ------------- | --------------------------------------------------------------------------------------------------------- |
| Windows zip   | `https://github.com/Kenja-mc/Cataclysm-BN/releases/latest/download/BrightNightsOverhaul-windows-x64.zip`  |
| Linux archive | `https://github.com/Kenja-mc/Cataclysm-BN/releases/latest/download/BrightNightsOverhaul-linux-x64.tar.gz` |

Each has a `.sha256` file next to it.

The release notes are a download table followed by every dated section of
`CHANGELOG-OVERHAUL.md` on or after the previous stable release's publication date (only the newest
section for the first release). Including that day avoids omitting same-day fixes, but can repeat
earlier changes from that day. `build-scripts/fork-release-notes.sh CHANGELOG-OVERHAUL.md 2026-10-20` shows what
they would be.

## Dependency reuse

- Windows restores vcpkg's compiled package archives from GitHub Actions cache. The key covers
  the architecture, runner OS, actual MSVC/SDK/CMake toolchain, manifest, overlays and build
  configuration. Compatible older manifests can seed the cache; vcpkg's native ABI hashes
  still decide which packages can be installed. New archives are saved only by successful,
  trusted runs. Pull-request events restore only.
- Windows and Linux compiler-cache buckets do not include the release tag or branch name.
  They separate actual toolchains, architectures, build modes and artifacts. The compiler
  cache checks each compilation unit; successful units remain reusable if a later step fails.
  Legacy `main` cache prefixes seed these ref-independent buckets on the next release run.
- Linux's bundled SDL3 uses a C precompiled header. CI sets
  `CCACHE_SLOPPINESS=include_file_ctime,include_file_mtime,time_macros,pch_defines` and
  `CFLAGS=-Xclang -fno-pch-timestamp` so ccache can reuse it; local presets are unchanged.
  See ccache's [precompiled-header requirements](https://ccache.dev/manual/latest.html#_precompiled_headers).
- The nightly promotion suite uses eight runners; only shard 0 writes the shared curses compiler
  cache. Model playtest legs restore only; screenshots write the tiles cache once.
  The separate weekly matrix has one writer per curses/tiles key.
- The host shader compiler keeps its fetched dependencies and incremental build tree in a
  separate cache keyed by image, installed packages, toolchain and recipe. Every restore is
  followed by CMake configure/build, so tracking upstream `main` does not freeze an old tool.
  Snapshots record the upstream revision actually built. Pull-request events do not save them.
- System packages still go through apt on each fresh Linux runner. Do not restore `/usr` or
  a package-manager database from cache: those files must stay consistent with the runner image.

The first matching run fills a cache. Use the build-only mode above for a second run, then
inspect the vcpkg restore summary, native compiler-cache statistics and shader compiler timings.
An exact archive-cache hit is not proof that every package ABI matched.

Prefer dispatching from `main` to seed reusable caches: GitHub exposes default-branch caches
to other refs, but a cache created only on one release tag is not shared with later tags.

The supported vcpkg backend is [`files`](https://learn.microsoft.com/en-us/vcpkg/reference/binarycaching#files),
persisted with [GitHub Actions cache](https://github.com/actions/cache).
The former `x-gha` provider has been removed from vcpkg.

## The Windows launcher and updater

The files live in `build-scripts/windows-launcher/`:

| File                       | Purpose                                                                                           |
| -------------------------- | ------------------------------------------------------------------------------------------------- |
| `Launch Bright Nights.bat` | What players double-click. Runs the updater in Launch mode, then starts `cataclysm-bn-tiles.exe`. |
| `Update Bright Nights.bat` | Runs the updater in Check mode and waits for a key.                                               |
| `bno-update.ps1`           | The updater. Windows PowerShell 5.1, ASCII only, no modules.                                      |
| `README-FIRST.txt`         | Short player guide shipped in the zip.                                                            |
| `test-bno-update.ps1`      | The end-to-end test CI runs. Not shipped.                                                         |

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
