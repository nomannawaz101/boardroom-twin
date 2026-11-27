"""JSON answer of each agent (plan sections 4.3 and 7.2). Unknown keys are ignored, lists capped.

Models never return a total, a vote, a cost or a verdict: code computes those.
"""

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel

import config
from schemas.claims import DraftClaim
from schemas.common import capped

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
    parts: Annotated[list[Part], Medium] = []
    integrations: Annotated[list[Integration], Medium] = []
    phases: Annotated[list[DesignPhase], Short] = []
    out_of_scope: Annotated[list[str], Medium] = []


class EffortPhase(BaseModel):
    no: int
    engineers: int
    weeks: float


class DeliveryManagerAnswer(BaseModel):
    phases: Annotated[list[EffortPhase], Short] = []
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
    claims: Annotated[list[DraftClaim], Long] = []


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
    objections: Annotated[list[ScoringObjection], Short] = []
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
    objections: Annotated[list[GateObjection], Short] = []
    quote: str = ""
    previous: Annotated[list[PreviousState], Long] = []
