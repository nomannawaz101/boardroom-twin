"""The objection tracker (plan section 4.5). Code assigns every id and status.

O items are objections the Bid Manager can fix by changing the proposal; C items are
conditions only the client can confirm (`needs_client`). Gate items that are Not met or Partly
become tracker items too. Unknown claim ids from a model are dropped from the item.
Items start open; Phase 4 marks one fixed only when the seat that raised it re-reads and agrees.
"""

from dataclasses import dataclass
from typing import Literal

from domain.scoring import criterion_key
from schemas.answers import GateObjection, ScoringObjection
from schemas.board import ChecklistResult
from schemas.state import TrackerItem

Kind = Literal["O", "C"]
Severity = Literal["blocker", "condition"]
STATUS_WORDS = {"not_met": "not met", "partly": "partly met"}


@dataclass(frozen=True)
class ItemDraft:
    """A tracker item before code gives it an id."""

    seat: str
    kind: Kind
    severity: Severity
    text: str
    item_id: str | None = None
    claim_ids: tuple[str, ...] = ()
    resolve_hint: str = ""


def next_tracker_id(tracker: list[TrackerItem], kind: Kind) -> str:
    numbers = [int(t.id[1:]) for t in tracker if t.kind == kind and t.id[1:].isdigit()]
    return f"{kind}{max(numbers, default=0) + 1}"


def add_items(
    tracker: list[TrackerItem], drafts: list[ItemDraft], round_no: int
) -> list[TrackerItem]:
    """Append items in order, each with the next free id of its kind."""
    added = list(tracker)
    for draft in drafts:
        added.append(
            TrackerItem(
                id=next_tracker_id(added, draft.kind),
                seat=draft.seat,
                kind=draft.kind,
                severity=draft.severity,
                item_id=draft.item_id,
                claim_ids=list(draft.claim_ids),
                text=draft.text,
                resolve_hint=draft.resolve_hint,
                raised_round=round_no,
            )
        )
    return added


def kind_of(needs_client: bool) -> Kind:
    return "C" if needs_client else "O"


def scoring_drafts(
    seat_id: str, objections: list[ScoringObjection], claim_ids: set[str]
) -> list[ItemDraft]:
    return [
        ItemDraft(
            seat=seat_id,
            kind=kind_of(o.needs_client),
            severity=o.severity,
            text=o.text.strip(),
            claim_ids=(o.claim_id,) if o.claim_id in claim_ids else (),
            resolve_hint=o.resolve_hint.strip(),
        )
        for o in objections
        if o.text.strip()
    ]


def gate_drafts(
    seat_id: str, items: list[ChecklistResult], objections: list[GateObjection]
) -> list[ItemDraft]:
    """One item per checklist line that is not met or partly met. The seat's own objection
    gives the wording; without one, code writes it. Objections on met or unknown items are
    ignored."""
    by_item: dict[str, GateObjection] = {}
    for objection in objections:
        by_item.setdefault(criterion_key(objection.item_id), objection)
    drafts = []
    for item in items:
        if item.status == "met":
            continue
        objection = by_item.get(item.id) or by_item.get(criterion_key(item.label))
        text = objection.text.strip() if objection and objection.text.strip() else ""
        drafts.append(
            ItemDraft(
                seat=seat_id,
                kind=kind_of(objection.needs_client if objection else False),
                severity="blocker" if item.must and item.status == "not_met" else "condition",
                text=text or f"{item.label}: {STATUS_WORDS[item.status]}.",
                item_id=item.id,
                resolve_hint=objection.resolve_hint.strip() if objection else "",
            )
        )
    return drafts


def open_items(tracker: list[TrackerItem], seat_id: str) -> list[TrackerItem]:
    return [t for t in tracker if t.seat == seat_id and t.status == "open"]
