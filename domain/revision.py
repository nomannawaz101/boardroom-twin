"""One Bid Manager round applied by code (plan section 4.6, Appendix A).

Every change must name an open objection id; anything else is ignored. Calculated claims are
locked, so changing one is refused. The Bid Manager's work shows as "answered"; an item is fixed
only later, when the seat that raised it re-reads the new text and agrees.
"""

from domain.claims import apply_change, find_claim
from domain.tracker import mark_answered
from schemas.answers import Change
from schemas.claims import Claim
from schemas.revision import AppliedChange, ChangeOutcome
from schemas.state import TrackerItem

NEEDS_TEXT = ("replace", "add", "assume")


def outcome_of(change: Change, open_ids: set[str]) -> ChangeOutcome | None:
    """Why a change cannot be applied, or None if code may try it."""
    if change.objection_id not in open_ids:
        return "unknown_objection"
    if change.action in NEEDS_TEXT and not change.text.strip():
        return "empty"
    return None


def apply_bid_changes(
    claims: list[Claim], tracker: list[TrackerItem], changes: list[Change], bid_round: int
) -> tuple[list[Claim], list[AppliedChange], list[TrackerItem]]:
    open_ids = {t.id for t in tracker if t.status == "open"}
    current = claims
    applied: list[AppliedChange] = []
    for change in changes:
        refusal = outcome_of(change, open_ids)
        if refusal is not None:
            applied.append(record(change, None, None, refusal))
            continue
        before = find_claim(current, change.claim_id)
        result = apply_change(current, change)
        if result.refused is not None:
            applied.append(record(change, before, None, result.refused))
            continue
        after = None if change.action == "remove" else changed_claim(result.claims, change, before)
        current = result.claims
        applied.append(record(change, before, after, "applied"))
    return current, applied, mark_answered(tracker, set(answered_ids(applied)), bid_round)


def changed_claim(claims: list[Claim], change: Change, before: Claim | None) -> Claim | None:
    if change.action == "replace" and before is not None:
        return find_claim(claims, before.id)
    return claims[-1]  # add and assume append the new claim


def record(
    change: Change, before: Claim | None, after: Claim | None, outcome: ChangeOutcome
) -> AppliedChange:
    return AppliedChange(
        objection_id=change.objection_id,
        action=change.action,
        claim_id=(after or before).id if (after or before) else change.claim_id,
        old_text=before.text
        if before is not None and change.action in ("replace", "remove")
        else None,
        new_text=after.text if after is not None else None,
        outcome=outcome,
    )


def answered_ids(changes: list[AppliedChange]) -> list[str]:
    return sorted({c.objection_id for c in changes if c.outcome == "applied"})
