"""run_agent: one agent call with checked JSON, retries, fallbacks, a capped tool loop and a step
record. Every fallback leaves a flag on the step record; nothing degrades silently.

Policy (numbers in config.py):
- invalid JSON: retried JSON_RETRIES times, then the caller's safe default, status `skipped`;
- cut-off answer (finish reason "length"): retried once with a higher cap, then `skipped`;
- rate limit (429): wait and retry with a doubling wait;
- other model errors: retry with a growing wait, then once on the fast tier, then `failed`;
- budget or key errors: BudgetUsedUp is raised so the stage can switch to Sample;
- tools: at most MAX_TOOL_ROUNDS rounds, then the model must answer without tools.
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ValidationError

import config
from agents.registry import get_agent
from domain.errors import BudgetUsedUp
from llm.usage import cost_usd
from schemas.common import FROM_MODEL
from schemas.step import StepFlag, StepRecord, StepStatus, ToolCallRecord
from tools.registry import TOOLS, ToolContext, ToolOutcome, run_tool

ErrorKind = Literal["rate_limit", "server", "timeout", "budget", "auth", "bad_request"]
FENCE = "```"
JSON_REMINDER = (
    "Your last reply was not valid JSON in the requested shape. Reply with only that JSON."
)
TOOL_RESULT_TAG = "tool_result"


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ChatRequest:
    model: str
    messages: list[dict[str, Any]]
    max_tokens: int
    tools: list[dict[str, object]] | None
    json_mode: bool


@dataclass(frozen=True)
class ChatReply:
    content: str
    tool_calls: list[ToolCall]
    finish_reason: str | None
    tokens_in: int
    tokens_out: int
    assistant_message: dict[str, Any]
    model: str = ""  # the model the service says answered; empty if it did not say


class ModelCallError(Exception):
    """A failed model call, classified so the retry policy can react. Carries no reply text."""

    def __init__(self, kind: ErrorKind) -> None:
        super().__init__(kind)
        self.kind = kind


class AllCallsFailed(Exception):
    """Every retry and the fast-tier fallback failed."""


class ChatModel(Protocol):
    async def complete(self, request: ChatRequest) -> ChatReply: ...


@dataclass
class Runtime:
    """What run_agent needs from outside; tests swap in the fake model, a clock and a sleeper."""

    model: ChatModel
    lite: bool = False
    tool_context: ToolContext = field(default_factory=ToolContext)
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    clock: Callable[[], float] = time.monotonic
    started_at: float | None = None

    def __post_init__(self) -> None:
        if self.started_at is None:
            self.started_at = self.clock()

    def elapsed_ms(self) -> int:
        return round((self.clock() - (self.started_at or 0.0)) * 1000)


@dataclass(frozen=True)
class AgentResult[T: BaseModel]:
    answer: T | None
    step: StepRecord


@dataclass
class CallState:
    """Running totals for one agent across all its model calls."""

    tier: config.Tier
    cap: int
    attempts: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    on_fallback: bool = False
    answered_by: str = ""
    flags: list[StepFlag] = field(default_factory=list)
    tool_records: list[ToolCallRecord] = field(default_factory=list)

    def flag(self, name: StepFlag) -> None:
        if name not in self.flags:
            self.flags.append(name)

    def add_reply(self, reply: ChatReply, requested: str) -> None:
        """Usage at the price of the tier that answered, and which model it was."""
        self.tokens_in += reply.tokens_in
        self.tokens_out += reply.tokens_out
        self.cost += cost_usd(self.tier, reply.tokens_in, reply.tokens_out)
        self.answered_by = reply.model or requested


def model_badge(model: str) -> str:
    """The badge on an agent card: a tier name only when the model really is one of that family
    (the judged gateway); otherwise the model's own name, so a development model is never
    shown as Sonnet or Haiku."""
    lowered = model.lower()
    family = next((label for word, label in config.TIER_LABELS.items() if word in lowered), None)
    return family or model


def extract_json(text: str) -> object | None:
    """Find the JSON object in a reply, tolerating code fences and text around it."""
    body = text.strip()
    if body.startswith(FENCE):
        body = body.removeprefix(FENCE).removeprefix("json").rsplit(FENCE, 1)[0].strip()
    start = body.find("{")
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(body[start:])
    except json.JSONDecodeError:
        return None
    return value


def problem_list(error: ValidationError) -> list[str]:
    """Where the reply broke the shape, for the retry message. Field paths and rule messages
    only; the reply's own values are never repeated."""
    problems = [".".join(str(part) for part in e["loc"]) + ": " + e["msg"] for e in error.errors()]
    return problems[: config.MAX_REPLY_PROBLEMS]


def parse_answer[T: BaseModel](text: str, schema: type[T]) -> tuple[T | None, list[str]]:
    """Check a model's reply. FROM_MODEL turns on the count and length rules of the answer
    shapes, which code-built objects and the stored run state do not have to meet."""
    value = extract_json(text)
    if not isinstance(value, dict):
        return None, []
    try:
        return schema.model_validate(value, context={FROM_MODEL: True}), []
    except ValidationError as error:
        return None, problem_list(error)


def reminder(problems: list[str]) -> dict[str, Any]:
    content = JSON_REMINDER if not problems else f"{JSON_REMINDER} Fix: {'; '.join(problems)}."
    return {"role": "user", "content": content}


