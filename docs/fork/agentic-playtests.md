# Agentic playtests

An agentic playtest puts a decision model in front of the game and lets it play. The model reads
the screen (and, on the tiles build, a frame), picks one action from a typed list, sends it, and
writes down what it saw. Nobody scripts a key sequence: the model chooses its own path through the
scenario, and the run ends with a report of what it found, per turn, with the cost.

This is fork issue #6. It sits next to the deterministic end-to-end suite, it does not replace it:
the suite proves a feature works, the playtest reports what a player meets.

## How one run works

| Step | Who                           | What                                                                          |
| ---- | ----------------------------- | ----------------------------------------------------------------------------- |
| 1    | `tests/e2e/playtest.py`       | `start_scenario()` starts a fresh private world and builds the scenario       |
| 2    | `tests/e2e/agent_state.py`    | `dump_state()` reads the screen and offers the actions `actions_for()` allows |
| 3    | `tests/e2e/agent_models.py`   | `Gateway.decide()` asks a model to choose one action id                       |
| 4    | `tests/e2e/agent_state.py`    | the chosen keys or click go to the game                                       |
| 5    | `tests/e2e/agent_playtest.py` | one transcript line per turn, plus frames and the report                      |

The state comes from the game itself where it can: in curses mode `dump_state` reads the screen and
the Lua console, so item counts and effects are exact rather than guessed from glyphs.

## The matrix

Two axes. The input surface is how the playtester reaches the game; the render surface is what it
looks at. The four combinations the fork asked for, in the same words:

| Combination | Input surface      | Render surface   | Implied scheme    | Harness                                          |
| ----------- | ------------------ | ---------------- | ----------------- | ------------------------------------------------ |
| KB          | keyboard only      | curses           | classic           | `--mode curses --scheme classic --input kb`      |
| KB + mouse  | keyboard and mouse | curses           | modern            | `--mode curses --scheme modern --input kb-mouse` |
| curses only | keyboard only      | curses           | modern or classic | `--mode curses`                                  |
| tileset     | keyboard and mouse | tiles under Xvfb | modern            | `--mode tiles --scheme modern --input kb-mouse`  |

Input and render are independent choices, and the driver takes `--mode`, `--scheme` and `--input`
separately, so a leg can mix them. KB means the classic control scheme played with the keyboard
only; KB + mouse means the modern scheme with the mouse.

Co-op has no playtest leg today, because the fork has no multiplayer behaviour yet: `OVERHAUL.md`
line 625 lists "Simple seamless co-op" as future work to evaluate before choosing an implementation,
and says no multiplayer behaviour is enabled; `CHANGELOG-OVERHAUL.md` line 206 repeats it as
future-work ticket #2. The matrix takes a co-op leg the day that lands. The only `co-op` text in the
tree today is `TOGGLE_SCOOP`, the vehicle scoop.

Content scenarios, all listed by `python3 tests/e2e/playtest.py --list`:

| Scenario           | Content                           | Starts                     | Notes                                                                                    |
| ------------------ | --------------------------------- | -------------------------- | ---------------------------------------------------------------------------------------- |
| `main_menu`        | Main menu navigation              | title screen               | Every tab and submenu; no world, so curses only                                          |
| `tutorial`         | The built-in tutorial             | tutorial room              | Follows the lesson popups; curses only                                                   |
| `natural_gameplay` | Natural gameplay                  | fresh world                | No scripted setup at all: the game as a player meets it                                  |
| `fork_features`    | A custom fork-feature map         | fresh world with Lua setup | Quick stack, sort pile, item variants, stack modifiers, the body panel, weather, the hub |
| `quick_stack`      | Quick stack fixture               | in game                    | Existing feature fixtures also work with the driver                                      |
| `sort_pile`        | Sort pile fixture                 | in game                    |                                                                                          |
| `folded_items`     | Item variants and stack modifiers | in game                    |                                                                                          |
| `hud`              | HUD, sidebar and body panel       | in game                    |                                                                                          |

