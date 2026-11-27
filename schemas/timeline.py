from datetime import date

from pydantic import BaseModel


class PhaseDates(BaseModel):
    no: int
    start: date
    end: date
    working_days: int


class Schedule(BaseModel):
    """Dates built by code from working days. Public holidays join in Phase 5."""

    start: date
    go_live: date
    phases: list[PhaseDates]
    holidays_checked: bool = False
