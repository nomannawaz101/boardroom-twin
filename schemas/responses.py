"""Stage responses (plan section 7.1). Everything the page shows comes from these."""

from typing import Literal

from pydantic import BaseModel

from config import RunMode
from schemas.answers import SolutionArchitectAnswer
from schemas.board import BoardPlan, BoardRound, Verdict
from schemas.case_file import BoardFlags, CaseFile, Signal
from schemas.claims import Claim
from schemas.cost import CostEstimate, PhaseEffort
from schemas.revision import BidRound, Report, StopDecision
from schemas.state import TrackerItem
from schemas.step import StepRecord
from schemas.timeline import Schedule


class InputChecks(BaseModel):
    real_data: Literal["passed"] = "passed"
    injection: Literal["passed", "notice"]
    is_brief: bool


class DiscoverResponse(BaseModel):
    run_id: str
    mode: RunMode
    brief: str
    country_code: str
    checks: InputChecks
    notices: list[str]
    case_file: CaseFile
    flags: BoardFlags
    board_plan: BoardPlan
    ignored_signals: list[Signal]
    steps: list[StepRecord]


class BoardResponse(BaseModel):
    """One board round, the objection tracker and the seat steps (plan section 7.1)."""

    round: BoardRound
    tracker: list[TrackerItem]
    verdict: Verdict  # the verdict so far, by section 4.7; final after the last round
    stop: StopDecision  # whether code stops the loop here, and why
    steps: list[StepRecord]


class DraftResponse(BaseModel):
    design: SolutionArchitectAnswer
    efforts: list[PhaseEffort]
    estimate: CostEstimate | None
    schedule: Schedule | None
    claims: list[Claim]
    draft_no: int
    retagged: list[str]
    steps: list[StepRecord]


class RevisionResponse(BaseModel):
    """One Bid Manager round and one re-vote of every selected seat (plan section 7.1)."""

    bid_round: BidRound
    round: BoardRound
    claims: list[Claim]
    draft_no: int
    tracker: list[TrackerItem]
    verdict: Verdict
    stop: StopDecision
    steps: list[StepRecord]


class ReportResponse(BaseModel):
    report: Report
