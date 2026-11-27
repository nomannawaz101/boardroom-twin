import pytest

from domain.scoring import clamp, match_ratings, scoring_vote, weighted_score
from domain.seats import SEATS_BY_ID
from schemas.answers import Rating

CFO = SEATS_BY_ID["cfo"]
ARCHITECT = SEATS_BY_ID["enterprise_architect"]


def ratings(**values: float) -> list[Rating]:
    return [Rating(criterion=k, rating=v, reason=f"{k} reason") for k, v in values.items()]


def score_of(spec_ratings: list[Rating], spec: object = CFO) -> float:
    return weighted_score(match_ratings(spec, spec_ratings))  # type: ignore[arg-type]


# --- Rule 1: score = sum of rating x weight, rounded to 2 decimals ---


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        # Design screen: 7 x 0.40 + 5 x 0.35 + 3 x 0.25 = 2.80 + 1.75 + 0.75 = 5.30
        ({"cost_clarity": 7, "value": 5, "budget_fit": 3}, 5.30),
        # 10 x 0.40 + 10 x 0.35 + 10 x 0.25 = 10.00
        ({"cost_clarity": 10, "value": 10, "budget_fit": 10}, 10.00),
        # 7.5 x 0.40 + 6 x 0.35 + 8 x 0.25 = 3.00 + 2.10 + 2.00 = 7.10
        ({"cost_clarity": 7.5, "value": 6, "budget_fit": 8}, 7.10),
        # 3.33 x 0.40 + 0 + 0 = 1.332 -> 1.33
        ({"cost_clarity": 3.33, "value": 0, "budget_fit": 0}, 1.33),
    ],
)
def test_cfo_score_matches_a_hand_calculation(values: dict[str, float], expected: float) -> None:
    assert score_of(ratings(**values)) == expected


def test_architect_score_matches_a_hand_calculation() -> None:
    # Design screen: 7 x 0.40 + 4 x 0.35 + 8 x 0.25 = 2.80 + 1.40 + 2.00 = 6.20
    values = {"system_fit": 7, "risk_recovery": 4, "maintainability": 8}
    assert score_of(ratings(**values), ARCHITECT) == 6.20


@pytest.mark.parametrize(("raw", "clamped"), [(-3, 0), (0, 0), (7.5, 7.5), (10, 10), (14, 10)])
def test_ratings_are_clamped(raw: float, clamped: float) -> None:
    assert clamp(raw) == clamped


def test_out_of_range_ratings_are_clamped_before_scoring() -> None:
    # 10 x 0.40 + 0 x 0.35 + 10 x 0.25 = 6.50
    assert score_of(ratings(cost_clarity=99, value=-5, budget_fit=12)) == 6.50


def test_a_missing_criterion_counts_as_zero_and_marks_the_answer_partial() -> None:
    criteria = match_ratings(CFO, ratings(cost_clarity=8, value=8))
    assert [c.rating for c in criteria] == [8, 8, None]
    assert weighted_score(criteria) == 6.00  # 3.20 + 2.80 + 0
    assert any(c.rating is None for c in criteria)


def test_criteria_match_by_label_too_and_unknown_ones_are_ignored() -> None:
    answer = ratings(**{"Cost clarity": 6, "VALUE": 6, "budget-fit": 6, "vibes": 10})
    criteria = match_ratings(CFO, answer)
    assert [c.rating for c in criteria] == [6, 6, 6]
    assert weighted_score(criteria) == 6.00


def test_the_first_rating_of_a_criterion_counts() -> None:
    answer = [Rating(criterion="value", rating=9), Rating(criterion="value", rating=1)]
    assert match_ratings(CFO, answer)[1].rating == 9


# --- Rule 2: the vote ---


@pytest.mark.parametrize(
    ("score", "open_item", "vote"),
    [
        (6.99, False, "rejected"),
        (6.99, True, "rejected"),
        (7.00, False, "approved"),
        (7.00, True, "yes_with_condition"),
        (9.50, False, "approved"),
    ],
)
def test_vote_follows_the_needed_score(score: float, open_item: bool, vote: str) -> None:
    assert scoring_vote(score, 7.0, open_item) == vote


def test_rounding_is_half_up_at_the_boundary() -> None:
    # 6.995 x (0.40 + 0.35 + 0.25) = 6.995 exactly -> 7.00, so the CFO's 7.0 is met.
    assert score_of(ratings(cost_clarity=6.995, value=6.995, budget_fit=6.995)) == 7.00
