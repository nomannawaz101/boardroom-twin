import asyncio
from collections.abc import Iterator
from dataclasses import replace

import pytest
from pydantic import BaseModel

import config
from domain.errors import BudgetUsedUp
from llm.client import JSON_REMINDER, AgentResult, Runtime, extract_json, model_badge, run_agent
from llm.fake import FakeChatModel, FakeStep, fail, reply_json, reply_text, reply_tool
from llm.usage import cost_usd
from tools.registry import ToolContext

SONNET_AGENT = "solution_architect"
HAIKU_AGENT = "business_analyst"


class Answer(BaseModel):
    value: int


class SleepRecorder:
    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


def run(
    script: list[FakeStep],
    agent_id: str = SONNET_AGENT,
    tools: list[str] | None = None,
    default: Answer | None = None,
    **runtime_options: object,
) -> tuple[AgentResult[Answer], FakeChatModel, SleepRecorder]:
    model = FakeChatModel(script)
    sleeper = SleepRecorder()
    runtime = Runtime(model=model, sleep=sleeper, **runtime_options)  # type: ignore[arg-type]
    result = asyncio.run(
        run_agent(agent_id, "system", "user", Answer, tools, runtime=runtime, default=default)
    )
    return result, model, sleeper


# --- Normal answers and JSON repair ---


def test_good_answer_first_time() -> None:
    result, model, _ = run([reply_json({"value": 1})])
    step = result.step
    assert result.answer == Answer(value=1)
    assert (step.status, step.attempts, step.flags) == ("ok", 1, [])
    assert (step.agent, step.label, step.stage, step.tier) == (
        SONNET_AGENT,
        "Solution Architect",
        2,
        "sonnet",
    )
    assert step.model == "fake-main"
    assert (step.tokens_in, step.tokens_out) == (100, 50)
    assert step.cost_usd == cost_usd("sonnet", 100, 50)
    assert model.requests[0].json_mode is True
    assert model.requests[0].max_tokens == config.MAX_OUT_DEFAULT


def test_json_inside_text_and_fences_is_repaired() -> None:
    result, _, _ = run([reply_text('Here you go:\n```json\n{"value": 2}\n```\nThanks')])
    assert result.answer == Answer(value=2)
    assert result.step.status == "ok"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('```json\n{"value": 3}\n```', {"value": 3}),
        ('{"value": 4} trailing words', {"value": 4}),
        ("no json here", None),
        ('{"value": ', None),
    ],
)
def test_extract_json(text: str, expected: object) -> None:
    assert extract_json(text) == expected


def test_bad_json_is_retried_with_a_reminder() -> None:
    result, model, _ = run([reply_text("not json"), reply_json({"value": 5})])
    assert result.answer == Answer(value=5)
    assert (result.step.status, result.step.attempts, result.step.flags) == (
        "retried",
        2,
        ["retried"],
    )
    assert model.requests[1].messages[-1] == {"role": "user", "content": JSON_REMINDER}


def test_wrong_shape_counts_as_bad_json() -> None:
    result, _, _ = run([reply_json({"other": 1}), reply_json({"value": 6})])
    assert result.answer == Answer(value=6)
    assert result.step.status == "retried"


def test_bad_json_every_time_gives_the_safe_default() -> None:
    script: list[FakeStep] = [reply_text("nope")] * (config.JSON_RETRIES + 1)
    result, _, _ = run(script, default=Answer(value=0))
    assert result.answer == Answer(value=0)
    assert result.step.status == "skipped"
    assert "skipped" in result.step.flags
    assert result.step.attempts == config.JSON_RETRIES + 1


def test_skipped_without_a_default_gives_none() -> None:
    result, _, _ = run([reply_text("nope")] * (config.JSON_RETRIES + 1))
    assert result.answer is None
    assert result.step.status == "skipped"


# --- Truncation ---


def test_cut_off_answer_is_retried_with_a_higher_cap() -> None:
    result, model, _ = run([reply_text('{"value": ', "length"), reply_json({"value": 7})])
    assert result.answer == Answer(value=7)
    assert result.step.status == "retried"
    assert model.requests[1].max_tokens == config.MAX_OUT_DEFAULT * config.TRUNCATION_CAP_FACTOR


def test_cut_off_twice_is_never_accepted() -> None:
    script = [reply_text('{"value": 1}', "length"), reply_text('{"value": 1}', "length")]
    result, _, _ = run(script, default=Answer(value=0))
    assert result.answer == Answer(value=0)
    assert result.step.status == "skipped"


# --- Rate limits, errors and the fast fallback ---


def test_rate_limit_waits_with_a_doubling_backoff() -> None:
    script = [fail("rate_limit"), fail("rate_limit"), reply_json({"value": 8})]
    result, _, sleeper = run(script)
    assert result.answer == Answer(value=8)
    assert sleeper.waits == [config.RATE_LIMIT_BASE_WAIT_S, config.RATE_LIMIT_BASE_WAIT_S * 2]
    assert result.step.status == "retried"
    assert result.step.attempts == 3


def test_model_error_falls_back_to_the_fast_model_once() -> None:
    script = [fail("server"), fail("timeout"), reply_json({"value": 9})]
    result, model, sleeper = run(script)
    assert result.answer == Answer(value=9)
    assert [r.model for r in model.requests] == ["fake-main", "fake-main", "fake-fast"]
    assert sleeper.waits == [config.MODEL_ERROR_BASE_WAIT_S]
    assert "fallback_fast" in result.step.flags
    assert (result.step.tier, result.step.model) == ("haiku", "fake-fast")


