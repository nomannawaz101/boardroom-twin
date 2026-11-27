"""Claims: code assigns ids, builds the calculated claims and keeps them locked.

A model can never edit a calculated claim; every rebuild recreates them from the numbers.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

import config
from schemas.answers import Change
from schemas.claims import Claim, DraftClaim, Section
from schemas.cost import CostEstimate
from schemas.timeline import Schedule

CLAIM_PREFIX = "C"
ASSUMPTION_PREFIX = "Confirm with the client: "
COST_SECTION: Section = "team_cost"
TIMELINE_SECTION: Section = "timeline"
DEFAULT_ADD_SECTION: Section = "proposed_solution"
MISSING_COST = "the day rate and team size, so the cost can be calculated."
MISSING_START = "the start date, so the dates can be calculated."
HOLIDAYS_NOT_CHECKED = "the dates count weekends only; local public holidays are not checked yet."

RefusalReason = Literal["locked", "unknown_claim"]
CalculatedText = tuple[Section, str]


@dataclass(frozen=True)
class ChangeOutcome:
    claims: list[Claim]
    refused: RefusalReason | None = None


def format_number(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.{config.MONEY_DECIMALS}f}"


def format_money(amount: float, currency: str) -> str:
    symbol = config.CURRENCY_SYMBOLS.get(currency)
    number = format_number(amount)
    return f"{symbol}{number}" if symbol else f"{number} {currency}"


def claim_number(claim_id: str) -> int:
    digits = claim_id.removeprefix(CLAIM_PREFIX)
    return int(digits) if digits.isdigit() else 0


def next_claim_id(claims: list[Claim]) -> str:
    return f"{CLAIM_PREFIX}{max((claim_number(c.id) for c in claims), default=0) + 1}"


def format_date(day: date) -> str:
    return f"{day:%a %b} {day.day}, {day.year}"


def cost_texts(estimate: CostEstimate) -> list[CalculatedText]:
    """One sentence per phase plus the total, all built from code-computed numbers."""
    money = estimate.currency
    texts: list[CalculatedText] = [
        (
            COST_SECTION,
            f"Phase {p.no}: {p.engineers} engineers x {format_number(p.days)} days x "
            f"{format_money(p.rate, money)} = {format_money(p.cost, money)}.",
        )
        for p in estimate.phases
    ]
    total = (
        f"Total: {format_number(estimate.engineer_days)} engineer-days, "
        f"{format_money(estimate.total, money)}."
    )
    return [*texts, (COST_SECTION, total)]


def schedule_texts(schedule: Schedule) -> list[CalculatedText]:
    texts: list[CalculatedText] = [
        (
            TIMELINE_SECTION,
            f"Phase {p.no}: {format_date(p.start)} to {format_date(p.end)} "
            f"({p.working_days} working days).",
        )
        for p in schedule.phases
    ]
    working_days = sum(p.working_days for p in schedule.phases)
    go_live = (
        f"Go-live: {format_date(schedule.go_live)}, "
        f"{working_days} working days after the start on {format_date(schedule.start)}."
    )
    return [*texts, (TIMELINE_SECTION, go_live)]


def calculated_texts(
    estimate: CostEstimate | None, schedule: Schedule | None
) -> list[CalculatedText]:
    cost = cost_texts(estimate) if estimate is not None else []
    dates = schedule_texts(schedule) if schedule is not None else []
    return [*cost, *dates]


def code_assumptions(estimate: CostEstimate | None, schedule: Schedule | None) -> list[str]:
    """Gaps that code knows about, so they appear as TO CONFIRM instead of being guessed."""
    gaps = []
    if estimate is None:
        gaps.append(MISSING_COST)
    if schedule is None:
        gaps.append(MISSING_START)
    elif not schedule.holidays_checked:
        gaps.append(HOLIDAYS_NOT_CHECKED)
    return gaps


def locked_claim(claim_id: str, section: Section, text: str) -> Claim:
    return Claim(id=claim_id, section=section, text=text, origin="calculated", locked=True)


def assumption_claim(claim_id: str, text: str) -> Claim:
    return Claim(
        id=claim_id, section="assumptions", text=ASSUMPTION_PREFIX + text, origin="assumption"
    )


def assemble_claims(
    drafts: list[DraftClaim], estimate: CostEstimate | None, schedule: Schedule | None = None
) -> list[Claim]:
    """Number the model's claims, then add code's assumptions and the locked calculated claims.

    A model cannot mark its own text as calculated, so such a claim becomes `derived`.
    """
    claims: list[Claim] = []
    for draft in drafts:
        origin = "derived" if draft.origin == "calculated" else draft.origin
        claim = Claim(
            id=next_claim_id(claims),
            section=draft.section,
            text=draft.text,
            origin=origin,
            quote=draft.quote,
        )
        claims.append(claim)
    for gap in code_assumptions(estimate, schedule):
        claims.append(assumption_claim(next_claim_id(claims), gap))
    for section, text in calculated_texts(estimate, schedule):
        claims.append(locked_claim(next_claim_id(claims), section, text))
    return claims


def rebuild_calculated(
    claims: list[Claim], estimate: CostEstimate | None, schedule: Schedule | None = None
) -> list[Claim]:
    """Recreate every calculated claim from the numbers, keeping existing ids where possible."""
    texts = iter(calculated_texts(estimate, schedule))
    rebuilt: list[Claim] = []
    for claim in claims:
        if claim.origin != "calculated":
            rebuilt.append(claim)
            continue
        item = next(texts, None)
        if item is not None:
            rebuilt.append(locked_claim(claim.id, *item))
    for section, text in texts:
        rebuilt.append(locked_claim(next_claim_id(rebuilt), section, text))
    return rebuilt


def find_claim(claims: list[Claim], claim_id: str | None) -> Claim | None:
    return next((c for c in claims if c.id == claim_id), None)


def apply_change(claims: list[Claim], change: Change) -> ChangeOutcome:
    """Apply one Bid Manager change. Locked claims and unknown ids are refused, never edited."""
    target = find_claim(claims, change.claim_id)
    if change.action in ("replace", "remove"):
        if target is None:
            return ChangeOutcome(claims, refused="unknown_claim")
        if target.locked:
            return ChangeOutcome(claims, refused="locked")
        if change.action == "remove":
            return ChangeOutcome([c for c in claims if c.id != target.id])
        updated = target.model_copy(
            update={"text": change.text, "origin": "proposal", "quote": None}
        )
        return ChangeOutcome([updated if c.id == target.id else c for c in claims])
    return ChangeOutcome([*claims, new_claim(claims, change, target)])


def new_claim(claims: list[Claim], change: Change, near: Claim | None) -> Claim:
    if change.action == "assume":
        text = change.text.removeprefix(ASSUMPTION_PREFIX)
        return Claim(
            id=next_claim_id(claims),
            section="assumptions",
            text=ASSUMPTION_PREFIX + text,
            origin="assumption",
        )
    section = near.section if near is not None else DEFAULT_ADD_SECTION
    return Claim(id=next_claim_id(claims), section=section, text=change.text, origin="proposal")
