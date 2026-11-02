#!/usr/bin/env bash
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
