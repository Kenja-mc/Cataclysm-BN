#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agent_actions import actions_for, classify_screen  # noqa: E402
from agent_models import (  # noqa: E402
    POOLS, Gateway, MissingKey, NoModelAvailable, load_env_file, pool,
)
from agent_state import close_tiles, dump_state, send_action  # noqa: E402
from playtest import SCENARIOS, start_scenario  # noqa: E402

RESERVED_DEFECT = "report_defect"
RESERVED_DONE = "report_done"
DEFECT_LABEL = ("Report a defect: the state above shows the game failing at the scenario - a control "
                "that did nothing, a missing or wrong menu entry or message. Ends the run.")
DONE_LABEL = "Report the scenario checked: nothing left to try here. Ends the run."
DEFECT_MIN_CONFIDENCE = 0.6

SETTLE_S = {"curses": 0.6, "tiles": 1.5}
STUCK_LIMIT = 10

EXIT_CLEAN, EXIT_DEFECT, EXIT_HARNESS, EXIT_KILL = 0, 1, 2, 3
RESULT_NAMES = {EXIT_CLEAN: "clean", EXIT_DEFECT: "defect reported", EXIT_HARNESS: "harness error",
                EXIT_KILL: "budget or kill switch"}


class HarnessError(RuntimeError):
    pass


class Stop(Exception):
    def __init__(self, reason: str, code: int):
        super().__init__(reason)
        self.reason = reason
        self.code = code


def resolve_models(spec: str) -> list[str]:
    return pool(spec) if spec in POOLS else [m.strip() for m in spec.split(",") if m.strip()]


def build_gateway(args: argparse.Namespace) -> tuple[Gateway, list[str], str]:
    models = resolve_models(args.models)
    if not models:
        raise HarnessError(f"--models {args.models!r} names no model")
    if args.dry_run:
        return Gateway(models=models, dry_run=True), models, \
            f"agent_models.Gateway(dry_run=True) over {'/'.join(models)}"
    return Gateway(models=models), models, " + ".join(models)


def text_only_pool(models: list[str]) -> bool:
    vision = set(pool("vision")) | set(pool("openrouter-vision"))
    return not set(models) & vision


def model_error(exc: BaseException) -> None:
    if isinstance(exc, MissingKey):
        raise HarnessError(
            f"no API key for the model pool: {exc}\n"
            "Set OPENROUTER_API_KEY (openrouter.ai, the openrouter-* pools), XPL_SK_AGENT "
            "(api.experientiallabs.ai) or OC_SK_AGENT (opencode.ai); a local key may also live in the "
            "KEY=VALUE file named by OPENROUTER_ENV_FILE. Without a repository secret a live run cannot "
            "start; --dry-run needs no key.") from exc
    if isinstance(exc, NoModelAvailable):
        raise Stop(f"every model in the pool is exhausted: {exc}", EXIT_KILL) from exc


@dataclass
class Report:
    args: argparse.Namespace
    scenario: dict
    turns_run: int = 0
    code: int = EXIT_CLEAN
    reason: str = "turn budget reached"
    defects: list[dict] = field(default_factory=list)
    stuck: str = ""
    models: Counter = field(default_factory=Counter)
    calls: int = 0
    measured_calls: int = 0
    estimated_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    usd_measured: float = 0.0
    usd_estimated: float = 0.0
    exhausted: list[str] = field(default_factory=list)
    frames: int = 0
    wall_s: float = 0.0
    save_name: str = ""
    userdir: str = ""
    mode: str = ""
    gateway_line: str = ""
    last_state: str = ""
    notes: list[str] = field(default_factory=list)

    def cost(self) -> str:
        plural = lambda n: "decision" if n == 1 else "decisions"  # noqa: E731 - one line reads better
        total = self.usd_measured + self.usd_estimated
        line = (f"${total:.4f} total = ${self.usd_measured:.4f} measured ({self.measured_calls} "
                f"{plural(self.measured_calls)}) + ${self.usd_estimated:.4f} estimated "
                f"({self.estimated_calls} {plural(self.estimated_calls)}); {self.tokens_in} in / "
                f"{self.tokens_out} out tokens over {self.calls} {plural(self.calls)}")
        if self.estimated_calls and not self.usd_estimated:
            line += "; estimated decisions priced at zero (free models)"
        if self.args.dry_run and not self.calls:
            line += "; dry run, no model asked"
        return f"cost: {line}"


