"""Scoring seats (plan section 4.4, rules 1 and 2). Code computes every score and vote.

A seat only rates its criteria. Ratings are clamped to 0..10; a missing criterion counts as 0
and marks the answer partial; score = sum of rating x weight, rounded to 2 decimals.
"""

from decimal import ROUND_HALF_UP, Decimal

import config
from domain.seats import SeatSpec
from schemas.answers import Rating
from schemas.board import CriterionResult, ScoringVote
from schemas.common import match_key as criterion_key


def clamp(rating: float) -> float:
    return min(max(rating, config.RATING_MIN), config.RATING_MAX)


def match_ratings(spec: SeatSpec, ratings: list[Rating]) -> list[CriterionResult]:
    """One result per criterion of the seat, in registry order. Unknown criteria are ignored;
    if a criterion is rated twice, the first rating counts."""
    found: dict[str, Rating] = {}
    for rating in ratings:
        key = criterion_key(rating.criterion)
        for criterion in spec.criteria:
            if key in (criterion.id, criterion_key(criterion.label)):
                found.setdefault(criterion.id, rating)
    return [
        CriterionResult(
            id=c.id,
            label=c.label,
            weight=c.weight,
            rating=clamp(found[c.id].rating) if c.id in found else None,
            reason=found[c.id].reason if c.id in found else "",
        )
        for c in spec.criteria
    ]


def weighted_score(criteria: list[CriterionResult]) -> float:
    """Exact decimal maths, rounded half up, so a hand calculation always matches (6.995 -> 7.00,
    never 6.99 from binary rounding), which matters right at a needed score."""
    total = sum(
        (Decimal(str(c.rating or 0.0)) * Decimal(str(c.weight)) for c in criteria), Decimal(0)
    )
    step = Decimal(1).scaleb(-config.SCORE_DECIMALS)
    return float(total.quantize(step, rounding=ROUND_HALF_UP))


def is_partial(criteria: list[CriterionResult]) -> bool:
    return any(c.rating is None for c in criteria)


def scoring_vote(score: float, needed: float, has_open_item: bool) -> ScoringVote:
    """Below the needed score: Rejected. At or above it with anything still open (an objection
    of this seat or a stated condition): Yes, with a condition. Otherwise: Approved."""
    if score < needed:
        return "rejected"
    return "yes_with_condition" if has_open_item else "approved"