## Which model plays what

`--models` takes a pool name or a comma-separated list of model ids.

| Pool     | Models, in order                                                                                                                                          | For                                       |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `text`   | `clef-flash`, `jev-latest`, `jev-1.13-free`, `deepseek-v4.1-flash-free`, `glm-5.3-flash-free`                                                             | Curses surfaces, where the state is text  |
| `vision` | `gpt-6-luna-decisions`, `deepseek-v4.1-flash-1017`, `clef`, `clef-flash`, `jev-latest`, `jev-1.13-free`, `deepseek-v4.1-flash-free`, `glm-5.3-flash-free` | Tiles surfaces, where a frame image helps |
| `openrouter-text`   | `nvidia/nemotron-3-ultra-550b-a55b:free`, `poolside/laguna-xs-2.1:free`, `openrouter/free`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`, `liquid/lfm-2.5-2.6b:free` | Curses surfaces with only `OPENROUTER_API_KEY` |
| `openrouter-vision` | `dots-studio/dots-3-note-preview:free`, `openrouter/free`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | Tiles surfaces with only `OPENROUTER_API_KEY` |

The pools only hand out models that are usable on the day: a model whose free window has passed is
dropped from the pool before the run starts.

| Model                      | Surface    | Text | Image | Notes                                              |
| -------------------------- | ---------- | ---- | ----- | -------------------------------------------------- |
| `clef-flash`               | System One | yes  | no    | Free without a card                                |
| `clef`                     | System One | yes  | yes   | Free without a card                                |
| `jev-latest`               | System One | yes  | no    | 32,000 tokens shared by state and questions        |
| `gpt-6-luna-decisions`     | Decisions  | yes  | yes   | Billed on input tokens only; free until 2026-11-14 |
| `deepseek-v4.1-flash-1017` | Chat       | yes  | yes   | 3.75M in and 750k out per day                      |
| `jev-1.13-free`            | System One | yes  | no    | OpenCode publishes no context size                 |
| `deepseek-v4.1-flash-free` | Chat       | yes  | no    | OpenCode publishes no context size                 |
| `glm-5.3-flash-free`       | Chat       | yes  | no    | OpenCode publishes no context size                 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | Chat | yes | no | OpenRouter, free; verified 2026-10-21 |
| `poolside/laguna-xs-2.1:free` | Chat | yes | no | OpenRouter, free; fast, small model |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | Chat | yes | yes | OpenRouter, free; shared upstream capacity |
| `liquid/lfm-2.5-2.6b:free` | Chat | yes | no | OpenRouter, free; slow last resort |
| `dots-studio/dots-3-note-preview:free` | Chat | yes | yes | OpenRouter, free; needs the image to stay on task |
| `openrouter/free`          | Chat       | yes  | yes   | OpenRouter's router over its free tier             |

The `openrouter-*` ids come from `GET https://openrouter.ai/api/v1/models` on 2026-10-21: the 21
rows priced at zero. Only the ids that answered the harness's JSON-action prompt in a local probe
are listed. The free models this account's data policy refuses (`nemotron-3.5-super-vl`,
`minimax-m3.1-flash`, `flint`) and the gemma rows that were upstream-429 at the time are left out.

A model that runs out of free tier is retired for the rest of the run and the next one in the pool
takes over. The gateway never bills past a free tier, so a spent pool ends the run instead.

## OpenRouter

OpenRouter is the third chat surface: OpenAI-compatible, at
`https://openrouter.ai/api/v1/chat/completions`, reached with one key, `OPENROUTER_API_KEY`, for
every model in the `openrouter-text` and `openrouter-vision` pools. The harness sends the optional
`HTTP-Referer` and `X-Title` attribution headers and treats an error object inside an HTTP 200
reply as a failed attempt, because OpenRouter reports upstream failures that way.

