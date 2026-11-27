"""Seat registry (plan section 4.1). A new seat is one data entry here, not new code."""

from dataclasses import dataclass
from typing import Literal

SeatKind = Literal["scoring", "gate"]
# Which board flag decides whether the seat joins; the composer (Phase 2) applies the rule.
JoinRule = Literal["always", "existing_systems", "contract", "personal_data"]


@dataclass(frozen=True)
class Criterion:
    id: str
    label: str
    weight: float


@dataclass(frozen=True)
class ChecklistItem:
    id: str
    label: str
    must: bool


@dataclass(frozen=True)
class SeatSpec:
    id: str
    kind: SeatKind
    title: str
    join_rule: JoinRule
    criteria: tuple[Criterion, ...] = ()
    needed_score: float | None = None
    checklist: tuple[ChecklistItem, ...] = ()


SEATS: tuple[SeatSpec, ...] = (
    SeatSpec(
        id="cfo",
        kind="scoring",
        title="CFO",
        join_rule="always",
        needed_score=7.0,
        criteria=(
            Criterion("cost_clarity", "Cost clarity", 0.40),
            Criterion("value", "Value", 0.35),
            Criterion("budget_fit", "Budget fit", 0.25),
        ),
    ),
    SeatSpec(
        id="vp_director",
        kind="scoring",
        title="VP or Director",  # replaced per brief by the composer, e.g. "VP, Claims Operations"
        join_rule="always",
        needed_score=7.0,
        criteria=(
            Criterion("customer_benefit", "Customer benefit", 0.40),
            Criterion("timing", "Timing", 0.35),
            Criterion("disruption", "Disruption", 0.25),
        ),
    ),
    SeatSpec(
        id="enterprise_architect",
        kind="scoring",
        title="Enterprise Architect",
        join_rule="existing_systems",
        needed_score=8.0,
        criteria=(
            Criterion("system_fit", "Fit with our systems", 0.40),
            Criterion("risk_recovery", "Risk and recovery plan", 0.35),
            Criterion("maintainability", "Maintainability", 0.25),
        ),
    ),
    SeatSpec(
        id="procurement",
        kind="gate",
        title="Procurement & Contracts",
        join_rule="contract",
        checklist=(
            ChecklistItem("pricing_model", "Pricing model stated", must=True),
            ChecklistItem("change_control", "Change control", must=True),
            ChecklistItem("acceptance_payment", "Acceptance and payment terms", must=False),
        ),
    ),
    SeatSpec(
        id="security",
        kind="gate",
        title="Security Officer",
        join_rule="personal_data",
        checklist=(
            ChecklistItem("data_protection", "Data protection", must=True),
            ChecklistItem("access_control", "Access control", must=True),
            ChecklistItem("data_rules_fit", "Fit with the client's data rules", must=False),
        ),
    ),
)

SEATS_BY_ID: dict[str, SeatSpec] = {s.id: s for s in SEATS}
