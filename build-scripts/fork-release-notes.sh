#!/usr/bin/env bash
# Print the release notes for a fork release from CHANGELOG-OVERHAUL.md.
#
# Usage: build-scripts/fork-release-notes.sh <changelog> [since-date]
#
# Prints every dated section ("## YYYY-MM-DD") on or after since-date (YYYY-MM-DD, normally the
# day the previous release was published). Including that day avoids losing same-day fixes.
# Without since-date, or when no section is newer, prints the newest dated section only.
set -euo pipefail

changelog=${1:?usage: fork-release-notes.sh <changelog> [since-date]}
since=${2:-}

if [ -n "$since" ] && ! [[ "$since" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
	echo "since-date must be YYYY-MM-DD, got: $since" >&2
	exit 1
fi

extract() {
	awk -v since="$1" '
		/^## / {
			if ($2 ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) {
				n++
				include = (since == "") ? (n == 1) : ($2 "" >= since "")
			} else {
				include = 0
			}
		}
		include { print }
	' "$changelog"
}

notes=$(extract "$since")
if [ -z "$notes" ]; then
	notes=$(extract "")
fi
if [ -z "$notes" ]; then
	echo "no dated section found in $changelog" >&2
	exit 1
fi
printf '%s\n' "$notes"
