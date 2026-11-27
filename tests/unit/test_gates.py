from itertools import product

import pytest

from domain.gates import gate_outcome, is_partial, match_items
from domain.seats import SEATS_BY_ID
from schemas.answers import ChecklistAnswer

PROCUREMENT = SEATS_BY_ID["procurement"]  # pricing_model MUST, change_control MUST, acceptance
SECURITY = SEATS_BY_ID["security"]
STATUSES = ("met", "partly", "not_met")


def answers(spec: object, statuses: tuple[str, ...]) -> list[ChecklistAnswer]:
    items = spec.checklist  # type: ignore[attr-defined]
    return [
        ChecklistAnswer(id=i.id, status=s, reason="r") for i, s in zip(items, statuses, strict=True)
    ]  # type: ignore[arg-type]


def expected(statuses: tuple[str, ...], musts: tuple[bool, ...]) -> str:
    """The rule written out by hand, independently of the code under test."""
    if any(m and s == "not_met" for s, m in zip(statuses, musts, strict=True)):
        return "blocked"
    if any(s != "met" for s in statuses):
        return "pass_with_conditions"
    return "pass"


@pytest.mark.parametrize("spec", [PROCUREMENT, SECURITY], ids=["procurement", "security"])
@pytest.mark.parametrize("statuses", list(product(STATUSES, repeat=3)))
def test_every_met_partly_not_met_combination(spec: object, statuses: tuple[str, ...]) -> None:
    items = match_items(spec, answers(spec, statuses))  # type: ignore[arg-type]
    musts = tuple(i.must for i in spec.checklist)  # type: ignore[attr-defined]
    assert gate_outcome(items) == expected(statuses, musts)


@pytest.mark.parametrize(
    ("statuses", "outcome"),
    [
        (("met", "met", "met"), "pass"),
        (("met", "met", "partly"), "pass_with_conditions"),
        (("met", "met", "not_met"), "pass_with_conditions"),  # non-must not met
        (("partly", "partly", "partly"), "pass_with_conditions"),
        (("not_met", "met", "met"), "blocked"),  # must not met
        (("met", "not_met", "met"), "blocked"),
    ],
)
def test_named_cases(statuses: tuple[str, ...], outcome: str) -> None:
    assert gate_outcome(match_items(PROCUREMENT, answers(PROCUREMENT, statuses))) == outcome


def test_a_missing_must_item_counts_as_not_met_blocks_and_is_partial() -> None:
    given = [
        ChecklistAnswer(id="pricing_model", status="met"),
        ChecklistAnswer(id="acceptance_payment", status="met"),
    ]
    items = match_items(PROCUREMENT, given)
    assert [(i.id, i.status, i.answered) for i in items] == [
        ("pricing_model", "met", True),
        ("change_control", "not_met", False),
        ("acceptance_payment", "met", True),
    ]
    assert gate_outcome(items) == "blocked"
    assert is_partial(items)


def test_items_match_by_label_and_unknown_items_are_ignored() -> None:
    given = [
        ChecklistAnswer(id="Data protection", status="met"),
        ChecklistAnswer(id="ACCESS-CONTROL", status="met"),
        ChecklistAnswer(id="data_rules_fit", status="met"),
        ChecklistAnswer(id="vibes", status="not_met"),
    ]
    items = match_items(SECURITY, given)
    assert [i.status for i in items] == ["met", "met", "met"]
    assert gate_outcome(items) == "pass" and not is_partial(items)