Every pooled model is a `:free` one, so a turn costs $0. OpenRouter still returns usage (prompt
and completion tokens) in the reply, so the report counts those decisions as measured at $0. A
free model that reports a price in the catalog is still billed as free by the gateway, which
never dials a paid lane.

A local key can stay out of the shell history: put `OPENROUTER_API_KEY=...` in a `KEY=VALUE` file
and name the file with `OPENROUTER_ENV_FILE`. The harness reads it the first time it needs a key,
once, never echoes a value, and an exported variable always wins over the file.

```sh
export OPENROUTER_ENV_FILE=~/.config/free-pool/env      # a KEY=VALUE file, mode 600
python3 tests/e2e/agent_models.py --check-keys          # per-pool readiness, no network
python3 tests/e2e/agent_playtest.py --scenario fork_features --mode curses --scheme modern \
        --input kb --models openrouter-text --turns 10 --budget-usd 1 \
        --report-dir /tmp/playtest-openrouter
```

In CI the same key is the repository secret `OPENROUTER_API_KEY`. When it is the only model
secret, the plan job points every live leg at the matching pool: `openrouter-text` for the two
curses legs, `openrouter-vision` for the two tiles legs. When `XPL_SK_AGENT` and `OC_SK_AGENT`
are also set, the legs keep their `text` and `vision` defaults unless a dispatch passes `models`.
Without any key the legs stay dry, as before.

Free models come and go. When the pool starts retiring ids (a 404 for a withdrawn free endpoint, a
429 from an upstream provider), refresh them from `GET https://openrouter.ai/api/v1/models` and
update the dated comment on the registry entries. A `:free` model this account's data policy
refuses is not pooled, even though the catalog lists it.

## Console requirements for the free tiers

Verified 2026-10-17.

| Model                      | Requirement for the free daily tier                                           |
| -------------------------- | ----------------------------------------------------------------------------- |
| `clef`, `clef-flash`       | Free, no card on file                                                         |
| `jev-latest`               | A saved card and one settled charge of $1 or more                             |
| `gpt-6-luna-decisions`     | A saved card and one settled charge of $1 or more; free only until 2026-11-14 |
| `deepseek-v4.1-flash-1017` | A saved card and one settled charge of $1 or more                             |

Keep **credits overflow off** at the org, so a spent free tier fails the call instead of billing the
card. With overflow on, a run that has used up its free tokens quietly starts spending.

## Run one locally

Export the keys by hand, or point the harness at a `KEY=VALUE` file with `OPENROUTER_ENV_FILE` so
the value never reaches a command line. The repository secret `OPENROUTER_API_KEY` is set on
`Kenja-mc/Cataclysm-BN`, so a nightly run or a dispatch plays live from the OpenRouter pools;
`XPL_SK_AGENT` and `OC_SK_AGENT` are not set there, so the `text` and `vision` pools need a local
key until they are added under **Settings → Secrets and variables → Actions**.

```sh
export XPL_SK_AGENT=...    # api.experientiallabs.ai: clef, clef-flash, jev-latest, gpt-6-luna-decisions
export OC_SK_AGENT=...     # opencode.ai: jev-1.13-free, deepseek-v4.1-flash-free, glm-5.3-flash-free
export OPENROUTER_ENV_FILE=~/.config/free-pool/env   # openrouter.ai: the openrouter-* pools
```

Check the wiring first. This needs no key, opens no socket and spends nothing:

```sh
python3 tests/e2e/agent_playtest.py --scenario stances --dry-run --turns 3 \
        --report-dir /tmp/playtest-dry
```

Then a real run. Keyboard only, classic scheme, the free text pool, ten turns:

```sh
python3 tests/e2e/agent_playtest.py --scenario fork_features --mode curses --scheme modern \
        --input kb --models text --turns 10 --seed 7 \
        --report-dir /tmp/playtest-fork --budget-usd 1
```

The same scenario on the tiles build, where the model also sees a frame:

