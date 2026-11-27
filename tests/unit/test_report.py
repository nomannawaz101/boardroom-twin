"""Report key numbers come from code: the cost calculator and the working-day schedule."""

from datetime import date

from domain.cost import estimate_cost
from domain.report import cost_number, go_live_number
from domain.timeline import plan_schedule
from schemas.cost import PhaseEffort
from schemas.state import RunState

BASE = {"run_id": "r", "mode": "full", "brief": "b"}


def test_cost_and_go_live_from_code() -> None:
    estimate = estimate_cost(
        [PhaseEffort(no=1, engineers=2, weeks=2), PhaseEffort(no=2, engineers=2, weeks=2)],
        600,
        "USD",
    )
    schedule = plan_schedule(date(2026, 12, 7), [(1, 10), (2, 10)])
    state = RunState.model_validate(
        BASE | {"estimate": estimate.model_dump(), "schedule": schedule.model_dump()}
    )
    cost, go_live = cost_number(state), go_live_number(state)
    assert (cost.value, cost.note) == ("$12,000", "Total $24,000")
    assert (go_live.value, go_live.note) == (
        "Mon Jan 4, 2027",
        "Weekends counted; holidays not checked yet",
    )


def test_missing_rate_and_start_stay_to_confirm() -> None:
    state = RunState.model_validate(BASE)
    assert cost_number(state).value == "To confirm"
    assert go_live_number(state).value == "To confirm"
