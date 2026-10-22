#!/usr/bin/env python3
"""Key-guessing survey: a decision model sees a screen without control hints and names the key.

    python3 tests/e2e/keyguess.py --models jev-latest --out /tmp/keyguess
    python3 tests/e2e/keyguess.py --models jev-latest,gpt-6-luna-decisions --trials 2 --out /tmp/keyguess
    python3 tests/e2e/keyguess.py --validate          # which offered keys actually reach each goal

Each scenario puts the game on a screen where a goal is reachable, states the goal, and asks the
model which key it would press, offering the same closed list to every model. The harness then
presses the chosen key on a *fresh game* and records whether the goal was reached, so the answers
can be scored instead of taken on trust.

A fresh game per trial costs about ten seconds and removes the whole class of stale-window
artifacts: a closed menu can leave its text on the pane, an open menu blocks the Lua console, and
a key that changed the world (wielded a pipe) would otherwise score the next key as a success.

The sidebar Controls panel is switched off and the welcome and tip popups are disabled, so the
screen carries no key hints. Screens still carry their own labels; the harness records whether any
hint text survived and never edits the capture.

Output: results.jsonl (one line per model and trial) and summary.md. This is a research tool, not
a test: it needs a model key and is not part of the suite.
"""
import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agent_models import (  # noqa: E402
    Gateway, MissingKey, NoModelAvailable, load_env_file,
)
from helpers import HELPERS, arena, bub_pos, empty_inventory, give  # noqa: E402
from tmux_game import Game, start_new_game  # noqa: E402

SIDEBAR_HINTS = ("wasd move", "qezc diag", "all keys", "RETURN menus", "CTRL+W peek",
                 "WASD look", "spc interact")

PANELS = ("Needs", "Movement", "Location", "Weapon", "Controls", "Log", "Compass", "Moon",
          "Vehicle", "Environment", "Sound", "Stats", "Stamina", "Health")


def keyguess_userdir():
    """A private config directory with the Controls panel off."""
    userdir = Path(tempfile.mkdtemp(prefix="bn-keyguess-"))
    config = userdir / "config"
    config.mkdir()
    (config / "panel_options.json").write_text(json.dumps([{
        "current_layout_id": "labels",
        "layouts": [{"layout_id": "labels", "panels": [
            {"name": name, "toggle": name != "Controls"} for name in PANELS
        ]}],
    }]))
    return userdir


def new_game():
    game = Game(name="bn-keyguess", userdir=keyguess_userdir(), options={
        "SAFEMODE": "false", "SHOW_WELCOME": "false", "SHOW_TIPS": "false",
        "CONTROL_SCHEME": "modern", "ANIMATIONS": "false", "NO_UNKNOWN_COMMAND_MSG": "false",
    })
    start_new_game(game)
    game.define_lua(HELPERS)
    return game


def screen_text(game):
    """The visible screen with the hint survey recorded, never rewritten."""
    text = game.screen()
    return text, [hint for hint in SIDEBAR_HINTS if hint in text.lower()]


# --------------------------------------------------------------------------- probes

def before_nothing(_game):
    return None


def clock(game):
    """Turns plus spent moves: one pause is one move, and a turn only ticks every 100."""
    turn, moves = game.lua("out(gapi.current_turn():to_turn()) "
                           "out(-gapi.get_avatar():get_moves())")
    return int(turn), int(moves)


def before_wait(game):
    return {"pos": bub_pos(game), "clock": clock(game)}


def wielded(game):
    """The wielded item from the sidebar; the Lua console cannot open under a menu."""
    found = re.search(r"Weapon\s*\|\s*(\S.*?)\s*(?:│|$)", game.screen(), re.M)
    return found.group(1).strip() if found else "none"


def probe_inventory(game, _before):
    """The item list itself: its header counts assigned hotkeys, which no other screen shows."""
    return "Item hotkeys assigned" in game.screen(), "inventory list"


def probe_map(game, _before):
    screen = game.screen()
    return re.search(r"LEVEL \(?-?\d+", screen) is not None or "Level " in screen, "map screen"


def probe_wait(game, before):
    now = clock(game)
    moved = bub_pos(game) != before["pos"]
    return now != before["clock"] and not moved, \
        f"position {'moved' if moved else 'held'}, clock {before['clock']} -> {now}"


def probe_hub(game, _before):
    return "Actions" in game.screen(), "action hub"


def probe_craft(game, _before):
    """The recipe list, not the hub entry that is also called Craft: it names missing parts."""
    screen = game.screen()
    return "craftable" in screen or "Missing:" in screen, "recipe list"


def partial_craft_category(game):
    """The Craft page of the Actions menu: the right first step of a two-step path."""
    return "Actions: Craft" in game.screen()


def probe_wield(game, _before):
    item = wielded(game)
    return item.lower() not in ("fists", "none"), f"wielded item: {item}"


def probe_armor(game, _before):
    """The item menu beside the helmet, where its protection table appears."""
    screen = game.screen()
    return "Activate" in screen and ("Protection" in screen or "Bash" in screen), "item menu"


