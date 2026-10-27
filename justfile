set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
    @just --list

fmt *ARGS:
    build-scripts/fmt.sh {{ARGS}}

fmt-cpp *FILES:
    build-scripts/fmt.sh cpp {{FILES}}

fmt-json *FILES:
    build-scripts/fmt.sh json {{FILES}}

fmt-return *PATHS:
    build-scripts/format-trailing-return.sh {{PATHS}}

fmt-docs:
    build-scripts/fmt.sh docs

fmt-lua:
    build-scripts/fmt.sh lua

lint: lint-json lint-dialogue

lint-json:
    build-scripts/lint-json.sh

lint-dialogue:
    tools/dialogue_validator.py data/json/npcs/* data/json/npcs/*/* data/json/npcs/*/*/*

hooks-setup:
    prek install

# Download and launch a PR tiles build: just playtest [--os OS] <PR URL>.
[positional-arguments]
playtest *args:
    deno run --allow-read --allow-write --allow-run --allow-env scripts/playtest.ts "$@"

# Rebuild only the game (-O0 -g1, NDEBUG, no tests) and load the dev save: just dev [--tiles]
# [--world NAME] [--no-run]. Game arguments go through the script: bin/dev-iterate.sh -- ARGS.
[positional-arguments]
dev *args:
    bin/dev-iterate.sh "$@"

check: lint
