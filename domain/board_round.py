"""One board round: each seat's answer turned into a result by code (plan section 4.4).

A seat that fails after retries is Not reviewed: it cannot proceed, it never hides another
seat's known result, and the other seats still count. Progress is "N of M can proceed".
"""

from domain import gates, scoring
from domain.seats import SEATS_BY_ID
from domain.tracker import add_items, gate_drafts, open_items, scoring_drafts
from schemas.answers import GateSeatAnswer, ScoringSeatAnswer
from schemas.board import BoardRound, ChecklistResult, PlannedSeat, Progress, SeatResult
from schemas.state import TrackerItem

BLOCKING_OUTCOME = "blocked"
REJECTED_VOTE = "rejected"
# The words the page shows. Written once, here, by code.
VOTE_WORDS = {
    "approved": "Approved",
    "yes_with_condition": "Yes, with a condition",
    "rejected": "Rejected",
}
OUTCOME_WORDS = {
    "pass": "Pass",
    "pass_with_conditions": "Pass, with conditions",
    "blocked": "Blocked",
}
NOT_REVIEWED_WORDS = "Not reviewed"


def review_scoring(
    seat: PlannedSeat,
    answer: ScoringSeatAnswer,
    claim_ids: set[str],
    tracker: list[TrackerItem],
    round_no: int,
) -> tuple[SeatResult, list[TrackerItem]]:
    spec = SEATS_BY_ID[seat.id]
    needed = spec.needed_score or 0.0
    criteria = scoring.match_ratings(spec, answer.ratings)
    score = scoring.weighted_score(criteria)
    updated = add_items(tracker, scoring_drafts(seat.id, answer.objections, claim_ids), round_no)
    condition = (answer.condition or "").strip() or None
    has_open = bool(open_items(updated, seat.id)) or condition is not None
    vote = scoring.scoring_vote(score, needed, has_open)
    result = SeatResult(
        seat_id=seat.id,
        kind="scoring",
        title=seat.title,
        status="answered",
        able=vote != REJECTED_VOTE,
        partial=scoring.is_partial(criteria),
        criteria=criteria,
        score=score,
        needed=needed,
        vote=vote,
        decision=VOTE_WORDS[vote],
        condition=condition,
        quote=answer.quote.strip(),
    )
    return result, updated


def review_gate(
    seat: PlannedSeat, answer: GateSeatAnswer, tracker: list[TrackerItem], round_no: int
) -> tuple[SeatResult, list[TrackerItem]]:
    items = gates.match_items(SEATS_BY_ID[seat.id], answer.items)
    outcome = gates.gate_outcome(items)
    if outcome is None:
        # Items still missing after the retries and nothing known blocks: undecided.
        return partial_not_reviewed(seat, items), tracker
    updated = add_items(tracker, gate_drafts(seat.id, items, answer.objections), round_no)
    result = SeatResult(
        seat_id=seat.id,
        kind="gate",
        title=seat.title,
        status="answered",
        able=outcome != BLOCKING_OUTCOME,
        partial=gates.is_partial(items),
        items=items,
        outcome=outcome,
        decision=OUTCOME_WORDS[outcome],
        quote=answer.quote.strip(),
    )
    return result, updated


def partial_not_reviewed(seat: PlannedSeat, items: list[ChecklistResult]) -> SeatResult:
    """A gate that left items out even after the retries: Not reviewed, marked partial, with
    the items it did answer shown. It adds no tracker items until it answers in full."""
    return not_reviewed(seat).model_copy(update={"partial": True, "items": items})


def not_reviewed(seat: PlannedSeat) -> SeatResult:
    """Rule 4.4.4: a seat that failed to answer cannot proceed and gets a Retry button."""
    return SeatResult(
        seat_id=seat.id,
        kind=seat.kind,
        title=seat.title,
        status="not_reviewed",
        able=False,
        needed=SEATS_BY_ID[seat.id].needed_score,
        decision=NOT_REVIEWED_WORDS,
    )


def build_round(no: int, results: list[SeatResult]) -> BoardRound:
    progress = Progress(able=sum(r.able for r in results), total=len(results))
    return BoardRound(no=no, seats=results, progress=progress)


def replace_seat(board_round: BoardRound, result: SeatResult) -> BoardRound:
    """After a seat is retried, the round is recomputed from all its seats."""
    seats = [result if s.seat_id == result.seat_id else s for s in board_round.seats]
    return build_round(board_round.no, seats)


def answered_count(results: list[SeatResult]) -> int:
    return sum(r.status == "answered" for r in results)
