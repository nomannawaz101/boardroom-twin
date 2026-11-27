"""Claims: code assigns ids, builds the calculated claims and keeps them locked.

A model can never edit a calculated claim; every rebuild recreates them from the numbers.
"""

from dataclasses import dataclass
from typing import Literal

import config
from schemas.answers import Change
from schemas.claims import Claim, DraftClaim, Section
from schemas.cost import CostEstimate

CLAIM_PREFIX = "C"
ASSUMPTION_PREFIX = "Confirm with the client: "
COST_SECTION: Section = "team_cost"
DEFAULT_ADD_SECTION: Section = "proposed_solution"

RefusalReason = Literal["locked", "unknown_claim"]


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


def calculated_texts(estimate: CostEstimate) -> list[str]:
    """One sentence per phase plus the total, all built from code-computed numbers."""
    money = estimate.currency
    texts = [
        f"Phase {p.no}: {p.engineers} engineers x {format_number(p.days)} days x "
        f"{format_money(p.rate, money)} = {format_money(p.cost, money)}."
        for p in estimate.phases
    ]
    texts.append(
        f"Total: {format_number(estimate.engineer_days)} engineer-days, "
        f"{format_money(estimate.total, estimate.currency)}."
    )
    return texts


def locked_claim(claim_id: str, text: str) -> Claim:
    return Claim(id=claim_id, section=COST_SECTION, text=text, origin="calculated", locked=True)


def assemble_claims(drafts: list[DraftClaim], estimate: CostEstimate | None) -> list[Claim]:
    """Number the model's claims, then add the locked calculated claims.

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
    if estimate is not None:
        for text in calculated_texts(estimate):
            claims.append(locked_claim(next_claim_id(claims), text))
    return claims


def rebuild_calculated(claims: list[Claim], estimate: CostEstimate) -> list[Claim]:
    """Recreate every calculated claim from the numbers, keeping existing ids where possible."""
    texts = iter(calculated_texts(estimate))
    rebuilt: list[Claim] = []
    for claim in claims:
        if claim.origin != "calculated":
            rebuilt.append(claim)
            continue
        text = next(texts, None)
        if text is not None:
            rebuilt.append(locked_claim(claim.id, text))
    for text in texts:
        rebuilt.append(locked_claim(next_claim_id(rebuilt), text))
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
