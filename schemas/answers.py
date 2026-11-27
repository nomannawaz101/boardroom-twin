"""JSON answer of each agent (plan sections 4.3 and 7.2). Unknown keys are ignored, lists capped.

Models never return a total, a vote, a cost or a verdict: code computes those.
"""

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, model_validator

import config
from schemas.claims import DraftClaim
from schemas.common import REQUIRED_ITEMS, at_least, capped, from_model, match_key

Short = capped(config.LIST_CAP_SHORT)
Medium = capped(config.LIST_CAP_MEDIUM)
Long = capped(config.LIST_CAP_LONG)


class Part(BaseModel):
    name: str
    purpose: str


class Integration(BaseModel):
    system: str
    how: str
    read_only: bool = True


class DesignPhase(BaseModel):
    no: int
    name: str
    scope: Annotated[list[str], Medium] = []


class SolutionArchitectAnswer(BaseModel):
    parts: Annotated[list[Part], capped(config.SA_PARTS[1]), at_least(config.SA_PARTS[0])] = []
    integrations: Annotated[list[Integration], Medium] = []
    phases: Annotated[
        list[DesignPhase], capped(config.SA_PHASES[1]), at_least(config.SA_PHASES[0])
    ] = []
    out_of_scope: Annotated[list[str], Medium] = []


class EffortPhase(BaseModel):
    no: int
    engineers: int = Field(ge=1)
    weeks: float = Field(gt=0)


class DeliveryManagerAnswer(BaseModel):
    phases: Annotated[list[EffortPhase], Short, at_least(config.DM_MIN_PHASES)] = []
    day_rate: float | None = None
    start: date | None = None
    notes: str = ""


class Evidence(BaseModel):
    tool: str | None = None
    quote: str | None = None


class Risk(BaseModel):
    kind: Literal["timing", "data", "delivery"]
    text: str
    evidence: Evidence = Evidence()


class RiskAnalystAnswer(BaseModel):
    risks: Annotated[list[Risk], Medium] = []


class ProposalManagerAnswer(BaseModel):
    claims: Annotated[
        list[DraftClaim], capped(config.PM_TARGET_CLAIMS[1]), at_least(config.PM_TARGET_CLAIMS[0])
    ] = []


class Change(BaseModel):
    objection_id: str
    action: Literal["replace", "remove", "add", "assume"]
    claim_id: str | None = None
    text: str = ""


class BidManagerAnswer(BaseModel):
    changes: Annotated[list[Change], Long] = []


class ClaimCheck(BaseModel):
    claim_id: str
    result: Literal["supported", "not_in_brief", "unsupported_detail"]
    note: str = ""


class QaReviewerAnswer(BaseModel):
    checks: Annotated[list[ClaimCheck], Long] = []


class PresalesLeadAnswer(BaseModel):
    questions: Annotated[list[str], Short] = []
    next_steps: Annotated[list[str], Short] = []


class ScreenPart(BaseModel):
    type: Literal["header", "input", "stepper", "cards", "table", "note"]
    props: dict[str, Any] = {}
    scope_item: str = ""


class UxDesignerAnswer(BaseModel):
    title: str
    parts: Annotated[list[ScreenPart], Medium] = []


# --- Board seats ---


class PreviousState(BaseModel):
    id: str
    state: Literal["resolved", "partly", "open"]


class Rating(BaseModel):
    criterion: str
    rating: float  # clamped to 0..10 by code, never trusted as given
    reason: str = ""


class ScoringObjection(BaseModel):
    claim_id: str | None = None
    text: str
    severity: Literal["blocker", "condition"] = "blocker"
    needs_client: bool = False
    resolve_hint: str = ""


class ScoringSeatAnswer(BaseModel):
    ratings: Annotated[list[Rating], Short] = []
    objections: Annotated[list[ScoringObjection], capped(config.SEAT_MAX_OBJECTIONS)] = []
    condition: str | None = None
    quote: str = ""
    previous: Annotated[list[PreviousState], Long] = []


class ChecklistAnswer(BaseModel):
    id: str
    status: Literal["met", "partly", "not_met"]
    reason: str = ""


class GateObjection(BaseModel):
    item_id: str
    text: str
    needs_client: bool = False
    resolve_hint: str = ""


class GateSeatAnswer(BaseModel):
    items: Annotated[list[ChecklistAnswer], Short] = []
    objections: Annotated[list[GateObjection], capped(config.SEAT_MAX_OBJECTIONS)] = []
    quote: str = ""
    previous: Annotated[list[PreviousState], Long] = []

    @model_validator(mode="after")
    def covers_the_checklist(self, info: ValidationInfo) -> "GateSeatAnswer":
        """A reply that leaves out a checklist item fails its check, so the seat is retried.
        A forgotten line must never become a gate outcome. The checklist comes from run_agent
        as a list of accepted keys (id and label) per item."""
        required: list[list[str]] = (info.context or {}).get(REQUIRED_ITEMS) or []
        if not from_model(info) or not required:
            return self
        answered = {match_key(item.id) for item in self.items}
        missing = [keys[0] for keys in required if not answered.intersection(keys)]
        if missing:
            raise ValueError(f"answer every checklist item; missing: {', '.join(missing)}")
        return self
