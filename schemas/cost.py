from pydantic import BaseModel


class PhaseEffort(BaseModel):
    no: int
    engineers: int
    weeks: float


class PhaseCost(BaseModel):
    no: int
    engineers: int
    days: float
    rate: float
    cost: float


class CostEstimate(BaseModel):
    phases: list[PhaseCost]
    engineer_days: float
    total: float
    currency: str
