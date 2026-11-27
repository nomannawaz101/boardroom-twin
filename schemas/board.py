"""The board for one brief (plan section 4.2) and one round of its review (section 4.4).

Built by code. Models only rate criteria and answer checklist items; every score, vote and
gate outcome here was computed by code.
"""

from typing import Literal

from pydantic import BaseModel

from domain.seats import SeatKind

ScoringVote = Literal["approved", "yes_with_condition", "rejected"]
GateOutcome = Literal["pass", "pass_with_conditions", "blocked"]
ItemStatus = Literal["met", "partly", "not_met"]
SeatStatus = Literal["answered", "not_reviewed"]


class PlannedSeat(BaseModel):
    id: str
    kind: SeatKind
    title: str
    why: str


class SkippedSeat(BaseModel):
    id: str
    title: str
    why_not: str


class BoardPlan(BaseModel):
    seats: list[PlannedSeat]
    skipped: list[SkippedSeat]


class CriterionResult(BaseModel):
    id: str
    label: str
    weight: float
    rating: float | None  # clamped to 0..10 by code; None when the seat left it out
    reason: str = ""


class ChecklistResult(BaseModel):
    id: str
    label: str
    must: bool
    status: ItemStatus
    reason: str = ""
    answered: bool = True  # False when the seat left it out (counted as not met)


class SeatResult(BaseModel):
    seat_id: str
    kind: SeatKind
    title: str
    status: SeatStatus
    able: bool  # can proceed: not Rejected, not Blocked, not Not reviewed (rule 4.4.5)
    partial: bool = False
    criteria: list[CriterionResult] = []
    score: float | None = None
    needed: float | None = None
    vote: ScoringVote | None = None
    items: list[ChecklistResult] = []
    outcome: GateOutcome | None = None
    decision: str = ""  # the vote or outcome in words, written by code
    condition: str | None = None
    quote: str = ""


class Progress(BaseModel):
    able: int
    total: int


class BoardRound(BaseModel):
    no: int
    seats: list[SeatResult]
    progress: Progress