def write_summary(path: Path, report: Report) -> None:
    args, scenario = report.args, report.scenario
    lines = [
        f"# Agentic playtest - {scenario['id']}",
        "",
        f"- result: **{RESULT_NAMES[report.code]}** (exit code {report.code})",
        f"- stopped: {report.reason}",
        f"- turns recorded: {report.turns_run} of {args.turns}; wall clock {report.wall_s:.1f}s",
        f"- scenario: {scenario['id']} - {scenario['about']}",
        f"- seed: {args.seed if args.seed is not None else 'none (the game picks one)'}",
        f"- surface: {report.mode or args.mode} build, {args.scheme} scheme, "
        f"{'keyboard only' if args.input == 'kb' else 'keyboard and mouse'}",
        f"- decisions asked from: {report.gateway_line or 'none'}",
        f"- world: {report.save_name or 'none (no game was started)'} in "
        f"{report.userdir or 'none'}",
        f"- artifacts: transcript.jsonl ({report.turns_run} turns), frames/ ({report.frames} frames)",
    ]
    caps = [f"turns {args.turns}"]
    if args.max_wall_s:
        caps.append(f"wall clock {args.max_wall_s:g}s")
    if args.max_tokens:
        caps.append(f"tokens {args.max_tokens}")
    if args.budget_usd:
        caps.append(f"budget ${args.budget_usd:.4f}")
    lines += [f"- caps: {', '.join(caps)}", "", "## Models that answered"]
    if report.models:
        lines += [f"- {model}: {turns} turn{'s' if turns != 1 else ''}"
                  for model, turns in report.models.most_common()]
    else:
        lines.append("- none: no decision was recorded")
    if report.exhausted:
        lines.append(f"- retired during the run: {', '.join(dict.fromkeys(report.exhausted))}")
    lines += ["", "## Cost", "", report.cost(), ""]
    if args.dry_run:
        lines += ["Dry run: no key and no network, so this is a wiring check, not playtest evidence.",
                  f"The loop recorded {report.turns_run} turn{'s' if report.turns_run != 1 else ''} "
                  "and wrote every turn it took." if report.turns_run else
                  "The run did not reach a turn: the wiring check failed before the first state dump.",
                  ""]

    lines += ["## Defects"]
    if not report.defects:
        lines.append("")
        lines.append("None named by the model.")
    for defect in report.defects:
        lines += ["",
                  f"### Turn {defect['turn']} - {defect['model']}, confidence {defect['confidence']:.2f}",
                  "",
                  f"The model named this defect with the game in the state below (turn {defect['turn']}, "
                  f"menu {defect['menu']!r}).",
                  "",
                  "```",
                  defect["state"].rstrip(),
                  "```"]

    if report.stuck:
        lines += ["", "## Stuck detector", "", report.stuck, "", "The state that repeated:", "",
                  "```", report.last_state.rstrip(), "```"]

    if report.notes:
        lines += ["", "## Notes", ""] + [f"- {note}" for note in report.notes]
    lines.append("")
    path.write_text("\n".join(lines))


