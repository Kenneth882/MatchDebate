from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import anthropic

from matchdebate.agents import api_key, model_name, read_prompt

OUTCOMES = ("home", "draw", "away")
POLICY_VERSION = "judge-v1.1"
EVIDENCE_ROOTS = (
    "table", "h2h", "home.table_row", "away.table_row", "home.last_5",
    "away.last_5", "home.home_record", "away.away_record",
    "home.shooting", "away.shooting",
)


class OutsideKnowledgeError(ValueError):
    """A contaminated prediction cannot be repaired in the same conversation."""


def fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def scoreline_outcome(home: int, away: int) -> str:
    return "home" if home > away else "away" if away > home else "draw"


def _response_json(raw: str) -> Any:
    text = raw.strip()
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() in {"```json", "```"} and lines[-1].strip() == "```":
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def _check_citation(path: Any, packet: dict) -> None:
    if not isinstance(path, str) or not any(
        path == root or path.startswith(root + ".") for root in EVIDENCE_ROOTS
    ):
        raise ValueError(f"Unsupported packet evidence path: {path!r}")
    value: Any = packet
    try:
        for part in path.split("."):
            if isinstance(value, dict):
                value = value[part]
            elif isinstance(value, list) and part.isdecimal():
                value = value[int(part)]
            else:
                raise KeyError(part)
    except (KeyError, IndexError, ValueError):
        raise ValueError(f"Packet evidence path does not exist: {path!r}") from None


def validate_prediction(payload: Any, packet: dict) -> dict:
    """Validate model output and derive the selected outcome in code."""
    if not isinstance(payload, dict):
        raise ValueError("Prediction must be a JSON object.")
    if payload.get("outside_knowledge_used") is True:
        raise OutsideKnowledgeError("Judge disclosed use of outside knowledge.")
    if payload.get("outside_knowledge_used") is not False:
        raise ValueError("outside_knowledge_used must be a boolean.")

    probabilities = payload.get("probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != set(OUTCOMES):
        raise ValueError("probabilities must contain exactly home, draw, and away.")
    for value in probabilities.values():
        if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
            raise ValueError("Each probability must be a finite number between 0 and 1.")
    if not math.isclose(sum(probabilities.values()), 1, rel_tol=0, abs_tol=1e-9):
        raise ValueError("Probabilities must sum to 1; do not use percentages.")

    scoreline = payload.get("scoreline")
    if not isinstance(scoreline, dict) or set(scoreline) != {"home", "away"}:
        raise ValueError("scoreline must contain exactly home and away goal counts.")
    if any(type(goals) is not int or goals < 0 for goals in scoreline.values()):
        raise ValueError("Goal counts must be nonnegative integers.")
    highest = max(probabilities.values())
    tied = [outcome for outcome in OUTCOMES if probabilities[outcome] == highest]
    outcome = scoreline_outcome(scoreline["home"], scoreline["away"])
    if outcome not in tied:
        raise ValueError(f"Scoreline must select a highest-probability outcome: {tied}.")

    reasoning = payload.get("reasoning")
    if not isinstance(reasoning, list) or not reasoning:
        raise ValueError("reasoning must contain at least one claim with packet_fields.")
    for item in reasoning:
        if not isinstance(item, dict) or not isinstance(item.get("claim"), str) or not item["claim"].strip():
            raise ValueError("Every reasoning entry must contain a nonempty claim.")
        paths = item.get("packet_fields")
        if not isinstance(paths, list) or not paths:
            raise ValueError("Every reasoning claim needs packet_fields citations.")
        for path in paths:
            _check_citation(path, packet)

    return {
        "probabilities": probabilities,
        "outcome": outcome,
        "scoreline": scoreline,
        "reasoning": [{"claim": item["claim"], "packet_fields": item["packet_fields"]}
                      for item in reasoning],
        "outside_knowledge_used": False,
        "tied_outcomes": tied if len(tied) > 1 else [],
    }


def judge_configuration(*, model: str | None = None, prompt: str | None = None) -> dict:
    configuration = {
        "model": model or model_name(),
        "prompt": read_prompt("judge.md") if prompt is None else prompt,
        "policy_version": POLICY_VERSION,
        "sdk_version": anthropic.__version__,
        "max_tokens": 4096,
    }
    if not configuration["prompt"].strip():
        raise ValueError("Judge prompt must not be empty.")
    return {**configuration, "version": fingerprint(configuration)}


def run_judge(packet: dict, briefs: dict[str, str], configuration: dict, *, client: Any = None) -> dict:
    """No filesystem/results tools: the only model inputs are packet and briefs."""
    attempts = []
    messages = [{"role": "user", "content": json.dumps({"packet": packet, "briefs": briefs})}]
    try:
        if client is None:
            client = anthropic.Anthropic(api_key=api_key(), timeout=60, max_retries=0)
        for attempt_number in range(2):
            response = client.messages.create(
                model=configuration["model"],
                max_tokens=configuration["max_tokens"],
                system=configuration["prompt"],
                messages=messages,
            )
            raw = "\n".join(block.text for block in response.content if block.type == "text")
            attempt = {
                "raw": raw,
                "response_id": response.id,
                "model": response.model,
                "stop_reason": response.stop_reason,
                "usage": response.usage.model_dump(),
            }
            attempts.append(attempt)
            try:
                prediction = validate_prediction(_response_json(raw), packet)
                if response.stop_reason != "end_turn":
                    raise ValueError(f"Incomplete response: {response.stop_reason}.")
                return {"status": "valid", "prediction": prediction, "attempts": attempts}
            except ValueError as error:
                attempt["validation_error"] = str(error)
                if isinstance(error, OutsideKnowledgeError) or attempt_number == 1:
                    return {"status": "invalid", "prediction": None, "attempts": attempts}
                messages.extend([
                    {"role": "assistant", "content": raw or "[Empty response]"},
                    {"role": "user", "content": (
                        f"Validation failed: {error}\n"
                        "You have one repair attempt. Return a complete corrected JSON prediction, "
                        "using the same packet and briefs. No result or odds are available."
                    )},
                ])
    except (anthropic.APIError, RuntimeError, TypeError) as error:
        # Persist failure type, not provider error bodies or credentials.
        return {"status": "error", "prediction": None, "attempts": attempts, "error": type(error).__name__}
    raise AssertionError("Judge attempt loop ended without a result.")
