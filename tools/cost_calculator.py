"""Cost calculator tool: people x days x rate, per phase and total. Pure code, cannot fail."""

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from domain.cost import PhaseDays, price_phases

if TYPE_CHECKING:
    from tools.registry import ToolContext

NAME = "cost_calculator"
DEFAULT_CURRENCY = "USD"

SCHEMA: dict[str, object] = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": "Cost of each phase (people x working days x day rate) and the total.",
        "parameters": {
            "type": "object",
            "properties": {
                "phases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "no": {"type": "integer", "description": "Phase number"},
                            "people": {"type": "integer", "description": "Engineers"},
                            "days": {"type": "number", "description": "Working days"},
                        },
                        "required": ["no", "people", "days"],
                    },
                },
                "rate": {"type": "number", "description": "Day rate per engineer"},
                "currency": {"type": "string", "description": "ISO code, e.g. USD"},
            },
            "required": ["phases", "rate"],
        },
    },
}


class PhaseInput(BaseModel):
    no: int
    people: int = Field(gt=0)
    days: float = Field(gt=0)


class CostInput(BaseModel):
    phases: list[PhaseInput] = Field(min_length=1)
    rate: float = Field(gt=0)
    currency: str = DEFAULT_CURRENCY


def handle(request: CostInput, context: "ToolContext") -> dict[str, Any]:
    phases = [PhaseDays(p.no, p.people, p.days) for p in request.phases]
    estimate = price_phases(phases, request.rate, request.currency)
    return {
        "phases": [{"no": p.no, "cost": p.cost} for p in estimate.phases],
        "engineer_days": estimate.engineer_days,
        "total": estimate.total,
        "currency": estimate.currency,
    }
