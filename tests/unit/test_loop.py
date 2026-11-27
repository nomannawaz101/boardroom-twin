"""Stop rules (plan section 4.6): every reason, and every reason that holds is named."""

import pytest

import config
from domain.loop import average_score, max_bid_rounds, stop_decision
from schemas.board import BoardRound, Progress, SeatResult


def board(no: int, scores: list[float], able: int, total: int = 3) -> BoardRound:
    seats = [
        SeatResult(
            seat_id=f"s{i}", kind="scoring", title=f"S{i}", status="answered", able=True, score=s
        )
        for i, s in enumerate(scores)
    ]
    return BoardRound(no=no, seats=seats, progress=Progress(able=able, total=total))


def reasons(rounds: list[BoardRound], done: int, limit: int = 2, cost: float = 0.0) -> list[str]:
    return stop_decision(rounds, done, limit, cost).reasons


def test_average_score_of_scoring_seats() -> None:
    assert average_score(board(1, [5.3, 7.1], 1)) == 6.2
    empty = BoardRound(no=1, seats=[], progress=Progress(able=0, total=0))
    assert average_score(empty) is None


def test_all_seats_proceed_stops() -> None:
    assert reasons([board(1, [8.0, 8.0], 3)], 0) == ["all_proceed"]


def test_round_one_with_seats_blocked_does_not_stop() -> None:
    assert reasons([board(1, [5.3, 7.1], 1)], 0) == []


@pytest.mark.parametrize(
    "after",
    [
        [5.3, 7.1],  # average 6.20 -> 6.20: no gain at all
        [5.6, 7.1],  # average 6.20 -> 6.35: a gain of 0.15, below 0.2
    ],
)
def test_a_round_that_improves_nothing_stops(after: list[float]) -> None:
    before = board(1, [5.3, 7.1], 1)
    assert reasons([before, board(2, after, 1)], 1) == ["no_gain"]


def test_a_gain_of_at_least_min_gain_continues() -> None:
    before = board(1, [5.3, 7.1], 1)  # average 6.2
    after = board(2, [5.7, 7.1], 1)  # average 6.4: gain 0.2
    assert reasons([before, after], 1) == []


def test_a_small_gain_with_one_more_seat_proceeding_continues() -> None:
    before = board(1, [5.3, 7.1], 1)
    after = board(2, [5.3, 7.2], 2)  # gain 0.05, but one more seat can proceed
    assert reasons([before, after], 1) == []


def test_the_round_limit_stops_after_two_bid_rounds() -> None:
    rounds = [board(1, [5.0, 6.0], 1), board(2, [5.5, 6.5], 1), board(3, [6.0, 7.0], 1)]
    assert reasons(rounds, 2) == ["max_rounds"]


def test_lite_mode_allows_one_bid_round() -> None:
    assert max_bid_rounds(lite=True) == config.LITE_MAX_BID_ROUNDS == 1
    assert max_bid_rounds(lite=False) == config.MAX_BID_ROUNDS == 2


def test_the_cost_guard_stops() -> None:
    assert reasons([board(1, [5.3, 7.1], 1)], 0, cost=config.RUN_COST_CAP_USD) == ["guard"]


def test_every_reason_that_holds_is_named_in_words() -> None:
    decision = stop_decision([board(1, [5.0], 1), board(2, [8.0], 3)], 2, 2, 0.0)
    assert decision.stopped and decision.reasons == ["all_proceed", "max_rounds"]
    assert decision.lines[0] == "Every seat on the board can proceed."
