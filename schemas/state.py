"""Run state held by the browser (plan section 7.2). It never holds a key or a passcode.

The verdict gets its own model when Phase 4 builds it.
"""

from typing import Literal

from pydantic import BaseModel

from config import RunMode
from schemas.answers import RiskAnalystAnswer, SolutionArchitectAnswer
from schemas.board import BoardPlan, BoardRound
from schemas.case_file import BoardFlags, CaseFile
from schemas.claims import Claim
from schemas.cost import CostEstimate
from schemas.step import StepRecord
from schemas.timeline import Schedule


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
    resolve_hint: str = ""  # what the seat says would resolve it; the Bid Manager reads this
    status: Literal["open", "fixed"] = "open"
    raised_round: int
    history: list[HistoryEntry] = []


class RunState(BaseModel):
    run_id: str
    mode: RunMode
    brief: str
    case_file: CaseFile | None = None
    flags: BoardFlags | None = None
    board_plan: BoardPlan | None = None
    design: SolutionArchitectAnswer | None = None
    estimate: CostEstimate | None = None
    schedule: Schedule | None = None
    risks: RiskAnalystAnswer | None = None
    claims: list[Claim] = []
    draft_no: int = 0
    rounds: list[BoardRound] = []
    tracker: list[TrackerItem] = []
    verdict: str | None = None
    steps: list[StepRecord] = []
