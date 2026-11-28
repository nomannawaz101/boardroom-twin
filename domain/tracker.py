"""The objection tracker (plan section 4.5). Code assigns every id and status.

O items are objections the Bid Manager can fix by changing the proposal; C items are
conditions only the client can confirm (`needs_client`). Gate items that are Not met or Partly
become tracker items too. Unknown claim ids from a model are dropped from the item.
Items start open; Phase 4 marks one fixed only when the seat that raised it re-reads and agrees.
"""

import re
from dataclasses import dataclass
from typing import Literal

import config
from domain.claims import normalize_text
from schemas.answers import GateObjection, PreviousState, ScoringObjection
from schemas.board import ChecklistResult
from schemas.common import match_key as criterion_key
from schemas.state import HistoryEntry, TrackerItem

Kind = Literal["O", "C"]
Severity = Literal["blocker", "condition"]
STATUS_WORDS = {"not_met": "not met", "partly": "partly met"}
# An objection that asks to change our commercial terms: a cap or ceiling, a discount, a lower
# rate or price, or the other contract type. Only Lumen Works can decide that.
TERMS_CHANGE = re.compile(
    r"\b(?:cap|capped|ceiling)\b|not[- ]to[- ]exceed|\bdiscount"
    r"|\b(?:lower|reduce[ds]?|cut)\s+(?:the\s+)?(?:day\s+)?(?:rate|price|fee)",
    re.IGNORECASE,
)
OTHER_CONTRACT = {
    "tm": re.compile(r"fixed[- ]price|firm price|fixed fee", re.IGNORECASE),
    "fixed": re.compile(r"time[- ]and[- ]materials|\bt&m\b", re.IGNORECASE),
}
EITHER_CONTRACT = re.compile(
    r"fixed[- ]price|firm price|fixed fee|time[- ]and[- ]materials|\bt&m\b", re.IGNORECASE
)


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
    must: bool = False


def next_tracker_id(tracker: list[TrackerItem], kind: Kind) -> str:
    numbers = [int(t.id[1:]) for t in tracker if t.kind == kind and t.id[1:].isdigit()]
    return f"{kind}{max(numbers, default=0) + 1}"


def content_words(text: str) -> set[str]:
    return {w for w in normalize_text(text).split() if len(w) >= config.CONTENT_WORD_MIN}


def similar_text(first: str, second: str) -> bool:
    """Most content words of the shorter text appear in the other."""
    a, b = content_words(first), content_words(second)
    if not a or not b:
        return normalize_text(first) == normalize_text(second)
    return len(a & b) / min(len(a), len(b)) >= config.SIMILAR_TEXT_OVERLAP


def same_target(item: TrackerItem, draft: ItemDraft) -> bool:
    same_claim = bool(draft.claim_ids) and item.claim_ids == list(draft.claim_ids)
    same_line = draft.item_id is not None and item.item_id == draft.item_id
    return same_claim or same_line


def repeated_item(tracker: list[TrackerItem], draft: ItemDraft) -> TrackerItem | None:
    """An open item this draft repeats. Client-only: the same seat on the same claim, or the
    same text (lower case, no punctuation) from any seat. Fixable: the same seat on the same
    claim or checklist line, with similar text."""
    for item in tracker:
        if item.kind != draft.kind or item.status != "open":
            continue
        own = item.seat == draft.seat and same_target(item, draft)
        if draft.kind == "C" and (own or normalize_text(item.text) == normalize_text(draft.text)):
            return item
        if draft.kind == "O" and own and similar_text(item.text, draft.text):
            return item
    return None


def updated_item(item: TrackerItem, draft: ItemDraft) -> TrackerItem:
    """The seat's newer wording, keeping the id; a blocker stays a blocker."""
    severity = "blocker" if "blocker" in (item.severity, draft.severity) else "condition"
    return item.model_copy(
        update={
            "text": draft.text,
            "resolve_hint": draft.resolve_hint or item.resolve_hint,
            "severity": severity,
            "must": item.must or draft.must,
        }
    )


def add_items(
    tracker: list[TrackerItem], drafts: list[ItemDraft], round_no: int
) -> list[TrackerItem]:
    """Append items in order, each with the next free id of its kind. An item raised again
    updates the existing item (same id) instead of opening a new one."""
    added = list(tracker)
    for draft in drafts:
        repeat = repeated_item(added, draft)
        if repeat is not None:
            if repeat.seat == draft.seat:
                added = [updated_item(t, draft) if t.id == repeat.id else t for t in added]
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
                must=draft.must,
                raised_round=round_no,
            )
        )
    return added


def asks_terms_change(item: TrackerItem, contract_type: str | None) -> bool:
    text = f"{item.text} {item.resolve_hint}"
    other = OTHER_CONTRACT.get(contract_type or "", EITHER_CONTRACT)
    return bool(TERMS_CHANGE.search(text) or other.search(text))


def flag_decisions(tracker: list[TrackerItem], contract_type: str | None) -> list[TrackerItem]:
    """Open fixable objections that ask to change our commercial terms become decisions for
    Lumen Works: the Bid Manager must not change the contract model to answer them."""
    return [
        t.model_copy(update={"decision": True})
        if t.kind == "O"
        and t.status == "open"
        and not t.decision
        and asks_terms_change(t, contract_type)
        else t
        for t in tracker
    ]


def unaddressed_blockers(tracker: list[TrackerItem]) -> list[str]:
    """Open fixable blockers and must-have gate items no applied change has answered yet.
    Decisions for Lumen Works are left out: no proposal change can settle them."""
    return [
        t.id
        for t in tracker
        if t.kind == "O"
        and t.status == "open"
        and not t.decision
        and (t.severity == "blocker" or t.must)
        and not t.answered_in
    ]


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
                must=item.must,
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
