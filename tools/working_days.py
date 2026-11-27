"""Working days tool: pure code, cannot fail on valid dates."""

from collections.abc import Collection
from datetime import date, timedelta

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


def run(start: str, end: str, holidays: list[str] | None = None) -> dict[str, int]:
    """Entry point for a model tool call; inputs arrive as ISO date strings."""
    holiday_dates = {date.fromisoformat(h) for h in holidays or []}
    total = count_working_days(date.fromisoformat(start), date.fromisoformat(end), holiday_dates)
    return {"working_days": total}
