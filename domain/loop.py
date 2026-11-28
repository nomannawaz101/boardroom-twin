"""The revision loop's stop rules (plan section 4.6) and the verdict (section 4.7).

Order matters: a known result always wins over a failed call.
1. Any scoring seat Rejected, or any gate Blocked: Not ready yet.
2. Else any selected seat Not reviewed: Review incomplete (seats that were not selected are
   never in the round, so they never count).
3. Else anything still open, any "Yes, with a condition" or any "Pass, with conditions":
   Approved with conditions.
4. Else: Approved.
The loop never forces approval.
"""

import config
from domain.tracker import unaddressed_blockers
from schemas.board import BoardRound, Verdict, VerdictCode
from schemas.revision import StopDecision, StopReason
from schemas.state import TrackerItem

VERDICT_WORDS: dict[VerdictCode, str] = {
    "not_ready": "Not ready yet",
    "review_incomplete": "Review incomplete",
    "approved_with_conditions": "Approved with conditions",
    "approved": "Approved",
}
CONDITIONAL = ("yes_with_condition", "pass_with_conditions")


def verdict_code(board_round: BoardRound, tracker: list[TrackerItem]) -> VerdictCode:
    seats = board_round.seats
    if any(s.vote == "rejected" or s.outcome == "blocked" for s in seats):
        return "not_ready"
    if any(s.status == "not_reviewed" for s in seats):
        return "review_incomplete"
    open_items = any(t.status == "open" for t in tracker)
    if open_items or any(s.vote in CONDITIONAL or s.outcome in CONDITIONAL for s in seats):
        return "approved_with_conditions"
    return "approved"


def final_verdict(board_round: BoardRound, tracker: list[TrackerItem]) -> Verdict:
    code = verdict_code(board_round, tracker)
    return Verdict(code=code, label=VERDICT_WORDS[code])


STOP_LINES: dict[StopReason, str] = {
    "all_proceed": "Every seat on the board can proceed.",
    "no_gain": "The last round improved nothing: the average scoring-seat score rose by less "
    f"than {config.MIN_GAIN} and no more seats could proceed.",
    "max_rounds": "The limit of Bid Manager rounds was reached.",
    "guard": "The run's cost guard tripped.",
}


def average_score(board_round: BoardRound) -> float | None:
    """Average score of the scoring seats that answered; None if none did."""
    scores = [s.score for s in board_round.seats if s.kind == "scoring" and s.score is not None]
    return round(sum(scores) / len(scores), config.SCORE_DECIMALS) if scores else None


def no_gain(previous: BoardRound, latest: BoardRound) -> bool:
    before, after = average_score(previous), average_score(latest)
    gain = (after or 0.0) - (before or 0.0)
    return gain < config.MIN_GAIN and latest.progress.able <= previous.progress.able


def stop_decision(
    rounds: list[BoardRound],
    bid_rounds_done: int,
    max_bid_rounds: int,
    run_cost: float,
    tracker: list[TrackerItem] | None = None,
) -> StopDecision:
    """Code stops the loop when any rule holds and names every rule that holds. "No gain"
    waits while an open blocker or must-have gate item has never had an applied change."""
    latest = rounds[-1]
    reasons: list[StopReason] = []
    if latest.progress.able == latest.progress.total:
        reasons.append("all_proceed")
    waiting = bool(unaddressed_blockers(tracker or []))
    if len(rounds) >= 2 and no_gain(rounds[-2], latest) and not waiting:
        reasons.append("no_gain")
    if bid_rounds_done >= max_bid_rounds:
        reasons.append("max_rounds")
    if run_cost >= config.RUN_COST_CAP_USD:
        reasons.append("guard")
    return StopDecision(
        stopped=bool(reasons), reasons=reasons, lines=[STOP_LINES[r] for r in reasons]
    )


def max_bid_rounds(lite: bool) -> int:
    return config.LITE_MAX_BID_ROUNDS if lite else config.MAX_BID_ROUNDS
