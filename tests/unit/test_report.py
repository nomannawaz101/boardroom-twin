"""Report key numbers come from code: the cost calculator and the working-day schedule."""

from datetime import date

from domain.cost import estimate_cost
from domain.report import cost_number, go_live_number, headline, score_number
from domain.timeline import plan_schedule
from schemas.board import BoardRound
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
        "Weekends skipped; public holidays not checked yet",
    )


def test_missing_rate_and_start_stay_to_confirm() -> None:
    state = RunState.model_validate(BASE)
    assert cost_number(state).value == "To confirm"
    assert go_live_number(state).value == "To confirm"


def board(no: int, scores: dict[str, float | None]) -> BoardRound:
    seats = [
        {
            "seat_id": seat,
            "kind": "scoring",
            "title": seat.upper(),
            "status": "answered" if score is not None else "not_reviewed",
            "able": True,
            "score": score,
        }
        for seat, score in scores.items()
    ]
    total = len(seats)
    return BoardRound.model_validate(
        {"no": no, "seats": seats, "progress": {"able": 0, "total": total}}
    )


def test_the_average_compares_the_same_reviewers_in_both_rounds() -> None:
    # The EA answered in round 1 but not in the last round: it must not drag draft 1 down.
    rounds = [
        board(1, {"cfo": 6.0, "vp": 7.0, "ea": 4.0}),
        board(3, {"cfo": 7.0, "vp": 8.0, "ea": None}),
    ]
    number = score_number(rounds)
    assert number.value == "6.5 → 7.5"
    assert number.note.endswith("(2 of 3 reviewers answered in both rounds)")
    assert headline(rounds, 2) == "Draft 1 scored 6.5. After 2 revision rounds it scored 7.5."


def test_no_reviewer_in_both_rounds_shows_a_dash_not_a_number() -> None:
    rounds = [board(1, {"cfo": 6.0, "vp": None}), board(2, {"cfo": None, "vp": 8.0})]
    number = score_number(rounds)
    assert (number.value, number.note) == ("—", "No reviewer answered in both rounds")


def test_when_every_reviewer_answered_both_rounds_there_is_no_note() -> None:
    rounds = [board(1, {"cfo": 6.0, "vp": 7.0}), board(2, {"cfo": 7.0, "vp": 8.0})]
    number = score_number(rounds)
    assert (number.value, number.note) == ("6.5 → 7.5", "CFO, VP")
    assert score_number(rounds[:1]).value == "6.5"
