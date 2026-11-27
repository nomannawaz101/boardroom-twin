"""Working days tool: pure code, cannot fail on valid dates."""

from collections.abc import Collection
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from tools.registry import ToolContext

NAME = "working_days"
SATURDAY = 5

SCHEMA: dict[str, object] = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Count working days (Monday to Friday, minus listed holidays) "
            "between two dates, both dates included."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "First day, YYYY-MM-DD"},
                "end": {"type": "string", "description": "Last day, YYYY-MM-DD"},
                "holidays": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Public holidays to skip, YYYY-MM-DD",
                },
            },
            "required": ["start", "end"],
        },
    },
}


def is_working_day(day: date, holidays: Collection[date] = ()) -> bool:
    return day.weekday() < SATURDAY and day not in holidays


def count_working_days(start: date, end: date, holidays: Collection[date] = ()) -> int:
    """Both ends are included; a reversed range has no working days."""
    span = (end - start).days + 1
    return sum(is_working_day(start + timedelta(days=i), holidays) for i in range(max(span, 0)))


def add_working_days(start: date, days: int, holidays: Collection[date] = ()) -> date:
    """Return the date that is `days` working days after `start` (start itself not counted)."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if is_working_day(current, holidays):
            remaining -= 1
    return current


class WorkingDaysInput(BaseModel):
    start: date
    end: date
    holidays: list[date] = []


def handle(request: WorkingDaysInput, context: "ToolContext") -> dict[str, Any]:
    total = count_working_days(request.start, request.end, set(request.holidays))
    return {"working_days": total}
