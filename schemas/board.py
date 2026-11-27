"""The board chosen for one brief (plan section 4.2). Built by code, never by a model."""

from pydantic import BaseModel

from domain.seats import SeatKind


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
