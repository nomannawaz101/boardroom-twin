"""Stage responses (plan section 7.1). Everything the page shows comes from these."""

from typing import Literal

from pydantic import BaseModel

from config import RunMode
from schemas.answers import SolutionArchitectAnswer
from schemas.board import BoardPlan
from schemas.case_file import BoardFlags, CaseFile, Signal
from schemas.claims import Claim
from schemas.cost import CostEstimate, PhaseEffort
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


class DraftResponse(BaseModel):
    design: SolutionArchitectAnswer
    efforts: list[PhaseEffort]
    estimate: CostEstimate | None
    schedule: Schedule | None
    claims: list[Claim]
    draft_no: int
    retagged: list[str]
    steps: list[StepRecord]
