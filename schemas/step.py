"""Step record: what one agent did. The screens and the run timeline are drawn from these."""

from typing import Any, Literal

from pydantic import BaseModel

from config import Tier

StepStatus = Literal["ok", "retried", "skipped", "failed", "not_reviewed"]
StepFlag = Literal["retried", "fallback_fast", "fixed_order", "skipped", "partial", "not_reviewed"]


class ToolCallRecord(BaseModel):
    tool: str
    input: dict[str, Any]
    result: dict[str, Any]
    ok: bool
    ms: int


class StepRecord(BaseModel):
    agent: str
    label: str
    tier: Tier
    model: str
    stage: int
    start_ms: int
    duration_ms: int
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    tool_calls: list[ToolCallRecord] = []
    flags: list[StepFlag] = []
    handoff_in: str = ""
    handoff_out: str = ""
    summary: str = ""
    status: StepStatus = "ok"
    attempts: int = 0