```sh
python3 tests/e2e/agent_playtest.py --scenario fork_features --mode tiles --scheme modern \
        --input kb-mouse --models vision --turns 10 --report-dir /tmp/playtest-tiles
```

The tiles build needs Xvfb and the software Vulkan driver, the same setup `tests/e2e/tiles.py`
documents, and it starts on a private display numbered :100 or higher, never your desktop.

To watch a scenario yourself instead of handing it to a model:

```sh
python3 tests/e2e/playtest.py --list
python3 tests/e2e/playtest.py fork_features           # attach and play it
python3 tests/e2e/playtest.py main_menu --no-attach   # print the screen and close
```

Caps are kill switches, not budgets to spend: `--budget-usd`, `--max-wall-s` and `--max-tokens`
stop the run and it then cannot report success.

## What the run leaves behind

`--report-dir` gets:

| File               | Contents                                                                                |
| ------------------ | --------------------------------------------------------------------------------------- |
| `transcript.jsonl` | One line per turn: turn, screen, menu, action, model, tokens, usd, measured, confidence |
| `summary.md`       | Result, the defects with their turn numbers, the cost line and the models used          |
| `frames/*.png`     | The frames the model was shown, in tiles mode                                           |

Exit codes tell a reader what happened:

| Code | Meaning                       |
| ---- | ----------------------------- |
| 0    | Clean run, no defect reported |
| 1    | A defect was reported         |
| 2    | Harness error                 |
| 3    | A cap stopped the run         |

## What CI runs

`.github/workflows/fork-playtest.yml` runs nightly and on manual dispatch, not on pushes or
pull requests. A manual run independently selects `run_e2e`, `run_agentic` and
`run_screenshots`; all three default on because dispatching this workflow is an explicit opt-in.
The nightly schedule still runs all three. To request only the end-to-end suite:

```sh
gh-fork workflow run fork-playtest.yml --repo Kenja-mc/Cataclysm-BN --ref main \
  -F run_e2e=true -F run_agentic=false -F run_screenshots=false
```

The suite lives in reusable `fork-e2e.yml`. Releases expose it as the default-off
`run_playtests` checkbox; when selected, it must pass before publication. Builds and Windows
updater checks remain mandatory. The cross-platform `matrix` workflow remains weekly and manual.
Nightly tiles jobs reuse a matching package when available, or build their own binary.

Four legs, each with its own content list (main menu and tutorial have no tiles surface, so both
tiles legs walk two scenarios):

| Leg                      | Mode   | Scheme  | Input    | Pool     | Content                                                      |
| ------------------------ | ------ | ------- | -------- | -------- | ------------------------------------------------------------ |
| `kb-classic-curses`      | curses | classic | kb       | `text`   | `main_menu`, `tutorial`, `natural_gameplay`, `fork_features` |
| `kb-mouse-modern-curses` | curses | modern  | kb-mouse | `text`   | `main_menu`, `tutorial`, `natural_gameplay`, `fork_features` |
| `kb-classic-tiles`       | tiles  | classic | kb       | `vision` | `natural_gameplay`, `fork_features`                          |
| `kb-mouse-modern-tiles`  | tiles  | modern  | kb-mouse | `vision` | `natural_gameplay`, `fork_features`                          |

Per run: 30 turns, a 15 minute wall clock and $2. The agents run standard GitHub-hosted runners,
free for public repositories, so only tokens cost money.

Each leg ends in one of four verdicts:

| Verdict         | Exit code | Effect                                                                                                             |
| --------------- | --------- | ------------------------------------------------------------------------------------------------------------------ |
| `clean`         | 0         | The run finished with no defect                                                                                    |
| `defect`        | 1         | A defect was reported. The leg does not fail; the nightly triage opens one issue for it                            |
| `killed`        | 3         | A cap (dollars, wall clock or tokens) stopped a run. The leg does not fail, and a capped run cannot report success |
| `harness-error` | 2         | The harness itself failed. This is the one verdict that fails the job                                              |

