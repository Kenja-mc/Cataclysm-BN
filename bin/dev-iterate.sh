#!/usr/bin/env bash
# Quick-iterate launcher: rebuild only the game with an unoptimized preset and optionally launch it
# straight into a development save. Run with --help for options and caveats.
set -euo pipefail

script=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/$(basename -- "${BASH_SOURCE[0]}")
repo=$(cd -- "$(dirname -- "$script")/.." && pwd -P)

usage() {
    cat <<'USAGE'
Build only the game with a quick-iterate preset and optionally launch it into a save.

usage: bin/dev-iterate.sh [--tiles] [--world NAME] [--userdir DIR]
                          [--no-build] [--no-run] [-- GAME-ARGS]

  --tiles       use linux-tiles-dev instead of linux-curses-dev
  --world NAME  world to load (default: $CATA_DEV_WORLD or "dev"); loads its first character
  --userdir DIR saves, config and logs (default: $CATA_DEV_USERDIR or out/dev-userdir/)
  --no-build    launch the last build without rebuilding
  --no-run      build only and exit; never opens a window, so it is safe for automation
  -- GAME-ARGS  everything after -- is passed to the game binary

This is an iteration build, not a validation build: -O0, -g1, NDEBUG (assert() compiled out,
RELEASE=1), and no tests, clang-tidy or Tracy. Use linux-curses or linux-full for the test gate,
for performance numbers, or when debugging.

The dev presets build without XDG or home directories, so saves, config and logs stay in --userdir
and dev runs never touch your normal profile. Create a world and a character from the main menu
once; later runs load its first character. While the game runs it holds a shared lock, so a build
waits for it to exit instead of relinking the binary underneath.
USAGE
}

need_value() {
    if [[ -z ${2-} || ${2-} == -* ]]; then
        echo "$1 needs a value (got '${2-}')" >&2
        exit 2
    fi
}

cd "$repo"

preset=linux-curses-dev
target=cataclysm-bn
world=${CATA_DEV_WORLD:-dev}
userdir=${CATA_DEV_USERDIR:-out/dev-userdir/}
build=1
run=1

while (($#)); do
    case "$1" in
        --tiles) preset=linux-tiles-dev target=cataclysm-bn-tiles ;;
        --world) need_value "$1" "${2-}"; world=$2; shift ;;
        --userdir) need_value "$1" "${2-}"; userdir=$2; shift ;;
        --no-build) build=0 ;;
        --no-run) run=0 ;;
        --) shift; break ;;
        -h | --help) usage; exit 0 ;;
        *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
    esac
    shift
done

if ((!build && !run)); then
    echo "--no-build with --no-run leaves nothing to do (see --help)" >&2
    exit 2
fi

if ((!run && $# > 0)); then
    echo "--no-run does not launch, so these game arguments would be ignored: $*" >&2
    exit 2
fi

command -v flock >/dev/null || {
    echo "flock (util-linux) is required: builds and runs share a per-tree lock" >&2
    exit 1
}

tree=out/build/$preset
binary=$tree/src/$target
lock=out/build/$preset.lock
mkdir -p out/build

if ((build)); then
    # Warnings belong in the build log too: a green build here proves nothing about tests.
    echo "warning: $preset is -O0 -g1 -DNDEBUG: assert() is disabled, RELEASE=1, and tests are not built." >&2
    echo "warning: use this build to iterate, never as the test gate or for performance numbers." >&2
    start=$SECONDS
    # One lock per tree: a parallel configure or build of the same tree corrupts it.
    flock "$lock" sh -eu -c '
        # mise.toml pins the build tools when mise is installed; otherwise use the PATH ones.
        if command -v mise >/dev/null 2>&1; then
            tools="mise exec --"
            ninja=$(mise which ninja)
        else
            tools=""
            ninja=$(command -v ninja)
        fi
        if [ ! -f "$1/build.ninja" ] ||
            [ CMakeLists.txt -nt "$1/build.ninja" ] ||
            [ CMakePresets.json -nt "$1/build.ninja" ] ||
            [ -n "$(find CMakeModules -newer "$1/build.ninja" -print -quit)" ] ||
            ! grep -Fxq "CMAKE_MAKE_PROGRAM:FILEPATH=$ninja" "$1/CMakeCache.txt"; then
            $tools cmake --preset "$2" -DCMAKE_MAKE_PROGRAM="$ninja"
        fi
        $tools cmake --build "$1" --target "$3"
    ' sh "$tree" "$preset" "$target"
    echo "built $target in $((SECONDS - start))s"
    echo "binary: $binary"
fi

((run)) || exit 0

if [[ ! -x $binary ]]; then
    echo "no binary at $binary; run without --no-build first" >&2
    exit 1
fi

# Trailing slashes are dropped so path building below stays uniform; "/" needs no suffix.
while [[ $userdir == */ && $userdir != / ]]; do userdir=${userdir%/}; done
userdir_prefix=${userdir%/}

world_dir=$userdir_prefix/save/$world
character=
for save in "$world_dir"/*.sav; do
    [[ -f $save ]] || continue
    character=$save
    break
done

args=(--basepath ./ --userdir "$userdir")
if [[ ! -d $world_dir ]]; then
    echo "no world '$world' in $userdir_prefix/save/: create a world and a character from the"
    echo "main menu, then rerun to load it directly"
elif [[ ! -f $world_dir/worldoptions.json && ! -f $world_dir/master.gsav ]]; then
    echo "$world_dir is not a world: it has no worldoptions.json or master.gsav; open the main menu"
elif [[ -z $character ]]; then
    echo "world '$world' has no character: the game would quit at once; open the main menu, add a"
    echo "character to it, then rerun to load it directly"
else
    args+=(--world "$world")
fi

mkdir -p "$userdir"
exec flock --shared "$lock" "$binary" "${args[@]}" "$@"
