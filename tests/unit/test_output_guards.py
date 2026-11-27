from guards.output import (
    contains_quote,
    known_numbers,
    number_guard,
    numbers_in,
    quote_guard,
    split_signals,
)
from schemas.case_file import Signal
from schemas.claims import Claim
from tests.fixtures.briefs import NORTHWIND


def claim(claim_id: str, text: str, origin: str = "proposal", **extra: object) -> Claim:
    return Claim.model_validate(
        {"id": claim_id, "section": "scope", "text": text, "origin": origin} | extra
    )


# Quote matching
def test_quote_match_ignores_case_spacing_and_edge_punctuation() -> None:
    assert contains_quote("budget   is TIGHT this year.", NORTHWIND)
    assert contains_quote("“Budget is tight this year”", NORTHWIND)


def test_quote_must_really_be_there() -> None:
    assert not contains_quote("budget is generous", NORTHWIND)
    assert not contains_quote("", NORTHWIND)
    assert not contains_quote(None, NORTHWIND)


# G10
def test_g10_brief_claim_with_a_real_quote_stays() -> None:
    kept = claim("C1", "Budget is tight.", "brief", quote="Budget is tight this year")
    result = quote_guard([kept], NORTHWIND)
    assert result.claims == [kept] and result.flagged_ids == []


def test_g10_brief_claim_without_a_real_quote_becomes_to_confirm() -> None:
    invented = claim("C2", "Budget is unlimited.", "brief", quote="budget is unlimited")
    missing = claim("C3", "Uses SAP.", "brief")
    result = quote_guard([invented, missing], NORTHWIND)
    assert [c.origin for c in result.claims] == ["assumption", "assumption"]
    assert [c.quote for c in result.claims] == [None, None]
    assert result.flagged_ids == ["C2", "C3"]


def test_g10_other_origins_are_not_touched() -> None:
    recommendation = claim("C4", "Add a status page.", "architect")
    assert quote_guard([recommendation], NORTHWIND).claims == [recommendation]


def test_g10_signals_without_a_real_quote_are_dropped() -> None:
    real = Signal(text="tight budget", quote="Budget is tight this year")
    inferred = Signal(text="handles personal data", quote="insurance data is sensitive")
    kept, dropped = split_signals([real, inferred], NORTHWIND)
    assert (kept, dropped) == ([real], [inferred])


# G9
def test_numbers_are_read_as_values() -> None:
    assert numbers_in("$12,000 for 2 engineers over 7.5 days, ref C7") == {12000.0, 2.0, 7.5}


def test_g9_numbers_from_the_brief_or_tools_pass() -> None:
    known = known_numbers(NORTHWIND, [{"working_days": 10, "total": 24000}], extra=[1])
    ok = [
        claim("C1", "Phase 1 starts Dec 7 with 2 engineers."),
        claim("C2", "Ten working days: 10 in total, $24,000."),
    ]
    result = number_guard(ok, known)
    assert result.flagged_ids == [] and result.claims == ok


def test_g9_invented_number_becomes_to_confirm() -> None:
    known = known_numbers(NORTHWIND, [])
    result = number_guard([claim("C1", "Saves $50,000 a year.")], known)
    assert result.flagged_ids == ["C1"]
    assert result.claims[0].origin == "assumption"


def test_g9_locked_calculated_claims_are_left_to_code() -> None:
    locked = claim("C9", "Total: 40 engineer-days, $24,000.", "calculated", locked=True)
    assert number_guard([locked], set()).claims == [locked]
