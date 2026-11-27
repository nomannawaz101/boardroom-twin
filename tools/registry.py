"""Tool registry and runner. A new tool is one file plus one entry in TOOLS."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from tools import cost_calculator, quote_check, working_days


@dataclass(frozen=True)
class ToolContext:
    """What our code knows that the model does not pass in, such as the brief text."""

    brief: str = ""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    schema: dict[str, object]
    input_model: type[BaseModel]
    handler: Callable[[Any, ToolContext], dict[str, Any]]


@dataclass(frozen=True)
class ToolOutcome:
    name: str
    input: dict[str, Any]
    result: dict[str, Any]
    ok: bool
    ms: int


TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            cost_calculator.NAME,
            cost_calculator.SCHEMA,
            cost_calculator.CostInput,
            cost_calculator.handle,
        ),
        ToolSpec(quote_check.NAME, quote_check.SCHEMA, quote_check.QuoteInput, quote_check.handle),
        ToolSpec(
            working_days.NAME,
            working_days.SCHEMA,
            working_days.WorkingDaysInput,
            working_days.handle,
        ),
    )
}


def parse_arguments(arguments: str) -> dict[str, Any]:
    parsed = json.loads(arguments or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("tool arguments must be a JSON object")
    return parsed


def run_tool(
    name: str,
    arguments: str,
    context: ToolContext,
    available: dict[str, ToolSpec] | None = None,
) -> ToolOutcome:
    """Run one tool call from a model. Bad input becomes an error result, never a crash.

    `available` limits the call to the tools offered to this agent; a model cannot reach others.
    """
    started = time.monotonic()
    spec = (TOOLS if available is None else available).get(name)
    raw: dict[str, Any] = {}
    try:
        raw = parse_arguments(arguments)
        if spec is None:
            result, ok = {"error": "unknown_tool"}, False
        else:
            result, ok = spec.handler(spec.input_model.model_validate(raw), context), True
    except ValueError:  # bad JSON, failed validation or input the tool cannot use
        result, ok = {"error": "invalid_arguments"}, False
    elapsed_ms = round((time.monotonic() - started) * 1000)
    return ToolOutcome(name=name, input=raw, result=result, ok=ok, ms=elapsed_ms)
