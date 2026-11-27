"""Claims: code assigns ids, builds the calculated claims and keeps them locked.

A model can never edit a calculated claim; every rebuild recreates them from the numbers.
"""

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal, get_args

import config
from domain.cost import weeks_to_days
from schemas.answers import Change
from schemas.claims import Claim, DraftClaim, Section
from schemas.cost import CostEstimate, PhaseEffort
from schemas.timeline import Schedule

CLAIM_PREFIX = "C"
ASSUMPTION_PREFIX = "Confirm with the client: "
COST_SECTION: Section = "team_cost"
TIMELINE_SECTION: Section = "timeline"
DEFAULT_ADD_SECTION: Section = "proposed_solution"
MISSING_COST = "the day rate and team size, so the cost can be calculated."
MISSING_START = "the start date, so the dates can be calculated."
HOLIDAYS_NOT_CHECKED = "the dates count weekends only; local public holidays are not checked yet."
DURATION_TEXT = (
    "Duration: {weeks} ({days} working days) from the start date. Start date to confirm."
)
EFFORT_TEXT = "Effort: {engineer_days} engineer-days over {phases}. Cost to confirm: no day rate."
NOT_DRAFTED = "{section} is not drafted yet."
SECTION_TITLES: dict[Section, str] = {
    "executive_summary": "Executive summary",
    "client_situation": "Client situation",
    "proposed_solution": "Proposed solution",
    "scope": "Scope",
    "timeline": "Timeline and milestones",
    "team_cost": "Team and cost",
    "risks": "Risks and mitigations",
    "assumptions": "Assumptions",
    "next_steps": "Next steps",
}

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


def phase_days(estimate: CostEstimate | None, efforts: list[PhaseEffort]) -> list[float]:
    """Working days per phase: the cost calculator's locked days, else the sized weeks."""
    if estimate is not None:
        return [p.days for p in estimate.phases]
    return [weeks_to_days(e.weeks) for e in efforts]


def duration_texts(days: list[float]) -> list[CalculatedText]:
    """Without a start date the dates stay TO CONFIRM, but the duration is still known."""
    working_days = sum(max(math.ceil(d), 1) for d in days)
    weeks = working_days / config.WORKING_DAYS_PER_WEEK
    unit = "week" if weeks == 1 else "weeks"
    shown = f"{round(weeks, config.WEEKS_DECIMALS):g}"
    text = DURATION_TEXT.format(weeks=f"{shown} {unit}", days=working_days)
    return [(TIMELINE_SECTION, text)]


def effort_texts(efforts: list[PhaseEffort]) -> list[CalculatedText]:
    """Without a day rate the cost stays TO CONFIRM, but the effort is still known."""
    engineer_days = sum(e.engineers * weeks_to_days(e.weeks) for e in efforts)
    phases = f"{len(efforts)} phase" + ("" if len(efforts) == 1 else "s")
    text = EFFORT_TEXT.format(engineer_days=format_number(engineer_days), phases=phases)
    return [(COST_SECTION, text)]


def calculated_texts(
    estimate: CostEstimate | None,
    schedule: Schedule | None,
    efforts: list[PhaseEffort] | None = None,
) -> list[CalculatedText]:
    """Every code-made claim, from the locked numbers. The wording lives only in this module."""
    sized = efforts or []
    if estimate is not None:
        cost = cost_texts(estimate)
    else:
        cost = effort_texts(sized) if sized else []
    if schedule is not None:
        dates = schedule_texts(schedule)
    else:
        days = phase_days(estimate, sized)
        dates = duration_texts(days) if days else []
    return [*cost, *dates]


def not_drafted_claim(claim_id: str, section: Section) -> Claim:
    text = ASSUMPTION_PREFIX + NOT_DRAFTED.format(section=SECTION_TITLES[section].lower())
    return Claim(id=claim_id, section=section, text=text, origin="assumption")


def fill_empty_sections(claims: list[Claim]) -> list[Claim]:
    """No section of a draft is ever empty: a gap becomes a TO CONFIRM line written by code."""
    filled = list(claims)
    for section in get_args(Section):
        if not any(c.section == section for c in filled):
            filled.append(not_drafted_claim(next_claim_id(filled), section))
    return filled


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
    drafts: list[DraftClaim],
    estimate: CostEstimate | None,
    schedule: Schedule | None = None,
    efforts: list[PhaseEffort] | None = None,
) -> list[Claim]:
    """Number the model's claims, then add code's assumptions, the locked calculated claims
    and, for any section still empty, a TO CONFIRM line.

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
    for section, text in calculated_texts(estimate, schedule, efforts):
        claims.append(locked_claim(next_claim_id(claims), section, text))
    return fill_empty_sections(claims)


def rebuild_calculated(
    claims: list[Claim],
    estimate: CostEstimate | None,
    schedule: Schedule | None = None,
    efforts: list[PhaseEffort] | None = None,
) -> list[Claim]:
    """Recreate every calculated claim from the numbers, keeping existing ids where possible."""
    texts = iter(calculated_texts(estimate, schedule, efforts))
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
