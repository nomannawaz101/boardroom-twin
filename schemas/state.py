"""Run state held by the browser (plan section 7.2). It never holds a key or a passcode.

Board plan, rounds and verdict get their own models when Phases 2 to 4 build them.
"""

from typing import Any, Literal

from pydantic import BaseModel

from config import RunMode
from schemas.answers import RiskAnalystAnswer, SolutionArchitectAnswer
from schemas.case_file import BoardFlags, CaseFile
from schemas.claims import Claim
from schemas.cost import CostEstimate
from schemas.step import StepRecord


class HistoryEntry(BaseModel):
    round: int
    state: Literal["resolved", "partly", "open"]


class TrackerItem(BaseModel):
    """One objection (O items: the proposal can fix) or condition (C items: only the client)."""

    id: str
    seat: str
    kind: Literal["O", "C"]
    severity: Literal["blocker", "condition"] = "blocker"
    item_id: str | None = None
    claim_ids: list[str] = []
    text: str
    status: Literal["open", "fixed"] = "open"
    raised_round: int
    history: list[HistoryEntry] = []


class RunState(BaseModel):
    run_id: str
    mode: RunMode
    brief: str
    case_file: CaseFile | None = None
    flags: BoardFlags | None = None
    board_plan: dict[str, Any] | None = None
    design: SolutionArchitectAnswer | None = None
    estimate: CostEstimate | None = None
    risks: RiskAnalystAnswer | None = None
    claims: list[Claim] = []
    draft_no: int = 0
    rounds: list[dict[str, Any]] = []
    tracker: list[TrackerItem] = []
    verdict: str | None = None
    steps: list[StepRecord] = []
