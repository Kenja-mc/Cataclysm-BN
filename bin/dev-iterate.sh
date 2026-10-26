#!/usr/bin/env bash
# Rebuilds only the game binary with an unoptimized dev preset and launches it straight into a save.
#
#   bin/dev-iterate.sh [--tiles] [--world NAME] [--userdir DIR] [--no-build] [--no-run] [-- GAME-ARGS]
#
#   --tiles       use linux-tiles-dev instead of linux-curses-dev
#   --world NAME  world to load (default: $CATA_DEV_WORLD or "dev"); loads its first character
#   --userdir DIR saves, config and logs (default: $CATA_DEV_USERDIR or out/dev-userdir/)
#   --no-build    launch the last build
#   --no-run      build only
#
# The first run of a new world opens the main menu: create a world with that name and a character,
# and every later run loads it directly.  Tests are not built; build a test preset before pushing.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
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
        --world) world=${2:?--world needs a name}; shift ;;
        --userdir) userdir=${2:?--userdir needs a path}; shift ;;
        --no-build) build=0 ;;
        --no-run) run=0 ;;
        --) shift; break ;;
        -h | --help) sed -n '2,13p' "${BASH_SOURCE[0]}" | cut -c3-; exit 0 ;;
        *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
    esac
    shift
done

tree=out/build/$preset
binary=$tree/src/$target

if ((build)); then
    mkdir -p out/build
    start=$SECONDS
    # One lock per tree: a parallel configure or build of the same tree corrupts it.
    flock "out/build/$preset.lock" sh -c '
        [ -f "$1/build.ninja" ] || cmake --preset "$2"
        cmake --build "$1" --target "$3"
    ' sh "$tree" "$preset" "$target"
    echo "built $target in $((SECONDS - start))s"
fi

((run)) || exit 0

if [[ ! -x $binary ]]; then
    echo "no binary at $binary; run without --no-build first" >&2
    exit 1
fi

userdir=${userdir%/}/
mkdir -p "$userdir"
args=(--basepath ./ --userdir "$userdir")
if [[ -d $userdir/save/$world ]]; then
    args+=(--world "$world")
else
    echo "no world '$world' in $userdir: create it from the main menu, then rerun to load it directly"
fi
exec "$binary" "${args[@]}" "$@"