# --------------------------------------------------------------------------- scenarios
# Each scenario: setup runs on a fresh game, open_keys reach the screen, goal is what the model
# reads, candidates map a stable id to (description, key sequence), and probe proves the goal.
SCENARIOS = {
    "inventory": {
        "setup": lambda g: (empty_inventory(g), give(g, "pipe")),
        "open_keys": [],
        "goal": "Open your inventory to see what you carry.",
        "candidates": {
            "i": ("press i", ["i"]), "b": ("press b", ["b"]), "Tab": ("press Tab", ["Tab"]),
            "u": ("press u", ["u"]), "g": ("press g", ["g"]), "Enter": ("press Enter", ["Enter"]),
        },
        "probe": probe_inventory, "before": before_nothing,
    },
    "map": {
        "setup": lambda g: arena(g),
        "open_keys": [],
        "goal": "Open the world map.",
        "candidates": {
            "m": ("press m", ["m"]), "Tab": ("press Tab", ["Tab"]), "v": ("press v", ["v"]),
            "l": ("press l", ["l"]), "M": ("press M", ["M"]), "o": ("press o", ["o"]),
        },
        "probe": probe_map, "before": before_nothing,
    },
    "wait": {
        "setup": lambda g: arena(g),
        "open_keys": [],
        "goal": "Stand still and let one turn pass without moving.",
        "candidates": {
            "x": ("press x", ["x"]), ".": ("press .", ["."]), "Space": ("press Space", ["Space"]),
            "5": ("press 5", ["5"]), "Esc": ("press Esc", ["Esc"]), "w": ("press w", ["w"]),
        },
        "probe": probe_wait, "before": before_wait,
    },
    "hub": {
        "setup": lambda g: arena(g),
        "open_keys": [],
        "goal": "Open the menu that lists the actions you can take right now.",
        "candidates": {
            "Enter": ("press Enter", ["Enter"]), "a": ("press a", ["a"]),
            "Tab": ("press Tab", ["Tab"]), "Space": ("press Space", ["Space"]),
            "?": ("press ?", ["?"]), "m": ("press m", ["m"]),
        },
        "probe": probe_hub, "before": before_nothing,
    },
    "hub_craft": {
        "setup": lambda g: (arena(g), empty_inventory(g)),
        "open_keys": ["Enter"],
        "goal": "The Actions menu is open. Open crafting.",
        "candidates": {
            "6": ("press 6", ["6"]), "6_enter": ("press 6, then Enter", ["6", "Enter"]),
            "5": ("press 5", ["5"]), "&": ("press &", ["&"]), "c": ("press c", ["c"]),
            "Enter": ("press Enter", ["Enter"]),
        },
        "probe": probe_craft, "before": before_nothing, "partial": partial_craft_category,
    },
    "wield": {
        "setup": lambda g: (empty_inventory(g), give(g, "pipe")),
        "open_keys": ["i"],
        "goal": "The inventory list is open with a pipe in it. Wield the pipe.",
        "candidates": {
            "h": ("press h", ["h"]), "w": ("press w", ["w"]), "Enter": ("press Enter", ["Enter"]),
            "u": ("press u", ["u"]), "e": ("press e", ["e"]),
            "enter_h": ("press Enter, then h", ["Enter", "h"]),
        },
        "probe": probe_wield, "before": before_nothing, "close_before_probe": True,
    },
    "inspect_armor": {
        "setup": lambda g: (empty_inventory(g), give(g, "helmet_army")),
        "open_keys": ["i"],
        "goal": "The inventory list is open with an army helmet in it. Open the item's menu to "
                "inspect its protection values.",
        "candidates": {
            "Enter": ("press Enter", ["Enter"]), "v": ("press v", ["v"]),
            "i": ("press i", ["i"]), "e": ("press e", ["e"]),
            "Enter_Enter": ("press Enter, then Enter", ["Enter", "Enter"]),
        },
        "probe": probe_armor, "before": before_nothing,
    },
}


def run_trial(scenario, keys):
    """One trial on a fresh game: open the screen, (decide,) press, probe, close.

    Returns (screen, hints, chosen_id or None, reached, evidence, before_screen).
    """
    game = new_game()
    try:
        scenario["setup"](game)
        for key in scenario["open_keys"]:
            game.keys(key, delay=1.0)
        screen, hints = screen_text(game)
        before = scenario["before"](game)
        for key in keys:
            game.keys(key, delay=1.0)
        if scenario.get("close_before_probe"):
            for _ in range(3):
                if "Item hotkeys assigned" not in game.screen() and "Activate" not in game.screen():
                    break
                game.keys("Escape", delay=0.6)
        reached, evidence = scenario["probe"](game, before)
        return screen, hints, reached, evidence
    finally:
        game.close()


