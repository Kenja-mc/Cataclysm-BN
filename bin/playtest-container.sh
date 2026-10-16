#!/usr/bin/env bash
# Runs the fork's end-to-end tests inside an unprivileged container (bubblewrap user namespace).
#
#   bin/playtest-container.sh e2e [test-name ...]   run the curses end-to-end suite in the box
#   bin/playtest-container.sh playtest <scenario>  set up a playtest scenario and hand it to you
#   bin/playtest-container.sh shell                 interactive shell inside the box
#
# The box gets a private HOME, private /tmp and no network.  The repository is mounted read-only,
# so the game, its data and the prebuilt binary come from the host tree; only the box's own HOME
# and /tmp are writable.  Building inside the box needs root (the host lacks ccache, mold and
# astyle and sudo asks for a password), so run `cmake --build` on the host first.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
box=$(mktemp -d "${TMPDIR:-/tmp}/bn-box-XXXXXX")
home=$box/home
mkdir -p "$home"

case "${1:-}" in
    e2e) shift; set -- python3 tests/e2e/run.py "$@" ;;
    playtest) shift; set -- python3 tests/e2e/playtest.py "$@" ;;
    shell) set -- bash ;;
    *)
        sed -n '2,11p' "${BASH_SOURCE[0]}" | cut -c3-
        exit 2
        ;;
esac

exec bwrap \
    --unshare-all --die-with-parent \
    --ro-bind /usr /usr --ro-bind /etc /etc \
    --symlink usr/bin /bin --symlink usr/lib /lib \
    --symlink usr/lib64 /lib64 --symlink usr/bin /sbin \
    --proc /proc --dev /dev --tmpfs /tmp \
    --dir /home --bind "$home" "$HOME" \
    --ro-bind "$repo" "$repo" --chdir "$repo" \
    --setenv HOME "$HOME" --setenv TERM xterm-256color \
    --setenv LANG C.UTF-8 --setenv LC_ALL C.UTF-8 \
    --setenv PATH /usr/local/bin:/usr/bin --setenv PYTHONDONTWRITEBYTECODE 1 \
    -- "$@"
