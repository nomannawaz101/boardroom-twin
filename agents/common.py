"""Shared helpers for agent modules: prompts, the marked input block and step text."""

import json
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from guards.input import DATA_BLOCK_RULE, LANGUAGE_RULE
from schemas.step import StepRecord

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SHARED_PROMPT = "shared"
INPUTS_TAG = "inputs"


@cache
def read_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def system_prompt(agent_id: str, **values: object) -> str:
    """Shared opening (plan Appendix A) plus the agent's own rules and JSON shape.

    Placeholders are replaced by name, so the JSON examples' braces are left alone.
    """
    own = read_prompt(agent_id)
    for key, value in values.items():
        own = own.replace("{" + key + "}", str(value))
    return "\n\n".join([read_prompt(SHARED_PROMPT), DATA_BLOCK_RULE, LANGUAGE_RULE, own])


def inputs_block(payload: dict[str, Any]) -> str:
    """Inputs travel as JSON inside a marked block. `</` is escaped so no text can close it."""
    body = json.dumps(payload, default=str, ensure_ascii=False).replace("</", "<\\/")
    return f"<{INPUTS_TAG}>\n{body}\n</{INPUTS_TAG}>"


def dump(model: BaseModel | None) -> Any:  # noqa: ANN401 - JSON-ready value for inputs_block
    return model.model_dump(mode="json", exclude_none=True) if model is not None else None


def with_text(step: StepRecord, summary: str, handoff_in: str, handoff_out: str) -> StepRecord:
    """Summary and handoff lines are written by code from the result, never by a model."""
    return step.model_copy(
        update={"summary": summary, "handoff_in": handoff_in, "handoff_out": handoff_out}
    )


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"
