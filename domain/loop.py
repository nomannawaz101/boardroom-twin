"""The verdict (plan section 4.7). The revision loop itself joins this module in Phase 4.

Order matters: a known result always wins over a failed call.
1. Any scoring seat Rejected, or any gate Blocked: Not ready yet.
2. Else any selected seat Not reviewed: Review incomplete (seats that were not selected are
   never in the round, so they never count).
3. Else anything still open, any "Yes, with a condition" or any "Pass, with conditions":
   Approved with conditions.
4. Else: Approved.
The loop never forces approval.
"""

from schemas.board import BoardRound, Verdict, VerdictCode
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
