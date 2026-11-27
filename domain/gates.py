"""Gate seats (plan section 4.4, rule 3). Code derives every outcome from the checklist.

A gate seat answers each checklist item Met, Partly or Not met. A must-have that is Not met
blocks. Otherwise any Partly, or a Not met on a non-must, passes with conditions. All Met passes.

An item the seat leaves out is never read as Met, Partly or Not met. The reply check makes the
seat answer it again; if it is still missing after the retries, a known must-have Not met still
blocks (a known result wins), and otherwise the outcome is undecided, so the seat is Not reviewed.
"""

from domain.seats import SeatSpec
from schemas.answers import ChecklistAnswer
from schemas.board import ChecklistResult, GateOutcome
from schemas.common import match_key as criterion_key

MISSING_REASON = "Not answered by the seat."


def match_items(spec: SeatSpec, answers: list[ChecklistAnswer]) -> list[ChecklistResult]:
    """One result per checklist item, in registry order. Unknown items are ignored; if an item
    is answered twice, the first answer counts."""
    found: dict[str, ChecklistAnswer] = {}
    for answer in answers:
        key = criterion_key(answer.id)
        for item in spec.checklist:
            if key in (item.id, criterion_key(item.label)):
                found.setdefault(item.id, answer)
    results = []
    for item in spec.checklist:
        answer = found.get(item.id)
        results.append(
            ChecklistResult(
                id=item.id,
                label=item.label,
                must=item.must,
                status=answer.status if answer else "missing",
                reason=answer.reason if answer else MISSING_REASON,
            )
        )
    return results


def gate_outcome(items: list[ChecklistResult]) -> GateOutcome | None:
    """None when the outcome cannot be decided: an item is missing and nothing known blocks."""
    if any(i.must and i.status == "not_met" for i in items):
        return "blocked"
    if is_partial(items):
        return None
    if any(i.status != "met" for i in items):
        return "pass_with_conditions"
    return "pass"


def is_partial(items: list[ChecklistResult]) -> bool:
    return any(i.status == "missing" for i in items)
