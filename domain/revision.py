"""One Bid Manager round applied by code (plan section 4.6, Appendix A).

Every change must name an open objection id; anything else is ignored. Calculated claims are
locked, and the client's facts, the commercial terms and the dates are protected, so changing
one is refused: they can only move through an assumption the client confirms. The Bid
Manager's work shows as "answered"; an item is fixed only later, when the seat that raised it
re-reads the new text and agrees.
"""

from domain.claims import apply_change, find_claim
from domain.tracker import mark_answered
from schemas.answers import Change
from schemas.claims import Claim, Section
from schemas.revision import AppliedChange, ChangeOutcome
from schemas.state import TrackerItem

NEEDS_TEXT = ("replace", "add", "assume")


def outcome_of(change: Change, open_items: dict[str, TrackerItem]) -> ChangeOutcome | None:
    """Why a change cannot be applied, or None if code may try it. A C item needs the client,
    so the proposal can only record it as an assumption ("Confirm with the client: ...")."""
    item = open_items.get(change.objection_id)
    if item is None:
        return "unknown_objection"
    if item.kind == "C" and change.action != "assume":
        return "client_only"
    if change.action in NEEDS_TEXT and not change.text.strip():
        return "empty"
    return None


def apply_bid_changes(
    claims: list[Claim], tracker: list[TrackerItem], changes: list[Change], bid_round: int
) -> tuple[list[Claim], list[AppliedChange], list[TrackerItem]]:
    open_now = {t.id: t for t in tracker if t.status == "open"}
    current = claims
    applied: list[AppliedChange] = []
    for change in changes:
        refusal = outcome_of(change, open_now)
        if refusal is not None:
            applied.append(record(change, None, None, refusal))
            continue
        edits = change.action in ("replace", "remove")
        before = find_claim(current, change.claim_id) if edits else None
        result = apply_change(
            current, change, objection_section(current, open_now[change.objection_id])
        )
        if result.refused is not None:
            applied.append(record(change, before, None, result.refused))
            continue
        after = None if change.action == "remove" else changed_claim(result.claims, change, before)
        current = result.claims
        applied.append(record(change, before, after, "applied"))
    return current, applied, mark_answered(tracker, set(answered_ids(applied)), bid_round)


def objection_section(claims: list[Claim], item: TrackerItem) -> Section | None:
    """The section of the claim an objection points to: where an added statement belongs when
    the Bid Manager names no section."""
    pointed = next(
        (find_claim(claims, cid) for cid in item.claim_ids if find_claim(claims, cid)), None
    )
    return pointed.section if pointed is not None else None


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
        proposed_text=change.text or None if outcome != "applied" else None,
        outcome=outcome,
    )


def answered_ids(changes: list[AppliedChange]) -> list[str]:
    return sorted({c.objection_id for c in changes if c.outcome == "applied"})
