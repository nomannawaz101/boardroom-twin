"""Working days tool: pure code, cannot fail on valid dates. The maths lives in domain/timeline."""

from datetime import date
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from domain.timeline import count_working_days

if TYPE_CHECKING:
    from tools.registry import ToolContext

NAME = "working_days"

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


class WorkingDaysInput(BaseModel):
    start: date
    end: date
    holidays: list[date] = []


def handle(request: WorkingDaysInput, context: "ToolContext") -> dict[str, Any]:
    total = count_working_days(request.start, request.end, set(request.holidays))
    return {"working_days": total}
