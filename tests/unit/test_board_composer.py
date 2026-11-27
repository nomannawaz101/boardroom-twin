from itertools import product

import pytest

from domain.board_composer import FILLER_WHY, compose_board, vp_title
from schemas.case_file import BoardFlags

ALL_SEATS = ["cfo", "vp_director", "enterprise_architect", "procurement", "security"]


def seats(**flags: object) -> list[str]:
    return [s.id for s in compose_board(BoardFlags.model_validate(flags)).seats]


# --- Appendix B: the expected board for each sample brief ---


def test_northwind_gets_all_five_seats() -> None:
    plan = compose_board(
        BoardFlags(
            personal_data=True,
            existing_systems=True,
            contract_type="tm",
            function="Claims Operations",
            seniority="large",
        )
    )
    assert [s.id for s in plan.seats] == ALL_SEATS
    assert plan.seats[1].title == "VP, Claims Operations"
    assert plan.skipped == []


def test_harbor_freight_gets_cfo_director_and_procurement() -> None:
    plan = compose_board(
        BoardFlags(
            personal_data=False,
            existing_systems=False,
            contract_type="tm",
            function="Operations",
            seniority="small",
        )
    )
    assert [s.id for s in plan.seats] == ["cfo", "vp_director", "procurement"]
    assert {s.id: s.why_not for s in plan.skipped} == {
        "enterprise_architect": "No existing system is touched.",
        "security": "No personal data is involved.",
    }


def test_harbor_freight_with_unclear_flags_adds_architect_and_security() -> None:
    assert seats(contract_type="tm") == ALL_SEATS


def test_summit_ridge_gets_all_five_seats() -> None:
    assert seats(personal_data=True, existing_systems=True, contract_type="fixed") == ALL_SEATS


# --- Rules ---


def test_cfo_and_vp_always_join() -> None:
    for personal, existing, contract in product(
        (True, False, None), (True, False, None), ("fixed", "tm", "other", "none", None)
    ):
        chosen = seats(personal_data=personal, existing_systems=existing, contract_type=contract)
        assert chosen[:2] == ["cfo", "vp_director"]
        assert 3 <= len(chosen) <= 5


@pytest.mark.parametrize(
    ("contract", "joins"),
    [("fixed", True), ("tm", True), ("other", True), (None, True), ("none", False)],
)
def test_procurement_joins_unless_there_is_no_contract(contract: str | None, joins: bool) -> None:
    chosen = seats(personal_data=False, existing_systems=True, contract_type=contract)
    assert ("procurement" in chosen) is joins


@pytest.mark.parametrize(("value", "joins"), [(True, True), (None, True), (False, False)])
def test_security_joins_for_personal_or_unclear_data(value: bool | None, joins: bool) -> None:
    chosen = seats(personal_data=value, existing_systems=True, contract_type="tm")
    assert ("security" in chosen) is joins


def test_minimum_of_three_adds_the_architect_with_its_reason() -> None:
    plan = compose_board(
        BoardFlags(personal_data=False, existing_systems=False, contract_type="none")
    )
    assert [s.id for s in plan.seats] == ["cfo", "vp_director", "enterprise_architect"]
    assert plan.seats[2].why == FILLER_WHY
    assert [s.id for s in plan.skipped] == ["procurement", "security"]


def test_every_seat_has_a_reason() -> None:
    plan = compose_board(BoardFlags())
    assert all(s.why for s in plan.seats)


@pytest.mark.parametrize(
    ("seniority", "function", "title"),
    [
        ("large", "Claims Operations", "VP, Claims Operations"),
        ("small", "Customer Support", "Director, Customer Support"),
        (None, "Claims", "VP, Claims"),
        ("small", None, "Director, Operations"),
        (None, "  ", "VP, Operations"),
    ],
)
def test_vp_title(seniority: str | None, function: str | None, title: str) -> None:
    flags = BoardFlags.model_validate({"seniority": seniority, "function": function})
    assert vp_title(flags) == title


def test_unknown_flag_values_from_a_model_count_as_unclear() -> None:
    flags = BoardFlags.model_validate({"contract_type": "retainer", "seniority": "huge"})
    assert (flags.contract_type, flags.seniority) == (None, None)