class Driver:
    def __init__(self, args: argparse.Namespace, report: Report, handle: Any, gateway: Gateway,
                 transcript: Any, frames_dir: Path):
        self.args = args
        self.report = report
        self.handle = handle
        self.gateway = gateway
        self.transcript = transcript
        self.frames_dir = frames_dir
        self.wants_image = report.mode == "tiles"
        self.start = time.monotonic()
        self.seen_states: Counter = Counter()
        self.invalid: Counter = Counter()

    def question(self, turn: int) -> str:
        args, scenario = self.args, self.report.scenario
        surface = "keyboard only" if args.input == "kb" else "keyboard and mouse"
        return (
            f"Turn {turn} of {args.turns}. You are playing Cataclysm: Bright Nights (a fork) through its "
            f"own UI: {self.report.mode} build, {args.scheme} control scheme, {surface}. "
            f"The scenario you are checking is {scenario['id']}: {scenario['about']} "
            "The state above is what the game shows right now. The choices are the complete list of "
            "inputs the harness can send from that state - anything else is ignored, so answer with "
            "exactly one choice id and nothing else. Play the scenario forward and try the feature it "
            f"names. Answer {RESERVED_DEFECT} when the state above shows the game failing at it, and "
            f"{RESERVED_DONE} when you have checked the scenario and have nothing left to try.")

    def ask(self, turn: int, state: Any, choices: dict[str, str]) -> tuple[Any, int, int]:
        question = self.question(turn)
        retries, decision = 0, None
        while decision is None:
            try:
                decision = self.gateway.decide(state_text=state.text, state_image=state.image,
                                               question=question, choices=choices, allow_estimate=True)
            except (Stop, HarnessError, KeyboardInterrupt):
                raise
            except BaseException as exc:  # noqa: BLE001 - classified, never guessed at
                model_error(exc)
                if retries >= 1:
                    raise HarnessError(f"the gateway failed twice on turn {turn}: {exc}\n"
                                       f"{traceback.format_exc()}") from exc
                retries += 1
                self.report.notes.append(f"turn {turn}: gateway raised {type(exc).__name__}, retried once")
            if decision is not None and decision.action_id not in choices:
                if retries >= 1:
                    break
                retries += 1
                self.report.notes.append(f"turn {turn}: the model answered {decision.action_id!r}, which is "
                                         f"not one of the choices")
                question += (f"\nYour previous answer {decision.action_id!r} is not one of the choices. "
                             f"Answer with exactly one of: {', '.join(choices)}.")
                decision = None
        return decision, retries, 1 + retries

    def send(self, action: Any) -> None:
        send_action(self.handle, action, mode=self.report.mode)
        time.sleep(SETTLE_S.get(self.report.mode, 1.0))

    def account(self, decision: Any, calls: int) -> None:
        report = self.report
        report.calls += calls
        report.tokens_in += decision.tokens_in
        report.tokens_out += decision.tokens_out
        report.usd_measured += decision.usd if decision.measured else 0.0
        report.usd_estimated += 0.0 if decision.measured else decision.usd
        report.measured_calls += 1 if decision.measured else 0
        report.estimated_calls += 0 if decision.measured else 1
        report.models[decision.model] += 1
        for model in decision.exhausted:
            if model not in report.exhausted:
                report.exhausted.append(model)

    def check_caps(self, turn: int) -> None:
        args, report = self.args, self.report
        if args.max_wall_s and time.monotonic() - self.start >= args.max_wall_s:
            raise Stop(f"wall clock cap of {args.max_wall_s}s reached on turn {turn}", EXIT_KILL)
        spent = report.usd_measured + report.usd_estimated
        if args.budget_usd and spent >= args.budget_usd:
            raise Stop(f"budget of ${args.budget_usd:.4f} reached (${spent:.4f} spent) on turn {turn}",
                       EXIT_KILL)
        tokens = report.tokens_in + report.tokens_out
        if args.max_tokens and tokens >= args.max_tokens:
            raise Stop(f"token cap of {args.max_tokens} reached ({tokens} tokens) on turn {turn}", EXIT_KILL)

    def line(self, turn: int, state: Any, digest: str, decision: Any, action: Any,
             retries: int, calls: int) -> dict:
        return {
            "turn": turn,
            "scenario": self.args.scenario,
            "seed": self.args.seed,
            "mode": self.report.mode,
            "scheme": self.args.scheme,
            "input": self.args.input,
            "screen": state.text,
            "menu": state.menu,
            "state_digest": digest,
            "action": decision.action_id if decision is not None else None,
            "label": action.label if action is not None else None,
            "keys": list(action.keys) if action is not None else [],
            "click": list(action.click) if action is not None and action.click else None,
            "model": decision.model if decision is not None else None,
            "tokens": (decision.tokens_in + decision.tokens_out) if decision is not None else 0,
            "tokens_in": decision.tokens_in if decision is not None else 0,
            "tokens_out": decision.tokens_out if decision is not None else 0,
            "usd": decision.usd if decision is not None else 0.0,
            "measured": bool(decision.measured) if decision is not None else False,
            "confidence": decision.confidence if decision is not None else None,
            "retries": retries,
            "calls": calls,
            "exhausted": list(decision.exhausted) if decision is not None else [],
            "frame": f"frames/turn_{turn:03d}.png" if state.image is not None else None,
            "defect": decision is not None and decision.action_id == RESERVED_DEFECT,
        }

    def turn(self, turn: int) -> None:
        args, report = self.args, self.report
        state = dump_state(self.handle, mode=report.mode, capture_image=self.wants_image)
        report.last_state = state.text
        if state.image is not None:
            (self.frames_dir / f"turn_{turn:03d}.png").write_bytes(state.image)
            report.frames += 1
        digest = hashlib.sha256(state.text.encode() + (state.image or b"")).hexdigest()[:16]
        self.seen_states[digest] += 1
        if self.seen_states[digest] >= STUCK_LIMIT:
            repeat = ("; the model also answered " + ", ".join(
                f"{action!r} {count} times, never in the action list"
                for action, count in self.invalid.most_common(3)) if self.invalid else "")
            report.stuck = (f"The state text was identical on {self.seen_states[digest]} turns (last turn "
                            f"{turn}, digest {digest}): the game never changed under the model{repeat}.")
            raise Stop(report.stuck, EXIT_KILL)

        screen = state.menu or classify_screen(state.text)
        actions = actions_for(screen, mode=report.mode, scheme=args.scheme,
                              mouse=args.input == "kb-mouse", text=state.text)
        if not actions:
            report.notes.append(f"turn {turn}: no input available in menu {state.menu!r}")
            self.record(self.line(turn, state, digest, None, None, 0, 0))
            print(f"turn {turn}: no input available in menu {state.menu!r}; nothing sent")
            self.check_caps(turn)
            return
        choices = {a.id: a.label for a in actions}
        for reserved in (RESERVED_DEFECT, RESERVED_DONE):
            if reserved in choices:
                raise HarnessError(f"the action list offers the reserved id {reserved!r} on turn {turn}")
        choices[RESERVED_DEFECT] = DEFECT_LABEL
        choices[RESERVED_DONE] = DONE_LABEL

        decision, retries, calls = self.ask(turn, state, choices)
        action = next((a for a in actions if a.id == decision.action_id), None)
        self.account(decision, calls)
        line = self.line(turn, state, digest, decision, action, retries, calls)
        parts = []
        if action is None:
            parts.append("nothing (not in the action list)")
        else:
            if action.keys:
                parts.append("keys " + "+".join(action.keys))
            if action.click is not None:
                parts.append(f"click {action.click}")
            if not parts:
                parts.append("no input")
        print(f"turn {turn}: {decision.action_id} -> {', '.join(parts)} | {decision.model} confidence "
              f"{decision.confidence:.2f} usd ${decision.usd:.4f}"
              f"{' estimated' if not decision.measured else ''}{f' ({retries} retries)' if retries else ''}")

        if decision.action_id == RESERVED_DEFECT:
            if decision.confidence < DEFECT_MIN_CONFIDENCE:
                report.notes.append(f"turn {turn}: defect claim dropped, confidence "
                                    f"{decision.confidence:.2f} below {DEFECT_MIN_CONFIDENCE:.2f}")
                self.record(line)
                self.check_caps(turn)
                return
            report.defects.append({"turn": turn, "model": decision.model,
                                   "confidence": decision.confidence, "state": state.text,
                                   "menu": state.menu})
            self.record(line)
            if args.defect_policy == "stop":
                raise Stop(f"the model named a defect on turn {turn}", EXIT_DEFECT)
            report.notes.append(f"turn {turn}: defect noted, run continues (--defect-policy note)")
            self.check_caps(turn)
            return
        if decision.action_id == RESERVED_DONE:
            self.record(line)
            raise Stop(f"the model reported the scenario checked on turn {turn}", EXIT_CLEAN)
        if action is None:
            self.invalid[decision.action_id] += 1
            self.record(line)
            if self.invalid[decision.action_id] >= STUCK_LIMIT:
                report.stuck = (f"The model answered {decision.action_id!r}, which is never in the action "
                                f"list, on {self.invalid[decision.action_id]} turns (last turn {turn}); "
                                "nothing was sent.")
                raise Stop(report.stuck, EXIT_KILL)
        else:
            self.send(action)
            self.record(line)
        self.check_caps(turn)

    def record(self, line: dict) -> None:
        self.transcript.write(json.dumps(line) + "\n")
        self.transcript.flush()
        self.report.turns_run += 1

    def run(self) -> None:
        for turn in range(1, self.args.turns + 1):
            self.check_caps(turn)
            self.turn(turn)
        self.report.reason = f"turn budget of {self.args.turns} reached"
        if self.report.defects:
            self.report.code = EXIT_DEFECT
            self.report.reason += f"; {len(self.report.defects)} defect claim(s) in the report"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Let a decision model playtest a fork scenario.",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", required=True, help="a scenario id from playtest.SCENARIOS")
    parser.add_argument("--mode", choices=["curses", "tiles"], default="curses", help="game surface")
    parser.add_argument("--scheme", choices=["modern", "classic"], default="modern")
    parser.add_argument("--input", choices=["kb", "kb-mouse"], default="kb", help="input the model may use")
    parser.add_argument("--models", default="text",
                        help='a pool (%s) or comma-separated model ids' % "|".join(sorted(POOLS)))
    parser.add_argument("--turns", type=int, default=20, help="turn budget: the normal end of a run")
    parser.add_argument("--seed", help="world seed: 1-64 letters, digits, '.', '_' or '-'")
    parser.add_argument("--report-dir", required=True, help="transcript.jsonl, summary.md and frames/")
    parser.add_argument("--budget-usd", type=float, default=None, help="kill switch on spent dollars")
    parser.add_argument("--max-wall-s", type=float, default=None, help="kill switch on wall clock")
    parser.add_argument("--max-tokens", type=int, default=None, help="kill switch on tokens in plus out")
    parser.add_argument("--defect-policy", choices=["stop", "note"], default="stop",
                        help="stop: a named defect ends the run (default); note: record it and play on")
    parser.add_argument("--dry-run", action="store_true", help="no key, no network: a wiring check only")
    args = parser.parse_args(argv)
    if args.turns < 1:
        parser.error("--turns must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env_file()
    report_dir = Path(args.report_dir)
    frames_dir = report_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "transcript.jsonl").write_text("")

    report = Report(args=args, scenario={"id": args.scenario, "about": "not a known scenario",
                                         "check": []})
    start = time.monotonic()
    handle = None
    try:
        scenarios = {s["id"]: s for s in SCENARIOS}
        if args.scenario not in scenarios:
            raise HarnessError(f"unknown scenario {args.scenario!r}; known: {', '.join(sorted(scenarios))}")
        report.scenario = scenarios[args.scenario]

        gateway, models, gateway_line = build_gateway(args)
        report.gateway_line = gateway_line
        if args.mode == "tiles" and text_only_pool(models):
            report.notes.append("the pool has no vision model, so the tiles frames only carry the state")

        with (report_dir / "transcript.jsonl").open("w") as transcript:
            handle = start_scenario(args.scenario, mode=args.mode, scheme=args.scheme, seed=args.seed)
            report.mode = handle.mode
            report.userdir = str(handle.userdir)
            report.save_name = handle.save_name or "not saved (the world lives in the running game)"
            print(f"{args.scenario}: {report.mode}/{args.scheme}/{args.input}, {report.gateway_line}, "
                  f"up to {args.turns} turns, seed {args.seed}")
            Driver(args, report, handle, gateway, transcript, frames_dir).run()
    except HarnessError as exc:
        report.code, report.reason = EXIT_HARNESS, f"harness error: {exc}"
    except Stop as exc:
        report.code, report.reason = exc.code, exc.reason
    except KeyboardInterrupt:
        report.code, report.reason = EXIT_KILL, "interrupted by hand"
    except BaseException as exc:  # noqa: BLE001 - even a driver bug must leave a report behind
        report.code = EXIT_HARNESS
        report.reason = f"harness error: {type(exc).__name__}: {exc}"
        report.notes.append(traceback.format_exc())
    finally:
        report.wall_s = time.monotonic() - start
        if handle is not None:
            try:
                close_tiles(handle)
            except Exception as exc:  # noqa: BLE001
                report.notes.append(f"closing the tiles connection failed: {exc}")
            try:
                handle.close()
            except Exception as exc:  # noqa: BLE001
                report.notes.append(f"closing the session failed: {exc}")
        write_summary(report_dir / "summary.md", report)
        print(report.cost())
        if report.code != EXIT_CLEAN:
            print(f"agent_playtest: {report.reason}", file=sys.stderr)
    return report.code


if __name__ == "__main__":
    sys.exit(main())
