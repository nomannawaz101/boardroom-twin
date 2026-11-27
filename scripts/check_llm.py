"""Check the model gateway: list models, one JSON call, one full tool round trip.

Prints PASS or FAIL per check and, on failure, only the error type. Never prints a key,
an address or a model reply. Run from anywhere: python "scripts/check_llm.py".
"""

import json
import logging
import os
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI  # noqa: E402

import config  # noqa: E402
from domain.timeline import count_working_days  # noqa: E402
from tools import working_days  # noqa: E402
from tools.registry import ToolContext, run_tool  # noqa: E402

log = logging.getLogger("check_llm")

TOOL_START = "2026-12-07"
TOOL_END = "2026-12-18"
TOOL_EXPECTED = count_working_days(date.fromisoformat(TOOL_START), date.fromisoformat(TOOL_END))


class CheckFailed(Exception):
    """A check ran but the answer was wrong; the message is a fixed safe phrase."""


def make_client() -> tuple[OpenAI, str]:
    names = (config.LLM_BASE_URL_VAR, config.LLM_API_KEY_VAR, config.LLM_MODEL_VAR)
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise CheckFailed("missing settings: " + ", ".join(missing))
    client = OpenAI(
        base_url=os.environ[config.LLM_BASE_URL_VAR],
        api_key=os.environ[config.LLM_API_KEY_VAR],
        timeout=config.LLM_TIMEOUT_S,
        max_retries=1,
    )
    return client, os.environ[config.LLM_MODEL_VAR]


def ensure_not_truncated(finish_reason: str | None) -> None:
    if finish_reason == "length":
        raise CheckFailed("answer cut off at the token cap")


def check_models(client: OpenAI, model: str) -> None:
    if not list(client.models.list()):
        raise CheckFailed("no models listed")


def check_json(client: OpenAI, model: str) -> None:
    reply = client.chat.completions.create(
        model=model,
        max_tokens=config.CHECK_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Reply with only JSON."},
            {"role": "user", "content": 'Return exactly {"ok": true}.'},
        ],
    )
    choice = reply.choices[0]
    ensure_not_truncated(choice.finish_reason)
    if json.loads(choice.message.content or "null") != {"ok": True}:
        raise CheckFailed("JSON answer had the wrong shape")


def check_tool_round_trip(client: OpenAI, model: str) -> None:
    messages: list[dict[str, object]] = [
        {"role": "system", "content": "Use the tools provided. Reply with only JSON."},
        {
            "role": "user",
            "content": (
                f"How many working days are there from {TOOL_START} to {TOOL_END}, "
                'both included? Answer as {"working_days": <number>}.'
            ),
        },
    ]
    first = client.chat.completions.create(
        model=model,
        max_tokens=config.CHECK_MAX_TOKENS,
        messages=messages,
        tools=[working_days.SCHEMA],
        tool_choice="auto",
    )
    calls = first.choices[0].message.tool_calls or []
    if not calls or calls[0].function.name != working_days.NAME:
        raise CheckFailed("model did not choose the working days tool")
    outcome = run_tool(calls[0].function.name, calls[0].function.arguments, ToolContext())
    if not outcome.ok:
        raise CheckFailed("model sent tool arguments the tool could not use")
    result = outcome.result
    messages.append(first.choices[0].message.model_dump(exclude_none=True))
    # Tool output goes back as data, never as instructions.
    messages.append({"role": "tool", "tool_call_id": calls[0].id, "content": json.dumps(result)})
    second = client.chat.completions.create(
        model=model,
        max_tokens=config.CHECK_MAX_TOKENS,
        messages=messages,
        tools=[working_days.SCHEMA],
        response_format={"type": "json_object"},
    )
    ensure_not_truncated(second.choices[0].finish_reason)
    answer = json.loads(second.choices[0].message.content or "null")
    if not isinstance(answer, dict) or answer.get("working_days") != TOOL_EXPECTED:
        raise CheckFailed("final answer did not use the tool result")


def run_check(name: str, check: Callable[[OpenAI, str], None], client: OpenAI, model: str) -> bool:
    try:
        check(client, model)
    except CheckFailed as failure:
        log.info("FAIL  %s: %s", name, failure)
        return False
    except Exception as error:  # noqa: BLE001 - only the type is shown, so nothing secret leaks
        log.info("FAIL  %s: %s", name, type(error).__name__)
        return False
    log.info("PASS  %s", name)
    return True


CHECKS: dict[str, Callable[[OpenAI, str], None]] = {
    "list models": check_models,
    "JSON mode": check_json,
    "tool round trip": check_tool_round_trip,
}


def main() -> int:
    # Only this script's logger prints; library loggers would print request URLs (the gateway host).
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        client, model = make_client()
    except CheckFailed as failure:
        log.info("FAIL  setup: %s", failure)
        return 1
    results = [run_check(name, check, client, model) for name, check in CHECKS.items()]
    log.info("OVERALL %s", "PASS" if all(results) else "FAIL")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
