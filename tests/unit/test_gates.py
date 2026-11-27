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


def answered(*pairs: tuple[str, str]) -> list[ChecklistAnswer]:
    return [ChecklistAnswer(id=item_id, status=status) for item_id, status in pairs]  # type: ignore[arg-type]


def test_a_missing_item_is_never_read_as_met_partly_or_not_met() -> None:
    items = match_items(
        PROCUREMENT, answered(("pricing_model", "met"), ("acceptance_payment", "met"))
    )
    assert [(i.id, i.status) for i in items] == [
        ("pricing_model", "met"),
        ("change_control", "missing"),
        ("acceptance_payment", "met"),
    ]
    assert is_partial(items)


def test_one_item_missing_and_the_rest_met_is_undecided() -> None:
    items = match_items(
        PROCUREMENT, answered(("pricing_model", "met"), ("acceptance_payment", "met"))
    )
    assert gate_outcome(items) is None


def test_one_item_missing_and_a_must_have_not_met_is_blocked() -> None:
    items = match_items(
        PROCUREMENT, answered(("pricing_model", "not_met"), ("acceptance_payment", "met"))
    )
    assert gate_outcome(items) == "blocked"


def test_one_item_missing_and_a_non_must_not_met_is_still_undecided() -> None:
    # Only a must-have Not met can block (section 4.4 rule 3); without it the missing line
    # leaves the outcome open, so the seat is Not reviewed.
    items = match_items(
        PROCUREMENT, answered(("pricing_model", "met"), ("acceptance_payment", "not_met"))
    )
    assert gate_outcome(items) is None


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
