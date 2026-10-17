"""Model layer for the agentic playtest (fork issue #6).

One interface, :meth:`Gateway.decide`, over three API surfaces:

* ``chat`` - an OpenAI-compatible ``/chat/completions`` route that is asked for a
  JSON object naming the action.
* ``systemone`` - TypeSafe System One typed decisions (``choice``, ``noul``,
  ``score``).
* ``decisions`` - OpenAI's Decisions API, typed ``predicate``/``choice``/``score``
  questions with probabilities, billed on input tokens only.

The gateway never dials a lane that is not free: the free tier is the budget, so a
spent free tier moves to the next model or stops, it does not bill.

Standard library only. Importing this module reads no key and opens no socket;
that happens on the first real (non dry-run) request.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

DEFAULT_TIMEOUT = 30.0
RETRY_SLEEP = 1.0
CHARS_PER_TOKEN = 4  # rough English/prose heuristic for the size of a request in tokens
QUOTA_STATUSES = (402, 429)
SYSTEMONE_MAX_OPTIONS = 64  # Jev gateway bound; the other surfaces take up to 255


class ModelError(Exception):
    """Base class for every failure raised by this layer."""


class MissingKey(ModelError):
    """The environment does not hold the key a surface needs."""


class NoModelAvailable(ModelError):
    """Every model in the pool is exhausted, so no decision can be made.

    ``reasons`` maps a model id to the reason it was retired or skipped, in the
    order the gateway gave up on it.
    """

    def __init__(self, reasons: dict[str, str]):
        self.reasons = dict(reasons)
        detail = ", ".join(f"{model}: {reason}" for model, reason in self.reasons.items())
        super().__init__(f"no model available ({detail})")


class BudgetExceeded(ModelError):
    """A cap (usd or call count) would be crossed by the next request."""

    def __init__(self, message: str, *, spent_usd: float, calls: int):
        self.spent_usd = spent_usd
        self.calls = calls
        super().__init__(message)


class _Retire(Exception):
    """The model cannot serve for the rest of this run; try the next one."""


class _Quota(_Retire):
    """Free-tier or credit exhaustion (429/402, insufficient_quota, free limit)."""


class _Rejected(_Retire):
    """The surface refused the request (4xx): the model or the shape is unusable."""


class _TryNext(Exception):
    """This call failed; another model may still answer."""


# --------------------------------------------------------------------------- registry

@dataclass(frozen=True)
class ModelSpec:
    """One catalog model: which surface reaches it, how big it is, what it costs."""

    id: str
    provider: str  # "xplabs" | "opencode"
    surface: str  # "chat" | "systemone" | "decisions"
    context: int | None  # tokens shared by state and question; None = not published
    vision: bool
    free: bool
    usd_per_mtok_in: float = 0.0  # list price; a free model contributes 0
    usd_per_mtok_out: float = 0.0
    free_until: str | None = None  # ISO date: after it the model is not free any more
    note: str = ""


REGISTRY: dict[str, ModelSpec] = {
    spec.id: spec
    for spec in (
        ModelSpec(
            "clef-flash", "xplabs", "systemone", 65_536, False, True,
            note="1e12 tok/day, free without a card",
        ),
        ModelSpec(
            "clef", "xplabs", "systemone", 65_536, True, True,
            note="16,384 context with images; multimodal per description, text per catalog row",
        ),
        ModelSpec(
            "jev-latest", "xplabs", "systemone", 32_000, False, True,
            note="context shared by state and questions; needs a card and a settled $1",
        ),
        ModelSpec(
            "gpt-6-luna-decisions", "xplabs", "decisions", 922_000, True, True,
            usd_per_mtok_in=0.10, free_until="2026-11-14",
            note="billed on input tokens only; free until 2026-11-14",
        ),
        ModelSpec(
            "deepseek-v4.1-flash-1017", "xplabs", "chat", 1_048_576, True, True,
            note="3.75M in / 750k out per day",
        ),
        ModelSpec(
            "jev-1.13-free", "opencode", "systemone", 32_000, False, True,
            note="OpenCode publishes no context; the Jev family shares 32,000",
        ),
        ModelSpec(
            "deepseek-v4.1-flash-free", "opencode", "chat", None, False, True,
            note="context not published",
        ),
        ModelSpec(
            "glm-5.3-flash-free", "opencode", "chat", None, False, True,
            note="context not published",
        ),
    )
}

# (provider, surface) -> (endpoint, key environment variable)
SURFACES: dict[tuple[str, str], tuple[str, str]] = {
    ("xplabs", "chat"): ("https://api.experientiallabs.ai/v1/chat/completions", "XPL_SK_AGENT"),
    ("xplabs", "systemone"): ("https://api.experientiallabs.ai/v1/systemone", "XPL_SK_AGENT"),
    ("xplabs", "decisions"): ("https://api.experientiallabs.ai/v1/decisions", "XPL_SK_AGENT"),
    ("opencode", "chat"): ("https://opencode.ai/inference/openai/v1/chat/completions", "OC_SK_AGENT"),
    ("opencode", "systemone"): ("https://opencode.ai/inference/systemone/v1/systemone", "OC_SK_AGENT"),
}

POOLS: dict[str, list[str]] = {
    "vision": [
        "gpt-6-luna-decisions",
        "deepseek-v4.1-flash-1017",
        "clef",
        "clef-flash",
        "jev-latest",
        "jev-1.13-free",
        "deepseek-v4.1-flash-free",
        "glm-5.3-flash-free",
    ],
    "text": [
        "clef-flash",
        "jev-latest",
        "jev-1.13-free",
        "deepseek-v4.1-flash-free",
        "glm-5.3-flash-free",
    ],
}


def usable(spec: ModelSpec, *, today: date | None = None) -> bool:
    """False when the model is not free any more and must never be dialled."""
    if not spec.free:
        return False
    if spec.free_until is None:
        return True
    return (today or date.today()) <= date.fromisoformat(spec.free_until)


def pool(name: str) -> list[str]:
    """The ordered model ids of a named pool, models on a spent promo window removed."""
    if name not in POOLS:
        raise ValueError(f"unknown pool {name!r}; expected one of {sorted(POOLS)}")
    return [model for model in POOLS[name] if usable(REGISTRY[model])]


def estimate_tokens(text: str) -> int:
    """Rough token count of a string (prose heuristic: four characters per token)."""
    return -(-len(text) // CHARS_PER_TOKEN) if text else 0


def compact_state(
    text: str, *, context: int, reserve_tokens: int = 0
) -> tuple[str, bool]:
    """Shrink ``text`` to fit a model's context, returning ``(text, changed)``.

    Keeps the last turns (trailing lines), an optional one-line summary (the first
    line, when it is short) and a marker naming how many lines were dropped. The
    result is bounded by the budget plus the summary and marker.
    """
    budget = max(64, context - reserve_tokens)
    if estimate_tokens(text) <= budget:
        return text, False
    keep_chars = budget * CHARS_PER_TOKEN
    lines = text.splitlines() or [text]
    kept: list[str] = []
    used = 0
    for line in reversed(lines):
        add = len(line) + 1
        if kept and used + add > keep_chars:
            break
        kept.append(line)
        used += add
        if used >= keep_chars:
            break
    kept.reverse()
    if len(kept) == 1 and used > keep_chars:
        kept = [kept[0][-keep_chars:]]  # a single line longer than the whole budget
    dropped = len(lines) - len(kept)
    summary = ""
    if dropped >= 1 and len(lines[0]) <= 200 and lines[0] != kept[0]:
        summary = lines[0] + "\n"
        dropped -= 1
    marker = f"[compacted: {dropped} of {len(lines)} earlier lines omitted]"
    return f"{summary}{marker}\n" + "\n".join(kept), True


# --------------------------------------------------------------------------- questions

@dataclass(frozen=True)
class Question:
    """A typed question for the non-chat surfaces."""

    qid: str
    instructions: str
    kind: str = "choice"  # "choice" | "noul" | "score"
    choices: dict[str, str] | None = None  # choice: option id -> description
    levels: tuple[str, ...] = ()  # score: ordered levels

    def __post_init__(self) -> None:
        if self.kind not in ("choice", "noul", "score"):
            raise ValueError(f"unknown question kind {self.kind!r}")
        if self.kind == "choice" and not self.choices:
            raise ValueError("a choice question needs a criteria/choices map")
        if self.kind == "choice" and not 2 <= len(self.choices or {}) <= 255:
            raise ValueError("a choice question needs 2 to 255 options")
        if self.kind == "score" and not 2 <= len(self.levels) <= 10:
            raise ValueError("a score question needs 2 to 10 levels")


@dataclass(frozen=True)
class Answer:
    """A typed answer: the chosen option, a probability, or a score."""

    kind: str
    value: str | float
    confidence: float
    tokens_in: int
    tokens_out: int
    measured: bool  # True: usage from the response. False: estimated locally.


@dataclass(frozen=True)
class Decision:
    action_id: str
    confidence: float
    model: str
    tokens_in: int
    tokens_out: int
    usd: float
    measured: bool
    exhausted: tuple[str, ...]  # models retired so far this run, in order


# --------------------------------------------------------------------------- answers

def _clamp(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def _first_number(source: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _argmax(mapping: dict[str, float], allowed: set[str] | None) -> tuple[str, float] | None:
    best: tuple[str, float] | None = None
    for option, probability in mapping.items():
        if allowed is not None and option not in allowed:
            continue
        if best is None or probability > best[1]:
            best = (option, float(probability))
    return best


def _json_objects(text: str) -> list[str]:
    """Balanced ``{...}`` substrings, longest first, so prose around JSON is tolerated."""
    found: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0:
                found.append(text[start : index + 1])
    found.sort(key=len, reverse=True)
    return found


CHAT_ACTION_KEYS = ("action", "action_id", "choice", "answer", "id")


def _parse_chat_choice(
    text: str, choices: dict[str, str]
) -> tuple[str, float] | None:
    """Pull ``(action_id, confidence)`` out of a chat reply, prose allowed."""
    for candidate in _json_objects(text):
        try:
            payload = json.loads(candidate)
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        for key in CHAT_ACTION_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value in choices:
                confidence = _first_number(payload, ("confidence", "probability", "prob"))
                return value, _clamp(confidence if confidence is not None else 0.5)
        probabilities = payload.get("probabilities")
        if isinstance(probabilities, dict):
            numbers = {
                option: value
                for option, value in probabilities.items()
                if option in choices and isinstance(value, (int, float))
            }
            best = _argmax(numbers, set(choices))
            if best is not None:
                return best[0], _clamp(best[1])
    # No JSON: accept a reply that names exactly one option.
    named = [option for option in choices if re.search(rf"\b{re.escape(option)}\b", text)]
    if len(named) == 1 and text.strip():
        return named[0], 0.5
    return None


def _parse_systemone_answer(
    answer: dict[str, Any], choices: dict[str, str] | None
) -> tuple[str, str | float, float]:
    """System One answer -> ``(kind, value, confidence)``."""
    kind = answer.get("type")
    if kind == "choice":
        probabilities = {
            option: float(value)
            for option, value in (answer.get("probabilities") or {}).items()
            if isinstance(value, (int, float))
        }
        chosen = answer.get("choice")
        confidence = _first_number(answer, ("confidence",))
        if not isinstance(chosen, str) or (choices is not None and chosen not in choices):
            best = _argmax(probabilities, set(choices) if choices else None)
            if best is None:
                raise _TryNext("choice answer names no known option")
            chosen, confidence = best[0], confidence if confidence is not None else best[1]
        if confidence is None:
            confidence = probabilities.get(chosen, 0.5)
        return "choice", chosen, _clamp(confidence)
    if kind == "noul":
        value = answer.get("noul")
        if not isinstance(value, (int, float)):
            raise _TryNext("noul answer carries no probability")
        # A noul is the probability itself; confidence is how far it is from a toss-up.
        return "noul", float(value), _clamp(abs(2.0 * float(value) - 1.0))
    if kind == "score":
        value = answer.get("score")
        if not isinstance(value, (int, float)):
            raise _TryNext("score answer carries no score")
        confidence = _first_number(answer, ("confidence",))
        return "score", float(value), _clamp(confidence if confidence is not None else 0.5)
    raise _TryNext(f"unsupported answer type {kind!r}")


def _parse_decisions_answer(
    answers: list[Any], name: str, choices: set[str] | None
) -> tuple[str, str | float, float]:
    """Decisions API answers -> ``(kind, value, confidence)`` for question ``name``."""
    if not isinstance(answers, list) or not answers:
        raise _TryNext("decision response carries no answers")
    answer: Any = None
    for entry in answers:
        if isinstance(entry, dict) and entry.get("name") == name:
            answer = entry
            break
    if answer is None:
        answer = answers[0]
    if not isinstance(answer, dict):
        raise _TryNext("decision answer is not an object")
    kind = answer.get("type")
    if kind == "refusal":
        raise _TryNext(f"model refused the question {answer.get('name')!r}")
    if kind == "predicate":
        probability = answer.get("probability")
        if not isinstance(probability, (int, float)):
            raise _TryNext("predicate answer carries no probability")
        return "noul", float(probability), _clamp(abs(2.0 * float(probability) - 1.0))
    if kind == "score":
        score = answer.get("score")
        if not isinstance(score, (int, float)):
            raise _TryNext("score answer carries no score")
        confidence = _first_number(answer, ("confidence",))
        return "score", float(score), _clamp(confidence if confidence is not None else 0.5)
    if kind == "choice":
        probabilities = {
            str(entry.get("value")): float(entry["probability"])
            for entry in (answer.get("probabilities") or [])
            if isinstance(entry, dict)
            and isinstance(entry.get("probability"), (int, float))
        }
        chosen = answer.get("choice")
        confidence = _first_number(answer, ("confidence",))
        if isinstance(chosen, bool):
            raise _TryNext("choice answer is a boolean, not one of our option ids")
        if not isinstance(chosen, str) or (choices is not None and chosen not in choices):
            best = _argmax(probabilities, choices)
            if best is None:
                raise _TryNext("choice answer names no known option")
            chosen, confidence = best[0], confidence if confidence is not None else best[1]
        if confidence is None:
            confidence = probabilities.get(chosen, 0.5)
        return "choice", chosen, _clamp(confidence)
    raise _TryNext(f"unsupported answer type {kind!r}")


# --------------------------------------------------------------------------- transport

def _error_fields(body: str) -> tuple[str, str]:
    """``(code, message)`` from a provider error body, tolerating a plain-text one."""
    try:
        payload = json.loads(body)
    except ValueError:
        return "", body.strip()[:400]
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return str(error.get("code") or error.get("type") or ""), str(error.get("message") or "")
    if isinstance(error, str):
        return "", error
    return "", body.strip()[:400]


def _is_quota(status: int, code: str, message: str) -> bool:
    if status in QUOTA_STATUSES:
        return True
    haystack = f"{code} {message}".lower()
    return "quota" in haystack or "free limit" in haystack


def _data_url(image: bytes) -> str:
    if image.startswith(b"\x89PNG"):
        mime = "image/png"
    elif image.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    else:
        mime = "image/png"

    return f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"


def _post(client: "Client", body: dict[str, Any], *, timeout: float, attempts: int = 2) -> dict[str, Any]:
    """POST JSON and return the parsed reply. One retry on 5xx or a timeout, never on 429."""
    key = os.environ.get(client.key_env, "")
    if not key:
        raise MissingKey(
            f"{client.key_env} is not set in the environment; export it or pass dry_run=True"
        )
    request = urllib.request.Request(
        client.endpoint,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",  # never logged, never echoed in an error
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    last = "no attempt made"
    for attempt in range(attempts):
        raw: str | None = None
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            payload = error.read().decode("utf-8", "replace")
            code, message = _error_fields(payload)
            if _is_quota(error.code, code, message):
                raise _Quota(f"HTTP {error.code} {code or 'error'}: {message}") from error
            if not 500 <= error.code < 600:
                raise _Rejected(f"HTTP {error.code} {code or 'error'}: {message}") from error
            last = f"HTTP {error.code} {message}"
            if attempt + 1 >= attempts:
                raise _TryNext(f"{last} after {attempt + 1} attempts") from error
        except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
            last = f"{type(error).__name__}: {error}"
            if attempt + 1 >= attempts:
                raise _TryNext(f"no reply after {attempt + 1} attempts ({last})") from error
        if raw is not None:
            try:
                return json.loads(raw)
            except ValueError as error:
                raise _TryNext(f"reply is not JSON: {raw[:200]!r}") from error
        time.sleep(RETRY_SLEEP)
    raise _TryNext(f"no reply after {attempts} attempts ({last})")


def _usage(body: dict[str, Any], reply: dict[str, Any], reply_text: str) -> tuple[int, int, bool]:
    """``(tokens_in, tokens_out, measured)``; estimates from the request when absent."""
    usage = reply.get("usage") if isinstance(reply.get("usage"), dict) else {}
    tokens_in = usage.get("prompt_tokens", usage.get("input_tokens"))
    tokens_out = usage.get("completion_tokens", usage.get("output_tokens"))
    if tokens_in is None and tokens_out is None:
        size = estimate_tokens(json.dumps(body))
        return size, estimate_tokens(reply_text), False
    return int(tokens_in or 0), int(tokens_out or 0), True


def cost_usd(spec: ModelSpec, tokens_in: int, tokens_out: int) -> float:
    """List-price cost of a call; a free model always reports 0."""
    if spec.free:
        return 0.0
    return (tokens_in * spec.usd_per_mtok_in + tokens_out * spec.usd_per_mtok_out) / 1_000_000


@dataclass(frozen=True)
class Client:
    """One surface of one provider: where to POST, which key unlocks it."""

    provider: str
    surface: str
    endpoint: str
    key_env: str

    def ask(
        self,
        spec: ModelSpec,
        question: Question,
        state_text: str,
        state_image: bytes | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        allow_estimate: bool = True,
    ) -> Answer:
        if self.surface == "chat":
            return self._ask_chat(spec, question, state_text, state_image, timeout, allow_estimate)
        if self.surface == "systemone":
            return self._ask_systemone(spec, question, state_text, state_image, timeout, allow_estimate)
        if self.surface == "decisions":
            return self._ask_decisions(spec, question, state_text, state_image, timeout, allow_estimate)
        raise ValueError(f"unknown surface {self.surface!r}")

    def _sees(self, spec: ModelSpec, state_image: bytes | None) -> bool:
        return bool(state_image) and spec.vision

    def _no_image_note(self, spec: ModelSpec, state_text: str, state_image: bytes | None) -> str:
        if state_image and not spec.vision:
            return f"[state image omitted: {spec.id} is text-only]\n{state_text}"
        return state_text

    def _ask_chat(
        self, spec, question, state_text, state_image, timeout, allow_estimate
    ) -> Answer:
        text = self._no_image_note(spec, state_text, state_image)
        prompt = _render_choice(question)
        user: Any = f"{text}\n\n{prompt}"
        if self._sees(spec, state_image):
            user = [
                {"type": "text", "text": f"{text}\n\n{prompt}"},
                {"type": "image_url", "image_url": {"url": _data_url(state_image or b"")}},
            ]
        body = {
            "model": spec.id,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert player of Cataclysm: Bright Nights. Decide the single "
                        "best action for the current turn. Reply with one JSON object and nothing "
                        'else: {"action": "<id>", "confidence": <0..1>} - <id> must be one of the '
                        "listed ids."
                    ),
                },
                {"role": "user", "content": user},
            ],
        }
        if question.kind != "choice" or not question.choices:
            raise ValueError("the chat surface answers choice questions only")
        reply = _post(self, body, timeout=timeout)
        choices = reply.get("choices")
        message = choices[0].get("message") if isinstance(choices, list) and choices else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise _TryNext("chat reply carries no text content")
        parsed = _parse_chat_choice(content, question.choices)
        if parsed is None:
            raise _TryNext("chat reply names no action id")
        tokens_in, tokens_out, measured = _usage(body, reply, content)
        if not measured and not allow_estimate:
            raise _TryNext("chat reply carries no usage and estimates are not allowed")
        return Answer("choice", parsed[0], parsed[1], tokens_in, tokens_out, measured)

    def _ask_systemone(
        self, spec, question, state_text, state_image, timeout, allow_estimate
    ) -> Answer:
        if question.choices and len(question.choices) > SYSTEMONE_MAX_OPTIONS:
            # The Jev gateway bound is 64 options; another model may still answer.
            raise _TryNext(
                f"systemone takes at most {SYSTEMONE_MAX_OPTIONS} options, got {len(question.choices)}"
            )
        state: Any = self._no_image_note(spec, state_text, state_image)
        body = {
            "model": spec.id,
            "state": state,
            "questions": {question.qid: _systemone_question(question)},
        }
        if self._sees(spec, state_image):
            # TypeSafe state may be an array of parts; keep the image attempt, fall back below.
            body["state"] = [
                {"type": "input_text", "text": state},
                {"type": "input_image", "image_url": _data_url(state_image or b"")},
            ]
        try:
            reply = _post(self, body, timeout=timeout)
        except _Rejected:
            if not self._sees(spec, state_image):
                raise
            body["state"] = state  # the surface refused the image: ask about the text alone
            reply = _post(self, body, timeout=timeout)
        answers = reply.get("answers")
        answer = answers.get(question.qid) if isinstance(answers, dict) else None
        if not isinstance(answer, dict):
            raise _TryNext(f"systemone reply carries no answer for {question.qid!r}")
        kind, value, confidence = _parse_systemone_answer(answer, question.choices)
        tokens_in, tokens_out, measured = _usage(body, reply, "")
        if not measured and not allow_estimate:
            raise _TryNext("systemone reply carries no usage and estimates are not allowed")
        return Answer(kind, value, confidence, tokens_in, tokens_out, measured)

    def _ask_decisions(
        self, spec, question, state_text, state_image, timeout, allow_estimate
    ) -> Answer:
        text = self._no_image_note(spec, state_text, state_image)
        source: Any = text
        if self._sees(spec, state_image):
            source = [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": text},
                        {"type": "input_image", "image_url": _data_url(state_image or b"")},
                    ],
                }
            ]
        body = {
            "model": spec.id,
            "input": source,
            "questions": [_decisions_question(question)],
        }
        reply = _post(self, body, timeout=timeout)
        choices = set(question.choices) if question.choices else None
        kind, value, confidence = _parse_decisions_answer(
            reply.get("answers"), question.qid, choices
        )
        tokens_in, tokens_out, measured = _usage(body, reply, "")
        if not measured and not allow_estimate:
            raise _TryNext("decision response carries no usage and estimates are not allowed")
        return Answer(kind, value, confidence, tokens_in, tokens_out, measured)


def _render_choice(question: Question) -> str:
    lines = [question.instructions, "Choose exactly one of these action ids:"]
    for option, description in (question.choices or {}).items():
        lines.append(f"- {option}: {description}" if description else f"- {option}")
    return "\n".join(lines)


def _systemone_question(question: Question) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": question.kind, "instructions": question.instructions}
    if question.kind == "choice":
        payload["criteria"] = dict(question.choices or {})
    elif question.kind == "score":
        payload["criteria"] = list(question.levels)
    return payload


def _decisions_question(question: Question) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": question.qid, "instructions": question.instructions}
    if question.kind == "choice":
        payload["type"] = "choice"
        payload["choices"] = [
            {"value": option, "description": description}
            for option, description in (question.choices or {}).items()
        ]
    elif question.kind == "score":
        payload["type"] = "score"
        payload["levels"] = [{"label": level} for level in question.levels]
    else:
        payload["type"] = "predicate"
    return payload


def client_for(model_id: str) -> Client:
    """The surface that reaches ``model_id``."""
    spec = REGISTRY.get(model_id)
    if spec is None:
        raise ValueError(f"unknown model {model_id!r}")
    endpoint, key_env = SURFACES[(spec.provider, spec.surface)]
    return Client(spec.provider, spec.surface, endpoint, key_env)


def required_keys(models: list[str]) -> list[str]:
    """The environment variables a live (non dry-run) run over ``models`` needs."""
    needed: list[str] = []
    for model_id in models:
        env = client_for(model_id).key_env
        if env not in needed:
            needed.append(env)
    return needed


def missing_keys(models: list[str]) -> list[str]:
    """The subset of :func:`required_keys` that is absent from the environment."""
    return [env for env in required_keys(models) if not os.environ.get(env)]


# --------------------------------------------------------------------------- gateway

class Gateway:
    """Chooses one action from a closed list through the cheapest free surface.

    Exhaustion is per-run state: a new instance starts with a full pool.
    """

    def __init__(
        self,
        *,
        models: list[str],
        budget_usd: float | None = None,
        max_calls: int | None = None,
        dry_run: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        if not models:
            raise ValueError("models must not be empty (use pool('vision') or pool('text'))")
        self.models = list(models)
        self.budget_usd = budget_usd
        self.max_calls = max_calls
        self.dry_run = dry_run
        self.timeout = timeout
        self.spent_usd = 0.0
        self.calls = 0
        self.compactions = 0
        self._retired: dict[str, str] = {}

    @property
    def exhausted(self) -> tuple[str, ...]:
        return tuple(self._retired)

    def _retire(self, model_id: str, reason: str) -> None:
        self._retired[model_id] = reason

    def _check_caps(self, spec: ModelSpec, state: str, question: Question) -> None:
        if self.max_calls is not None and self.calls >= self.max_calls:
            raise BudgetExceeded(
                f"max_calls={self.max_calls} reached after {self.calls} calls",
                spent_usd=self.spent_usd,
                calls=self.calls,
            )
        if self.budget_usd is None:
            return
        rough_in = estimate_tokens(f"{state}{question.instructions}{''.join(question.choices or {})}")
        estimate = cost_usd(spec, rough_in, 0)
        if self.spent_usd + estimate > self.budget_usd:
            raise BudgetExceeded(
                f"budget_usd={self.budget_usd} would be crossed: spent {self.spent_usd:.6f} usd",
                spent_usd=self.spent_usd,
                calls=self.calls,
            )

    def decide(
        self,
        *,
        state_text: str,
        state_image: bytes | None,
        question: str,
        choices: dict[str, str],
        allow_estimate: bool = True,
    ) -> Decision:
        """Decide one action from ``choices`` (id -> description).

        ``allow_estimate=False`` refuses a reply that carries no usage instead of
        accounting for it with a local estimate.
        """
        if not choices:
            raise ValueError("choices must not be empty")
        typed = Question("action", question, "choice", dict(choices))
        failed: dict[str, str] = {}
        for model_id in self.models:
            if model_id in self._retired:
                continue
            spec = REGISTRY.get(model_id)
            if spec is None:
                self._retire(model_id, "unknown model slug")
                continue
            if not usable(spec):
                self._retire(model_id, f"not free after {spec.free_until}")
                continue
            state = state_text
            if spec.context is not None:
                state, shrunk = compact_state(
                    state_text,
                    context=spec.context,
                    reserve_tokens=estimate_tokens(question) + 256,
                )
                if shrunk:
                    self.compactions += 1
            self._check_caps(spec, state, typed)
            self.calls += 1
            if self.dry_run:
                action = min(choices)
                return Decision(
                    action_id=action,
                    confidence=1.0,
                    model=model_id,
                    tokens_in=0,
                    tokens_out=0,
                    usd=0.0,
                    measured=True,  # dry-run zeros are exact, not estimates
                    exhausted=self.exhausted,
                )
            try:
                answer = client_for(model_id).ask(
                    spec, typed, state, state_image, timeout=self.timeout,
                    allow_estimate=allow_estimate,
                )
            except _Quota as error:
                self._retire(model_id, f"exhausted: {error}")
                continue
            except _Rejected as error:
                self._retire(model_id, f"refused: {error}")
                continue
            except _TryNext as error:
                failed[model_id] = f"failed: {error}"
                continue
            if answer.kind != "choice" or not isinstance(answer.value, str):
                failed[model_id] = f"answered {answer.kind}, not a choice"
                continue
            if answer.value not in choices:
                failed[model_id] = f"chose unknown option {answer.value!r}"
                continue
            usd = cost_usd(spec, answer.tokens_in, answer.tokens_out)
            self.spent_usd += usd
            return Decision(
                action_id=answer.value,
                confidence=answer.confidence,
                model=model_id,
                tokens_in=answer.tokens_in,
                tokens_out=answer.tokens_out,
                usd=usd,
                measured=answer.measured,
                exhausted=self.exhausted,
            )
        raise NoModelAvailable({**self._retired, **failed})

    def report(self) -> dict[str, Any]:
        """Run totals for the playtest report."""
        return {
            "calls": self.calls,
            "spent_usd": self.spent_usd,
            "compactions": self.compactions,
            "exhausted": {model: reason for model, reason in self._retired.items()},
        }


# --------------------------------------------------------------------------- self-test

def _self_test() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f" ({detail})" if detail and not ok else ""))
        if not ok:
            failures.append(name)

    def decide(gateway: Gateway, state: str = "Turn 1: you are in a house, unharmed.") -> Decision:
        return gateway.decide(
            state_text=state,
            state_image=None,
            question="What should the survivor do this turn?",
            choices={"wait": "stand still", "smash": "break the window", "run": "leave the house"},
        )

    catalog = {
        "clef-flash", "clef", "jev-latest", "gpt-6-luna-decisions",
        "deepseek-v4.1-flash-1017", "jev-1.13-free", "deepseek-v4.1-flash-free",
        "glm-5.3-flash-free",
    }
    check("registry holds the nine catalog models", set(REGISTRY) == catalog)
    check("every model has a reachable surface",
          all((s.provider, s.surface) in SURFACES for s in REGISTRY.values()))
    check("every pool id is in the registry",
          all(model in REGISTRY for models in POOLS.values() for model in models))

    vision = ["gpt-6-luna-decisions", "deepseek-v4.1-flash-1017", "clef", "clef-flash",
              "jev-latest", "jev-1.13-free", "deepseek-v4.1-flash-free", "glm-5.3-flash-free"]
    if not usable(REGISTRY["gpt-6-luna-decisions"]):
        vision.remove("gpt-6-luna-decisions")
    check("vision pool ordering", pool("vision") == vision, f"{pool('vision')}")
    check("text pool ordering",
          pool("text") == ["clef-flash", "jev-latest", "jev-1.13-free",
                           "deepseek-v4.1-flash-free", "glm-5.3-flash-free"],
          f"{pool('text')}")
    check("pool() copies, callers cannot corrupt it", pool("text") is not POOLS["text"])
    try:
        pool("nope")
        check("unknown pool name raises", False)
    except ValueError:
        check("unknown pool name raises", True)
    luna = REGISTRY["gpt-6-luna-decisions"]
    check("a promo window past its date is not usable",
          usable(luna, today=date(2026, 10, 17)) and not usable(luna, today=date(2026, 11, 15)))

    first = decide(Gateway(models=pool("vision"), dry_run=True), "Turn 1: dry.")
    check("dry run picks deterministically from the choices", first.action_id == "run")
    check("dry run dials the first model of the pool", first.model == vision[0], first.model)
    check("dry run costs nothing and measures it", first.usd == 0.0 and first.measured)
    check("dry run, nothing retired yet", first.exhausted == ())

    fallback = Gateway(models=["ghost-model", "clef-flash"], dry_run=True)
    decided = decide(fallback)
    check("an unknown model is retired, the next one answers",
          decided.model == "clef-flash" and decided.exhausted == ("ghost-model",),
          f"{decided.model} {decided.exhausted}")
    check("exhaustion is per run, a new gateway starts fresh",
          Gateway(models=["ghost-model", "clef-flash"], dry_run=True).exhausted == ())
    try:
        decide(Gateway(models=["ghost-model"], dry_run=True))
        check("a spent pool raises NoModelAvailable", False)
    except NoModelAvailable as error:
        check("a spent pool raises NoModelAvailable", "ghost-model" in error.reasons)

    big = "\n".join(f"Turn {turn}: the survivor is in the house, hp 80, {turn} turns elapsed."
                    for turn in range(1, 4_000))
    compact_gateway = Gateway(models=["jev-1.13-free"], dry_run=True)
    decide(compact_gateway, big)
    check("a small-context fallback compacts the state", compact_gateway.compactions == 1)
    check("compaction leaves a large state alone via a big-context model",
          Gateway(models=["deepseek-v4.1-flash-1017"], dry_run=True).decide(
              state_text=big, state_image=None, question="q", choices={"a": "", "b": ""}
          ).model == "deepseek-v4.1-flash-1017")
    shrunk, changed = compact_state(big, context=32_000, reserve_tokens=256)
    check("compaction reports the change", changed)
    check("compaction keeps the tail",
          shrunk.endswith("Turn 3999: the survivor is in the house, hp 80, 3999 turns elapsed."))
    check("compaction marks the summary and the drop",
          "[compacted:" in shrunk and shrunk.startswith("Turn 1:"))
    check("compaction fits the context", len(shrunk) <= (32_000 - 256) * CHARS_PER_TOKEN + 400,
          str(len(shrunk)))
    check("a state that fits is returned untouched",
          compact_state("short state", context=32_000) == ("short state", False))

    capped = Gateway(models=["clef-flash"], dry_run=True, max_calls=1)
    decide(capped)
    try:
        decide(capped)
        check("max_calls raises BudgetExceeded", False)
    except BudgetExceeded as error:
        check("max_calls raises BudgetExceeded", error.calls == 1)
    over = Gateway(models=["clef-flash"], dry_run=True, budget_usd=1.0)
    over.spent_usd = 5.0
    try:
        decide(over)
        check("budget_usd raises BudgetExceeded", False)
    except BudgetExceeded:
        check("budget_usd raises BudgetExceeded", True)

    check("a free model costs 0", cost_usd(luna, 10_000, 10_000) == 0.0)
    paid = replace(luna, free=False)
    check("a paid model is priced on input tokens only",
          abs(cost_usd(paid, 1_000_000, 1_000) - 0.10) < 1e-9)
    both = replace(luna, free=False, usd_per_mtok_in=1.0, usd_per_mtok_out=2.0)
    check("both token legs are priced", abs(cost_usd(both, 1_000_000, 500_000) - 2.0) < 1e-9)
    check("usage in the reply is measured",
          _usage({}, {"usage": {"input_tokens": 10, "output_tokens": 2}}, "") == (10, 2, True))
    check("chat-style usage keys are measured",
          _usage({}, {"usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}}, "")
          == (7, 3, True))
    estimated = _usage({"model": "m", "state": "x" * 400}, {}, "")
    check("absent usage is estimated from the request", estimated[0] > 0 and estimated[2] is False)
    check("an empty reply estimates no output tokens", _usage({}, {}, "")[1] == 0)

    parsed = _parse_chat_choice(
        'Sure, here you go:\n```json\n{"action": "smash", "confidence": 1.4}\n```',
        {"wait": "", "smash": "", "run": ""},
    )
    check("chat JSON survives surrounding prose and clamps confidence",
          parsed == ("smash", 1.0), f"{parsed}")
    check("chat prose naming one option is accepted",
          _parse_chat_choice("I would run.", {"wait": "", "run": ""}) == ("run", 0.5))
    check("chat reply with no usable id is rejected",
          _parse_chat_choice("I don't know.", {"wait": "", "run": ""}) is None)
    check("systemone noul becomes a probability",
          _parse_systemone_answer({"type": "noul", "noul": 0.75}, None) == ("noul", 0.75, 0.5))
    check("systemone score carries its confidence",
          _parse_systemone_answer({"type": "score", "score": 1.43, "confidence": 0.35}, None)
          == ("score", 1.43, 0.35))
    check("systemone choice carries probabilities",
          _parse_systemone_answer(
              {"type": "choice", "choice": "returns", "confidence": 1.0,
               "probabilities": {"returns": 1.0, "billing": 0.0}},
              {"returns": "", "billing": ""},
          ) == ("choice", "returns", 1.0))
    check("systemone hallucinated option falls back to the best known one",
          _parse_systemone_answer(
              {"type": "choice", "choice": "other", "probabilities": {"run": 0.7, "wait": 0.3}},
              {"run": "", "wait": ""},
          ) == ("choice", "run", 0.7))
    check("decisions choice reads value and confidence",
          _parse_decisions_answer(
              [{"type": "choice", "name": "action", "choice": "wait", "confidence": 0.61,
                "probabilities": [{"value": "wait", "probability": 0.61},
                                  {"value": "run", "probability": 0.39}]}],
              "action", {"wait", "run"},
          ) == ("choice", "wait", 0.61))
    predicate = _parse_decisions_answer([{"type": "predicate", "name": "a", "probability": 0.95}], "a", None)
    check("decisions predicate becomes a probability",
          predicate[0] == "noul" and predicate[1] == 0.95 and abs(predicate[2] - 0.9) < 1e-9, f"{predicate}")
    check("decisions score becomes a score",
          _parse_decisions_answer([{"type": "score", "name": "a", "score": 1.24, "confidence": 0.64}], "a", None)
          == ("score", 1.24, 0.64))
    try:
        _parse_decisions_answer([{"type": "refusal", "name": "a"}], "a", None)
        check("decisions refusal is not an answer", False)
    except _TryNext:
        check("decisions refusal is not an answer", True)

    try:
        Question("action", "q", "choice", {"only": ""})
        check("a one-option menu is rejected", False)
    except ValueError:
        check("a one-option menu is rejected", True)
    wide = Question("action", "q", "choice", {f"opt{index}": f"option {index}" for index in range(70)})
    try:
        client_for("jev-1.13-free").ask(REGISTRY["jev-1.13-free"], wide, "state", None)
        check("systemone skips a menu wider than 64 options", False)
    except _TryNext as error:
        check("systemone skips a menu wider than 64 options", "64" in str(error))

    saved = {name: os.environ.pop(name) for name in ("XPL_SK_AGENT", "OC_SK_AGENT") if name in os.environ}
    try:
        check("dry run needs no key", decide(Gateway(models=pool("vision"), dry_run=True)).model == vision[0])
        for model, env in (("clef-flash", "XPL_SK_AGENT"), ("jev-1.13-free", "OC_SK_AGENT")):
            try:
                decide(Gateway(models=[model]))
                check(f"a missing key names {env}", False)
            except MissingKey as error:
                check(f"a missing key names {env}", env in str(error))
    finally:
        os.environ.update(saved)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("all checks passed (no network, no key)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Model layer for the agentic playtest.")
    parser.add_argument("--self-test", action="store_true", help="run the offline dry-run checks")
    parser.add_argument("--pool", choices=sorted(POOLS), help="print an ordered pool")
    parser.add_argument("--demo", action="store_true", help="print one dry-run decision as JSON")
    parser.add_argument(
        "--check-keys", action="store_true",
        help="report the secrets a live run needs; exit 2 when one is missing",
    )
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            return _self_test()
        if args.pool:
            print(json.dumps(pool(args.pool), indent=2))
            return 0
        if args.check_keys:
            needed = required_keys(pool("vision"))
            absent = missing_keys(pool("vision"))
            print(f"live run needs: {', '.join(needed)}")
            if absent:
                print(
                    f"agent_models: missing repository secret(s) {', '.join(absent)}: "
                    "a live playtest cannot run. Add them, or run with --dry-run.",
                    file=sys.stderr,
                )
                return 2
            print("all keys present")
            return 0
        if args.demo:
            decision = Gateway(models=pool("text"), dry_run=True).decide(
                state_text="Turn 1: a zombie is at the door, you hold a crowbar.",
                state_image=None,
                question="What should the survivor do this turn?",
                choices={"wait": "stand still", "fight": "attack the zombie", "run": "leave"},
            )
            print(json.dumps(decision.__dict__, indent=2))
            return 0
    except MissingKey as error:
        # A readable line, not a traceback: the run cannot start without the secret.
        print(f"agent_models: {error}", file=sys.stderr)
        return 2
    except ModelError as error:
        print(f"agent_models: {type(error).__name__}: {error}", file=sys.stderr)
        return 3
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
