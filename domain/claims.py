"""Claims: code assigns ids, builds the calculated claims and keeps them locked.

A model can never edit a calculated claim; every rebuild recreates them from the numbers.
"""

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal, get_args

import config
from domain.cost import weeks_to_days
from schemas.answers import Change
from schemas.claims import ASSUMPTION_PREFIX, Claim, DraftClaim, Section
from schemas.cost import CostEstimate, PhaseEffort
from schemas.timeline import Schedule

CLAIM_PREFIX = "C"
# The on-screen tags (plan section 7.2). Recommendations carry no tag.
ORIGIN_TAGS: dict[str, str] = {
    "brief": "FROM BRIEF",
    "calculated": "CALCULATED",
    "assumption": "TO CONFIRM",
}
COST_SECTION: Section = "team_cost"
TIMELINE_SECTION: Section = "timeline"
DEFAULT_ADD_SECTION: Section = "proposed_solution"
PROTECTED_ORIGINS = ("brief", "calculated")
PROTECTED_SECTIONS: tuple[Section, ...] = ("team_cost", "timeline")
NOT_WORD_OR_SPACE = re.compile(r"[^\w\s]")
# Contract type, rate, price, cost, team size and dates. Payment and acceptance terms are not
# in the list: they are proposal clauses the board can ask for.
COMMERCIAL_FACT = re.compile(
    r"fixed[- ]price|time[- ]and[- ]materials|\bt&m\b|not[- ]to[- ]exceed|\bprice\b|\bpricing\b"
    r"|\bcosts?\b|\bbudget\b|\brate\b|\bcap\b|\bcapped\b|\bfee\b|\bcontract type\b"
    r"|[$€£]\s?\d|\b\d[\d,.]*\s?(?:usd|eur|gbp|k)\b|\bengineers?\b|\bheadcount\b|\bfte\b"
    r"|\bteam size\b|engineer-days?|\bweeks?\b|working days|\bgo-live\b|\bstart date\b"
    r"|\bdeadline\b|\b(?:jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b"
    r"|\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b"
    r"|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
MISSING_COST = "the day rate and team size, so the cost can be calculated."
MISSING_START = "the start date, so the dates can be calculated."
HOLIDAYS_NOT_CHECKED = "the dates count weekdays only; public holidays are not checked yet."
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

RefusalReason = Literal["locked", "unknown_claim", "protected", "duplicate"]
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
        if origin == "assumption" and has_assumption(claims, draft.text):
            continue  # the same assumption once is enough
        claim = Claim(
            id=next_claim_id(claims),
            section=draft.section,
            text=draft.text,
            origin=origin,
            quote=draft.quote,
        )
        claims.append(claim)
    for gap in code_assumptions(estimate, schedule):
        if not has_assumption(claims, gap):
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


def normalize_text(text: str) -> str:
    """For spotting near-identical texts: lower case, no punctuation, no "Confirm with the
    client:" prefix, single spaces."""
    plain = text.strip().removeprefix(ASSUMPTION_PREFIX.strip()).lower()
    plain = plain.removeprefix(ASSUMPTION_PREFIX.strip().lower())
    return " ".join(NOT_WORD_OR_SPACE.sub(" ", plain).split())


def states_commercial_fact(text: str) -> bool:
    """True when a sentence is about contract type, rate, price, cost, team size or dates."""
    return COMMERCIAL_FACT.search(text) is not None


def is_protected(claim: Claim) -> bool:
    """Claims the Bid Manager may never replace or remove: the client's own facts, code's
    numbers, and anything about the commercial terms or the dates."""
    return (
        claim.locked
        or claim.origin in PROTECTED_ORIGINS
        or claim.section in PROTECTED_SECTIONS
        or states_commercial_fact(claim.text)
    )


def has_assumption(claims: list[Claim], text: str) -> bool:
    wanted = normalize_text(text)
    return any(c.origin == "assumption" and normalize_text(c.text) == wanted for c in claims)


def apply_change(
    claims: list[Claim], change: Change, fallback: Section | None = None
) -> ChangeOutcome:
    """Apply one Bid Manager change. Locked, protected and unknown claims are refused, never
    edited; commercial facts can only arrive as an assumption ("Confirm with the client: ...").
    `fallback` is the section of the claim the objection points to, for an added statement."""
    target = find_claim(claims, change.claim_id)
    if change.action in ("replace", "remove"):
        if target is None:
            return ChangeOutcome(claims, refused="unknown_claim")
        if target.locked:
            return ChangeOutcome(claims, refused="locked")
        if is_protected(target):
            return ChangeOutcome(claims, refused="protected")
    if change.action in ("replace", "add") and states_commercial_fact(change.text):
        return ChangeOutcome(claims, refused="protected")
    if change.action == "remove" and target is not None:
        return ChangeOutcome([c for c in claims if c.id != target.id])
    if change.action == "replace" and target is not None:
        updated = target.model_copy(
            update={"text": change.text, "origin": "proposal", "quote": None}
        )
        return ChangeOutcome([updated if c.id == target.id else c for c in claims])
    if change.action == "assume" and has_assumption(claims, change.text):
        return ChangeOutcome(claims, refused="duplicate")
    return ChangeOutcome([*claims, new_claim(claims, change, target, fallback)])


def new_claim(
    claims: list[Claim], change: Change, near: Claim | None, fallback: Section | None = None
) -> Claim:
    if change.action == "assume":
        text = change.text.removeprefix(ASSUMPTION_PREFIX)
        return Claim(
            id=next_claim_id(claims),
            section="assumptions",
            text=ASSUMPTION_PREFIX + text,
            origin="assumption",
        )
    near_section = near.section if near is not None else None
    section = change.section or fallback or near_section or DEFAULT_ADD_SECTION
    return Claim(id=next_claim_id(claims), section=section, text=change.text, origin="proposal")