def survey(scenario_id, scenario, model, trials, results_path, dry_run):
    gateway = Gateway(models=[model], dry_run=dry_run)
    rows = []
    for _trial in range(trials):
        game = new_game()
        try:
            scenario["setup"](game)
            for key in scenario["open_keys"]:
                game.keys(key, delay=1.0)
            screen, hints = screen_text(game)
            state = STATE_TEMPLATE.format(goal=scenario["goal"], screen=screen)
            choices = {label: description
                       for label, (description, _keys) in scenario["candidates"].items()}
            try:
                decision = gateway.decide(state_text=state, state_image=None,
                                          question="Which key do you press?", choices=choices)
            except (MissingKey, NoModelAvailable) as error:
                row = {"scenario": scenario_id, "model": model, "error": str(error)}
                with results_path.open("a") as fh:
                    fh.write(json.dumps(row) + "\n")
                print(f"{scenario_id:14} {model:28} -> error: {error}")
                # A fresh gateway per trial: a retired model would stay retired otherwise.
                gateway = Gateway(models=[model], dry_run=dry_run)
                continue
            before = scenario["before"](game)
            for key in scenario["candidates"][decision.action_id][1]:
                game.keys(key, delay=1.0)
            if scenario.get("close_before_probe"):
                for _ in range(3):
                    if "Item hotkeys assigned" not in game.screen() \
                            and "Activate" not in game.screen():
                        break
                    game.keys("Escape", delay=0.6)
            reached, evidence = scenario["probe"](game, before)
            partial = (not reached and "partial" in scenario and scenario["partial"](game))
        finally:
            game.close()
        row = {"scenario": scenario_id, "goal": scenario["goal"], "screen": screen,
               "hints_visible": hints, "model": decision.model, "key": decision.action_id,
               "confidence": decision.confidence, "reached": reached, "partial": partial,
               "evidence": evidence}
        rows.append(row)
        with results_path.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        outcome = "reached" if reached else "first step" if partial else "missed"
        print(f"{scenario_id:14} {decision.model:28} -> {decision.action_id:12} "
              f"({outcome}) {evidence}")
    return rows


STATE_TEMPLATE = """You are playing Cataclysm: Bright Nights, a turn-based survival roguelike.
The keyboard layout was never taught to you and the game shows no key hints.

GOAL: {goal}

The screen in front of you reads:

{screen}

Which key or key sequence do you press?"""


def validate(scenario_id, scenario):
    reached = []
    for label, (_description, keys) in scenario["candidates"].items():
        _screen, _hints, ok, evidence = run_trial(scenario, keys)
        if ok:
            reached.append(label)
        print(f"  {label:12} {'reached' if ok else 'no':8} {evidence}")
    print(f"{scenario_id}: reachable by {', '.join(reached) if reached else 'NO KEY'}")
    return reached


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--models", default="jev-latest",
                        help="comma-separated gateway model ids (see agent_models.REGISTRY)")
    parser.add_argument("--scenarios", nargs="*", default=None,
                        help=f"scenario ids (default: all): {', '.join(SCENARIOS)}")
    parser.add_argument("--out", default="/tmp/bn-keyguess", help="report directory")
    parser.add_argument("--dry-run", action="store_true", help="no key, no network")
    parser.add_argument("--env-file", default=None, help="KEY=VALUE file for the model keys")
    parser.add_argument("--trials", type=int, default=1,
                        help="answers per model and scenario, to spread a stochastic model")
    parser.add_argument("--validate", action="store_true",
                        help="press every offered key and report which reach each goal")
    args = parser.parse_args()

    load_env_file(args.env_file)
    names = args.scenarios or list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        parser.error(f"unknown scenario {unknown[0]}; choose from {', '.join(SCENARIOS)}")

    if args.validate:
        for name in names:
            print(f"== {name}")
            validate(name, SCENARIOS[name])
        return

    models = [m for m in args.models.split(",") if m]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    if results_path.exists():
        results_path.unlink()

    rows = []
    for name in names:
        for model in models:
            survey(name, SCENARIOS[name], model, args.trials, results_path, args.dry_run)
    # The jsonl holds every row, error rows included, in the order they happened.
    rows = [json.loads(line) for line in results_path.read_text().splitlines() if line]

    lines = ["# Key-guess survey", "",
             f"Models: {', '.join(models)}. Trials per model and scenario: {args.trials}.", "",
             "| Scenario | Model | Key | Confidence | Result | Evidence |",
             "|---|---|---|---|---|---|"]
    answered = [row for row in rows if "error" not in row]
    for row in rows:
        if "error" in row:
            lines.append(f"| {row['scenario']} | {row['model']} | - | - | error | {row['error']} |")
            continue
        result = "reached" if row["reached"] else "first step" if row.get("partial") else "missed"
        lines.append(f"| {row['scenario']} | {row['model']} | `{row['key']}` | "
                     f"{row['confidence']:.2f} | {result} | {row['evidence']} |")
    hits = sum(1 for row in answered if row["reached"])
    lines += ["", f"Goals reached: {hits}/{len(answered)} answered; "
                  f"{len(rows) - len(answered)} model errors."]
    hints = sorted({h for row in answered for h in row["hints_visible"]})
    lines += [f"Hint text visible in captures: {', '.join(hints) if hints else 'none'}."]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"\nwrote {results_path} and {out_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
