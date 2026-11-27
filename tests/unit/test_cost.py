import pytest

from domain.claims import format_money
from domain.cost import (
    CostInputError,
    PhaseDays,
    choose_efforts,
    choose_rate,
    estimate_cost,
    price_phases,
)
from schemas.answers import DeliveryManagerAnswer
from schemas.case_file import Rate, Team
from schemas.cost import PhaseEffort


def northwind_estimate():  # noqa: ANN201 - test helper
    phases = [PhaseEffort(no=1, engineers=2, weeks=2), PhaseEffort(no=2, engineers=2, weeks=2)]
    return estimate_cost(phases, 600, "USD")


# --- Cost maths ---


def test_northwind_cost_matches_a_hand_calculation() -> None:
    estimate = northwind_estimate()
    assert [(p.days, p.cost) for p in estimate.phases] == [(10, 12000.0), (10, 12000.0)]
    assert (estimate.engineer_days, estimate.total) == (40, 24000.0)


def test_summit_ridge_change_request_is_33000() -> None:
    estimate = estimate_cost([PhaseEffort(no=1, engineers=2, weeks=6)], 550, "USD")
    assert (estimate.engineer_days, estimate.total) == (60, 33000.0)


def test_money_rounds_half_up_to_cents() -> None:
    estimate = price_phases([PhaseDays(1, 1, 1)], 0.125, "USD")
    assert estimate.total == 0.13


def test_fractional_days_are_priced() -> None:
    assert price_phases([PhaseDays(1, 3, 2.5)], 400, "USD").total == 3000.0


@pytest.mark.parametrize(
    ("engineers", "days", "rate"), [(0, 5, 600), (2, 0, 600), (2, 5, 0), (-1, 5, 600)]
)
def test_cost_refuses_zero_or_negative_input(engineers: int, days: float, rate: float) -> None:
    with pytest.raises(CostInputError):
        price_phases([PhaseDays(1, engineers, days)], rate, "USD")


def test_cost_needs_a_phase() -> None:
    with pytest.raises(CostInputError):
        price_phases([], 600, "USD")


@pytest.mark.parametrize(
    ("amount", "currency", "text"),
    [(12000, "USD", "$12,000"), (1234.5, "EUR", "€1,234.50"), (500, "CHF", "500 CHF")],
)
def test_format_money(amount: float, currency: str, text: str) -> None:
    assert format_money(amount, currency) == text


# --- Which inputs code trusts ---


def test_effort_comes_from_the_delivery_manager_renumbered_by_code() -> None:
    answer = DeliveryManagerAnswer.model_validate(
        {
            "phases": [
                {"no": 5, "engineers": 2, "weeks": 2},
                {"no": 7, "engineers": 1, "weeks": 3},
            ]
        }
    )
    efforts = choose_efforts(answer, None)
    assert [(e.no, e.engineers, e.weeks) for e in efforts] == [(1, 2, 2), (2, 1, 3)]


def test_effort_falls_back_to_the_brief_team() -> None:
    efforts = choose_efforts(DeliveryManagerAnswer(), Team(engineers=2, weeks=4))
    assert [(e.no, e.engineers, e.weeks) for e in efforts] == [(1, 2, 4)]
    assert choose_efforts(DeliveryManagerAnswer(), None) == []


def test_rate_is_used_only_if_the_brief_states_it() -> None:
    stated = Rate(amount=600, currency="USD")
    assert choose_rate(600, stated, {600.0, 2.0}) == (600, "USD")
    assert choose_rate(650, stated, {600.0}) == (600, "USD")
    assert choose_rate(650, None, {600.0}) == (None, "USD")
    assert choose_rate(None, Rate(amount=550, currency="EUR"), {550.0}) == (550, "EUR")