Without a usable model secret the workflow does not play live at all: it keeps only the first
matching leg (`kb-classic-curses` by default), makes it a dry run with 3 turns, and says so in the
job summary. A live leg needs one of `OPENROUTER_API_KEY` (on its own) or the pair
`XPL_SK_AGENT` + `OC_SK_AGENT`. When only the OpenRouter key exists, the plan retargets every leg
at the free pools: `openrouter-text` for curses, `openrouter-vision` for tiles. Dispatch filters
still apply, so a tiles-only request checks a tiles leg. End-to-end tests and screenshots are
independent of model-key availability and run only when their manual option or the schedule selects them.

The end-to-end suite runs as four parallel shards. A single runner could not finish the full suite
inside the job's two-hour timeout: the tail of the suite is slower on two cores than it is locally,
and the job was cancelled with the suite still running. Each shard builds the same cache-warm curses
binary and runs a balanced quarter of the checks (`--shard=0/4`), and uploads its own log as
`e2e-suite-log-<shard>`. `run.py` assigns the tests longest first into the lightest shard, using the
per-test seconds in `tests/e2e/durations.json`; positional slicing put the three mouse tests in one
shard and made it 47% longer than its neighbours. A local run is parallel by default;
`--serial` keeps it in one process. `--durations=<path>` writes timings to the requested file; use
`--durations=tests/e2e/durations.json` on a successful full, unfiltered run to refresh the manifest.
Do not use a single `--shard` to refresh it: that records only that shard's tests.
Rerun the suite afterward to verify the changed shard assignments.

`python3 tests/e2e/feature_shots.py` runs on the nightly schedule or when `run_screenshots` is selected.
It uploads `docs/fork/images/features/*.png` as an artifact and never commits them. Note the trap: `--only`
rewrites the feature page with just the shots it captured, so leave it off when regenerating the
whole set.

## Key-guess survey

`tests/e2e/keyguess.py` asks a decision model which key it would press, without teaching it the
layout. Each scenario opens a real screen of the modern scheme with the sidebar Controls panel off
and the popups disabled, states a goal (open the map, wield the pipe), and offers six keys or key
sequences. The harness then presses the chosen keys on a fresh game and checks the goal through
the game state, so every answer is scored as reached, first step or missed.

```sh
python3 tests/e2e/keyguess.py --validate                       # which offered keys reach each goal
XPL_SK_AGENT=... python3 tests/e2e/keyguess.py --models jev-latest,gpt-6-luna-decisions \
    --trials 3 --out /tmp/keyguess
```

Run `--validate` after changing a scenario: a goal no offered key reaches is a trap, not a
question. Each trial starts its own game (about ten seconds) because a closed menu can leave its
text on the pane and a pressed key can change the world. A model error is recorded as an error
row and the survey continues. Results are `results.jsonl` and `summary.md` in `--out`. The
harness is research tooling, not part of the suite; survey results and keymap proposals live on
the `research/controls` branch.

## Limits worth knowing

- The driver plays what it can see. A scenario that hides the feature behind a menu needs turns to
  open that menu, so give those runs more `--turns`.
- `main_menu` and `tutorial` start at the title screen and in the tutorial room, so the tiles mode
  refuses them: the tiles build can only reopen a saved world.
- A run is not a pass or fail per check line. The report says what the model met; the deterministic
  suite stays the gate.
- Known quirk: the harness wakes the map with the wait key before handing it over, and in the classic
  scheme that key is Look Around, so a classic run starts with that panel open (Escape closes it).
- The tiles harness shells out to ImageMagick for capture and pixels. ImageMagick 7 provides the
  `magick` shim and ImageMagick 6 the `import`, `identify` and `convert` binaries; `tiles.py` picks
  whichever is installed, because the GitHub runners carry 6 and development machines usually 7.
