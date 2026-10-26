#!/usr/bin/env bash
# Asks a running hot-reload build (bin/dev-iterate.sh --hot) to patch in the C++ edited since it
# started or last reloaded.  Bind it to an editor key.  The game applies it at the next key press
# (tiles: also on a mouse move) and reports the outcome in the message log; details go to debug.log.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if ! pkill -USR1 -f "^$repo/out/build/linux-(curses|tiles)-hotreload/src/cataclysm-bn"; then
    echo "no hot-reload game is running; start one with bin/dev-iterate.sh --hot" >&2
    exit 1
fi