def test_failure_after_the_fallback_is_failed_not_defaulted() -> None:
    script = [fail("server"), fail("server"), fail("server")]
    result, _, _ = run(script, default=Answer(value=0))
    assert result.answer is None
    assert result.step.status == "failed"
    assert result.step.attempts == 3


def test_fast_agent_does_not_claim_a_fallback() -> None:
    result, model, _ = run([fail("server"), fail("server"), reply_json({"value": 1})], HAIKU_AGENT)
    assert result.answer == Answer(value=1)
    assert "fallback_fast" not in result.step.flags
    assert {r.model for r in model.requests} == {"fake-fast"}


@pytest.mark.parametrize("kind", ["budget", "auth"])
def test_budget_or_key_error_raises_budget_used_up(kind: str) -> None:
    with pytest.raises(BudgetUsedUp):
        run([fail(kind)])  # type: ignore[arg-type]


def test_lite_mode_uses_the_fast_tier() -> None:
    result, model, _ = run([reply_json({"value": 1})], lite=True)
    assert model.requests[0].model == "fake-fast"
    assert result.step.tier == "haiku"


# --- Tool loop ---


def test_tool_round_trip_records_the_call_and_marks_the_result() -> None:
    args = {"start": "2026-12-07", "end": "2026-12-18"}
    script = [reply_tool("working_days", args), reply_json({"value": 10})]
    result, model, _ = run(script, tools=["working_days"])
    assert result.answer == Answer(value=10)
    record = result.step.tool_calls[0]
    assert (record.tool, record.input, record.result, record.ok) == (
        "working_days",
        args,
        {"working_days": 10},
        True,
    )
    assert model.requests[0].tools is not None and model.requests[0].json_mode is False
    tool_message = model.requests[1].messages[-1]
    assert tool_message["role"] == "tool"
    assert tool_message["content"] == '<tool_result>{"working_days": 10}</tool_result>'


def test_tool_rounds_are_capped() -> None:
    args = {"start": "2026-12-07", "end": "2026-12-08"}
    script: list[FakeStep] = [reply_tool("working_days", args)] * config.MAX_TOOL_ROUNDS
    script.append(reply_json({"value": 1}))
    result, model, _ = run(script, tools=["working_days"])
    assert result.answer == Answer(value=1)
    assert len(result.step.tool_calls) == config.MAX_TOOL_ROUNDS
    final = model.requests[config.MAX_TOOL_ROUNDS]
    assert final.tools is None and final.json_mode is True


def test_a_tool_that_was_not_offered_cannot_run() -> None:
    script = [reply_tool("cost_calculator", {"phases": [], "rate": 1}), reply_json({"value": 1})]
    result, _, _ = run(script, tools=["working_days"])
    record = result.step.tool_calls[0]
    assert (record.ok, record.result) == (False, {"error": "unknown_tool"})


def test_quote_checker_reads_the_brief_from_code_not_the_model() -> None:
    script = [reply_tool("quote_checker", {"quote": "budget is TIGHT"}), reply_json({"value": 1})]
    context = ToolContext(brief="Budget is tight this year.")
    result, _, _ = run(script, tools=["quote_checker"], tool_context=context)
    assert result.step.tool_calls[0].result == {"found": True}


# --- Timing ---


def test_step_timing_comes_from_the_run_clock() -> None:
    ticks: Iterator[float] = iter([10.0, 10.5, 12.0])
    result, _, _ = run([reply_json({"value": 1})], clock=lambda: next(ticks))
    assert (result.step.start_ms, result.step.duration_ms) == (500, 1500)


# --- Model badge: the model that answered, after any fallback ---

GATEWAY_MODELS = {"LITELLM_MODEL": "claude-sonnet-5-5", "LITELLM_MODEL_FAST": "claude-haiku-5-5"}


@pytest.mark.parametrize(
    ("model", "badge"),
    [
        ("claude-sonnet-5-5", "Sonnet"),
        ("claude-haiku-5-5", "Haiku"),
        ("provider/Claude-Haiku-5-5-20261101", "Haiku"),
        ("dev-model-x", "dev-model-x"),
    ],
)
def test_model_badge(model: str, badge: str) -> None:
    assert model_badge(model) == badge


def test_fallback_badge_names_the_fast_model_that_answered() -> None:
    result, _, _ = run([fail("server"), fail("server"), reply_json({"value": 1})])
    step = result.step
    assert (step.tier, step.model, step.badge) == ("haiku", "fake-fast", "fake-fast")
    assert "fallback_fast" in step.flags


def test_gateway_models_keep_the_tier_names_including_after_a_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in GATEWAY_MODELS.items():
        monkeypatch.setenv(name, value)
    normal, _, _ = run([reply_json({"value": 1})])
    assert (normal.step.model, normal.step.badge) == ("claude-sonnet-5-5", "Sonnet")
    fallback, _, _ = run([fail("server"), fail("server"), reply_json({"value": 1})])
    assert (fallback.step.model, fallback.step.badge) == ("claude-haiku-5-5", "Haiku")


def test_the_badge_follows_the_model_the_service_reports_not_the_one_asked_for() -> None:
    reply = replace(reply_json({"value": 1}), model="provider/claude-haiku-5-5-20261101")
    result, _, _ = run([reply])
    assert result.step.model == "provider/claude-haiku-5-5-20261101"
    assert result.step.badge == "Haiku"


def test_a_step_where_every_call_failed_names_the_last_model_tried() -> None:
    result, _, _ = run([fail("server")] * 3)
    assert (result.step.status, result.step.model, result.step.badge) == (
        "failed",
        "fake-fast",
        "fake-fast",
    )
