"""Gate seats (plan section 4.4, rule 3). Code derives every outcome from the checklist.

A gate seat answers each checklist item Met, Partly or Not met. A must-have that is Not met
blocks. Otherwise any Partly, or a Not met on a non-must, passes with conditions. All Met passes.
An item the seat leaves out counts as Not met (a missing clause is never assumed) and marks the
answer partial.
"""

from domain.scoring import criterion_key
from domain.seats import SeatSpec
from schemas.answers import ChecklistAnswer
from schemas.board import ChecklistResult, GateOutcome

MISSING_REASON = "Not answered by the seat, so code counts it as not met."


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
                status=answer.status if answer else "not_met",
                reason=answer.reason if answer else MISSING_REASON,
                answered=answer is not None,
            )
        )
    return results


def gate_outcome(items: list[ChecklistResult]) -> GateOutcome:
    if any(i.must and i.status == "not_met" for i in items):
        return "blocked"
    if any(i.status != "met" for i in items):
        return "pass_with_conditions"
    return "pass"


def is_partial(items: list[ChecklistResult]) -> bool:
    return any(not i.answered for i in items)