def with_reminder(messages: list[dict[str, Any]], problems: list[str]) -> list[dict[str, Any]]:
    """One reminder at a time: a newer one replaces the last, so retries do not pile up."""
    last = messages[-1] if messages else {}
    keep = messages[:-1] if str(last.get("content", "")).startswith(JSON_REMINDER) else messages
    return [*keep, reminder(problems)]


def tool_message(call: ToolCall, outcome: ToolOutcome) -> dict[str, Any]:
    """Tool output goes back inside a marked block: it is data, never instructions."""
    payload = json.dumps(outcome.result)
    return {
        "role": "tool",
        "tool_call_id": call.id,
        "content": f"<{TOOL_RESULT_TAG}>{payload}</{TOOL_RESULT_TAG}>",
    }


def run_tool_calls(
    calls: list[ToolCall], offered: list[str], state: CallState, runtime: Runtime
) -> list[dict[str, Any]]:
    available = {name: TOOLS[name] for name in offered}
    messages = []
    for call in calls:
        outcome = run_tool(call.name, call.arguments, runtime.tool_context, available)
        state.tool_records.append(
            ToolCallRecord(
                tool=call.name,
                input=outcome.input,
                result=outcome.result,
                ok=outcome.ok,
                ms=outcome.ms,
            )
        )
        messages.append(tool_message(call, outcome))
    return messages


async def call_model(
    state: CallState, messages: list[dict[str, Any]], tools: list[str] | None, runtime: Runtime
) -> ChatReply:
    """One model reply, with waits, retries and the single fast-tier fallback."""
    rate_waits = 0
    errors = 0
    schemas = [TOOLS[name].schema for name in tools] if tools else None
    while True:
        request = ChatRequest(
            model=config.model_for_tier(state.tier),
            messages=list(messages),
            max_tokens=state.cap,
            tools=schemas,
            json_mode=schemas is None,
        )
        state.attempts += 1
        try:
            reply = await runtime.model.complete(request)
        except ModelCallError as error:
            if error.kind in ("budget", "auth"):
                raise BudgetUsedUp() from error
            if error.kind == "rate_limit" and rate_waits < config.RATE_LIMIT_RETRIES:
                await runtime.sleep(config.RATE_LIMIT_BASE_WAIT_S * 2**rate_waits)
                rate_waits += 1
            elif errors < config.MODEL_ERROR_RETRIES:
                await runtime.sleep(config.MODEL_ERROR_BASE_WAIT_S * 2**errors)
                errors += 1
            elif not state.on_fallback:
                state.on_fallback = True
                if state.tier != config.FAST_TIER:
                    state.tier = config.FAST_TIER
                    state.flag("fallback_fast")
            else:
                raise AllCallsFailed() from error
            state.flag("retried")
            continue
        state.add_reply(reply, request.model)
        return reply


async def answer_loop[T: BaseModel](
    state: CallState,
    messages: list[dict[str, Any]],
    schema: type[T],
    tools: list[str] | None,
    runtime: Runtime,
) -> tuple[T | None, StepStatus]:
    json_failures = 0
    truncated = False
    tool_rounds = 0
    while True:
        offered = tools if tools and tool_rounds < config.MAX_TOOL_ROUNDS else None
        reply = await call_model(state, messages, offered, runtime)
        if offered and reply.tool_calls:
            tool_rounds += 1
            tool_messages = run_tool_calls(reply.tool_calls, offered, state, runtime)
            messages = [*messages, reply.assistant_message, *tool_messages]
            continue
        if reply.finish_reason == "length":
            if truncated:
                return None, "skipped"
            truncated = True
            state.cap *= config.TRUNCATION_CAP_FACTOR
            state.flag("retried")
            continue
        answer, problems = parse_answer(reply.content, schema)
        if answer is not None:
            return answer, "retried" if "retried" in state.flags else "ok"
        json_failures += 1
        if json_failures > config.JSON_RETRIES:
            return None, "skipped"
        messages = with_reminder(messages, problems)
        state.flag("retried")


async def run_agent[T: BaseModel](
    agent_id: str,
    system: str,
    user: str,
    schema: type[T],
    tools: list[str] | None = None,
    *,
    runtime: Runtime,
    default: T | None = None,
) -> AgentResult[T]:
    """Run one agent and return its checked answer plus the step record for the screens.

    On `skipped` the answer is the caller's safe default; on `failed` it is None.
    """
    spec = get_agent(agent_id)
    state = CallState(
        tier=config.FAST_TIER if runtime.lite else spec.tier, cap=config.max_out(agent_id)
    )
    start_ms = runtime.elapsed_ms()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        answer, status = await answer_loop(state, messages, schema, tools, runtime)
    except AllCallsFailed:
        answer, status = None, "failed"
    if status == "skipped":
        answer = default
        state.flag("skipped")
    # If no call answered at all, name the model that was tried last.
    answered = state.answered_by or config.model_for_tier(state.tier)
    step = StepRecord(
        agent=spec.id,
        label=spec.label,
        tier=state.tier,
        model=answered,
        badge=model_badge(answered),
        stage=spec.stage,
        start_ms=start_ms,
        duration_ms=runtime.elapsed_ms() - start_ms,
        tokens_in=state.tokens_in,
        tokens_out=state.tokens_out,
        cost_usd=round(state.cost, config.COST_DECIMALS),
        tool_calls=state.tool_records,
        flags=state.flags,
        status=status,
        attempts=state.attempts,
    )
    return AgentResult(answer=answer, step=step)
