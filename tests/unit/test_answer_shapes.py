"""Count and length rules of the answer shapes (plan sections 7.2 and Appendix A).

They apply to a model's reply (run_agent passes the FROM_MODEL context), not to code-built
objects or the stored run state, so a safe default can still travel in the state.
"""

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import config
from llm.client import Runtime, run_agent
from llm.fake import FakeChatModel, reply_json
from schemas.answers import DeliveryManagerAnswer, ProposalManagerAnswer, SolutionArchitectAnswer
from schemas.common import FROM_MODEL
from schemas.state import RunState

STRICT = {FROM_MODEL: True}


def part(i: int) -> dict[str, str]:
    return {"name": f"Part {i}", "purpose": "does a thing"}


def design(parts: int, phases: int = 1) -> dict[str, Any]:
    return {
        "parts": [part(i) for i in range(parts)],
        "phases": [{"no": i + 1, "name": "Phase", "scope": []} for i in range(phases)],
    }


def claim(words: int = 5) -> dict[str, str]:
    return {"section": "scope", "text": " ".join(["word"] * words), "origin": "proposal"}


def strict(schema: type[BaseModel], value: dict[str, Any]) -> BaseModel:
    return schema.model_validate(value, context=STRICT)


# --- Solution Architect: 2 to 5 parts, 1 to 3 phases ---


def test_architect_needs_at_least_two_parts() -> None:
    with pytest.raises(ValidationError, match="needs at least 2 items, got 1"):
        strict(SolutionArchitectAnswer, design(parts=1))


def test_architect_needs_a_phase() -> None:
    with pytest.raises(ValidationError, match="phases"):
        strict(SolutionArchitectAnswer, design(parts=2, phases=0))


def test_architect_extra_parts_and_phases_are_cut_to_the_maximum() -> None:
    answer = strict(SolutionArchitectAnswer, design(parts=7, phases=4))
    assert len(answer.parts) == config.SA_PARTS[1]  # type: ignore[attr-defined]
    assert len(answer.phases) == config.SA_PHASES[1]  # type: ignore[attr-defined]


# --- Delivery Manager: at least one phase, each with engineers and weeks ---


def test_sizing_needs_a_phase() -> None:
    with pytest.raises(ValidationError, match="needs at least 1"):
        strict(DeliveryManagerAnswer, {"phases": []})


@pytest.mark.parametrize("phase", [{"engineers": 0, "weeks": 2}, {"engineers": 2, "weeks": 0}])
def test_sizing_refuses_zero_engineers_or_weeks(phase: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        strict(DeliveryManagerAnswer, {"phases": [{"no": 1} | phase]})


# --- Proposal Manager: at least 10 claims of at most 20 words ---


def test_draft_needs_the_minimum_number_of_claims() -> None:
    minimum = config.PM_TARGET_CLAIMS[0]
    with pytest.raises(ValidationError, match=f"needs at least {minimum}"):
        strict(ProposalManagerAnswer, {"claims": [claim()] * (minimum - 1)})
    strict(ProposalManagerAnswer, {"claims": [claim()] * minimum})


def test_a_claim_over_the_word_limit_fails_the_answer() -> None:
    claims = [claim()] * (config.PM_TARGET_CLAIMS[0] - 1) + [claim(config.CLAIM_MAX_WORDS + 1)]
    with pytest.raises(ValidationError, match="at most 20 words"):
        strict(ProposalManagerAnswer, {"claims": claims})


def test_extra_claims_are_cut_to_the_maximum() -> None:
    answer = strict(ProposalManagerAnswer, {"claims": [claim()] * 30})
    assert len(answer.claims) == config.PM_TARGET_CLAIMS[1]  # type: ignore[attr-defined]


# --- The rules bind model replies only ---


def test_code_built_objects_and_stored_state_are_not_held_to_reply_rules() -> None:
    assert SolutionArchitectAnswer.model_validate(design(parts=1)).parts
    state = RunState.model_validate(
        {"run_id": "r", "mode": "full", "brief": "b", "design": {"parts": []}}
    )
    assert state.design is not None and state.design.parts == []


def test_run_agent_retries_a_short_design_then_uses_the_default_with_a_flag() -> None:
    model = FakeChatModel([reply_json(design(parts=1))] * (config.JSON_RETRIES + 1))
    result = asyncio.run(
        run_agent(
            "solution_architect",
            "s",
            "u",
            SolutionArchitectAnswer,
            runtime=Runtime(model=model),
            default=SolutionArchitectAnswer(),
        )
    )
    assert result.answer == SolutionArchitectAnswer()
    assert result.step.status == "skipped" and "skipped" in result.step.flags
    reminders = [r.messages[-1]["content"] for r in model.requests[1:]]
    assert all("parts" in text for text in reminders)
    assert len(model.requests[-1].messages) == len(model.requests[1].messages)  # no pile-up


def test_run_agent_accepts_a_good_design_after_a_short_one() -> None:
    model = FakeChatModel([reply_json(design(parts=1)), reply_json(design(parts=3))])
    result = asyncio.run(
        run_agent(
            "solution_architect", "s", "u", SolutionArchitectAnswer, runtime=Runtime(model=model)
        )
    )
    assert result.answer is not None and len(result.answer.parts) == 3
    assert result.step.status == "retried"
