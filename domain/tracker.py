"""The objection tracker (plan section 4.5). Code assigns every id and status.

O items are objections the Bid Manager can fix by changing the proposal; C items are
conditions only the client can confirm (`needs_client`). Gate items that are Not met or Partly
become tracker items too. Unknown claim ids from a model are dropped from the item.
Items start open; Phase 4 marks one fixed only when the seat that raised it re-reads and agrees.
"""

from dataclasses import dataclass
from typing import Literal

from domain.claims import normalize_text
from schemas.answers import GateObjection, PreviousState, ScoringObjection
from schemas.board import ChecklistResult
from schemas.common import match_key as criterion_key
from schemas.state import HistoryEntry, TrackerItem

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


def same_client_item(tracker: list[TrackerItem], draft: ItemDraft) -> TrackerItem | None:
    """An open client-only item this draft repeats: the same seat on the same claim, or the
    same text (lower case, no punctuation) from any seat."""
    if draft.kind != "C":
        return None
    wanted = normalize_text(draft.text)
    for item in tracker:
        if item.kind != "C" or item.status != "open":
            continue
        same_claim = (
            item.seat == draft.seat and draft.claim_ids and item.claim_ids == list(draft.claim_ids)
        )
        if same_claim or normalize_text(item.text) == wanted:
            return item
    return None


def add_items(
    tracker: list[TrackerItem], drafts: list[ItemDraft], round_no: int
) -> list[TrackerItem]:
    """Append items in order, each with the next free id of its kind. A client-only item raised
    again updates the existing item (same id) instead of opening a new one."""
    added = list(tracker)
    for draft in drafts:
        repeat = same_client_item(added, draft)
        if repeat is not None:
            if repeat.seat == draft.seat:
                update = {
                    "text": draft.text,
                    "resolve_hint": draft.resolve_hint or repeat.resolve_hint,
                }
                added = [t.model_copy(update=update) if t.id == repeat.id else t for t in added]
            continue
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
    seat_id: str,
    items: list[ChecklistResult],
    objections: list[GateObjection],
    tracker: list[TrackerItem] | None = None,
) -> list[ItemDraft]:
    """One item per checklist line that is not met or partly met. The seat's own objection
    gives the wording; without one, code writes it. Objections on met or unknown items are
    ignored, and a line that already has an open item of this seat gets no second one."""
    already_open = {t.item_id for t in open_items(tracker or [], seat_id) if t.item_id}
    by_item: dict[str, GateObjection] = {}
    for objection in objections:
        by_item.setdefault(criterion_key(objection.item_id), objection)
    drafts = []
    for item in items:
        if item.status in ("met", "missing") or item.id in already_open:
            continue
        objection = by_item.get(item.id) or by_item.get(criterion_key(item.label))
        text = objection.text.strip() if objection and objection.text.strip() else ""
        hint = objection.resolve_hint.strip() if objection else ""
        drafts.append(
            ItemDraft(
                seat=seat_id,
                kind=kind_of(objection.needs_client if objection else False),
                severity="blocker" if item.must and item.status == "not_met" else "condition",
                text=text or checklist_text(item),
                item_id=item.id,
                resolve_hint=hint or checklist_hint(item),
            )
        )
    return drafts


def checklist_text(item: ChecklistResult) -> str:
    """A gate item in the seat's own words: "Access control: <the seat's reason>"."""
    reason = item.reason.strip().rstrip(".")
    return f"{item.label}: {reason}." if reason else f"{item.label}: {STATUS_WORDS[item.status]}."


def checklist_hint(item: ChecklistResult) -> str:
    """What would resolve a gate item, from the seat's own reason, for the Bid Manager."""
    reason = item.reason.strip().rstrip(".")
    label = item.label[0].lower() + item.label[1:]
    if reason:
        return f"Add {label} as the seat described: {reason}."
    return f"Add {label} to the proposal so the seat can mark it met."


def open_items(tracker: list[TrackerItem], seat_id: str) -> list[TrackerItem]:
    return [t for t in tracker if t.seat == seat_id and t.status == "open"]


# A gate's checklist answer for the line an item is about counts as its re-read of that item
# when its `previous` list leaves the item out.
CHECKLIST_STATES = {"met": "resolved", "partly": "partly", "not_met": "open"}


def reread_states(
    tracker: list[TrackerItem],
    seat_id: str,
    previous: list[PreviousState],
    checklist: list[ChecklistResult] | None = None,
) -> dict[str, str]:
    """What the raising seat said about each of its own open items after re-reading.

    Ids of other seats' items and unknown ids are ignored: only the seat that raised an item
    can fix it. A missing checklist line says nothing."""
    own = {t.id: t for t in open_items(tracker, seat_id)}
    states = {p.id: p.state for p in previous if p.id in own}
    by_line = {c.id: c.status for c in checklist or []}
    for item_id, item in own.items():
        line_status = by_line.get(item.item_id or "")
        if item_id not in states and line_status in CHECKLIST_STATES:
            states[item_id] = CHECKLIST_STATES[line_status]
    return states


def apply_reread(
    tracker: list[TrackerItem], states: dict[str, str], round_no: int
) -> list[TrackerItem]:
    """Record each re-read in the item's history. Only "resolved" fixes an item."""
    updated = []
    for item in tracker:
        state = states.get(item.id)
        if state is None:
            updated.append(item)
            continue
        history = [*item.history, HistoryEntry(round=round_no, state=state)]  # type: ignore[arg-type]
        status = "fixed" if state == "resolved" else "open"
        updated.append(item.model_copy(update={"history": history, "status": status}))
    return updated


def mark_answered(tracker: list[TrackerItem], ids: set[str], bid_round: int) -> list[TrackerItem]:
    """The Bid Manager answered these items. That is shown as "answered", never as "fixed"."""
    return [
        t.model_copy(update={"answered_in": [*t.answered_in, bid_round]}) if t.id in ids else t
        for t in tracker
    ]
