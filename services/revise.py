"""Stage 4: one Bid Manager round, then one re-vote of every selected seat (plan section 4.6).

Vercel keeps nothing between requests, so each request is one round and the run state travels
in the browser. Code refuses a round that does not follow the last one or comes after the loop
stopped, so there are never more than 3 board votes.
"""

from agents import bid_manager
from domain.errors import InputBlocked, StepFailed
from domain.loop import final_verdict
from domain.revision import answered_ids, apply_bid_changes
from guards.input import recheck_brief
from guards.output import known_numbers, number_guard, quote_guard
from llm.client import Runtime
from schemas.claims import Claim
from schemas.responses import RevisionResponse
from schemas.revision import AppliedChange, BidRound
from schemas.state import RunState
from services.board import Draft, decide_stop, require_draft, vote
from services.logs import log_step

NO_BOARD = "The board has not reviewed the draft yet. Please run the board first."
WRONG_ROUND = "That revision round does not follow the last one."
STOPPED = "Code already stopped the revision loop for this run."


def check_round(state: RunState, round_no: int) -> None:
    if not state.rounds:
        raise StepFailed(NO_BOARD)
    if round_no != len(state.revisions) + 1:
        raise InputBlocked(WRONG_ROUND)
    if state.stop is not None and state.stop.stopped:
        raise InputBlocked(STOPPED)
    if decide_stop(state, state.rounds, len(state.revisions), []).stopped:
        raise InputBlocked(STOPPED)


def guard_changed(
    claims: list[Claim], changes: list[AppliedChange], brief: str, state: RunState
) -> list[Claim]:
    """G10 and G9 on what the Bid Manager wrote: an invented quote or number becomes TO CONFIRM.
    Claims that did not change keep the tags the draft stage gave them."""
    changed = {c.claim_id for c in changes if c.outcome == "applied" and c.new_text}
    code_values = [m.model_dump(mode="json") for m in (state.estimate, state.schedule) if m]
    phases = state.estimate.phases if state.estimate else []
    extra = [x for p in phases for x in (p.no, p.engineers, p.days)]
    known = known_numbers(brief, code_values, extra)
    subset = [c for c in claims if c.id in changed]
    checked = number_guard(quote_guard(subset, brief).claims, known).claims
    by_id = {c.id: c for c in checked}
    return [by_id.get(c.id, c) for c in claims]


async def revise(state: RunState, round_no: int, runtime: Runtime) -> RevisionResponse:
    case_file, plan = require_draft(state)
    check_round(state, round_no)
    brief = recheck_brief(state.brief)
    open_now = [t for t in state.tracker if t.status == "open"]
    manager = await bid_manager.run(open_now, state.claims, case_file, plan, runtime)
    log_step(state.run_id, manager.step)
    if manager.answer is None:
        raise StepFailed()
    claims, changes, tracker = apply_bid_changes(
        state.claims, state.tracker, manager.answer.changes, round_no
    )
    claims = guard_changed(claims, changes, brief, state)
    draft = Draft(claims=claims, draft_no=state.draft_no + 1, changes=changes)
    board_round, tracker, seat_steps = await vote(state, draft, tracker, round_no + 1, runtime)
    steps = [bid_manager.describe(manager.step, changes, round_no), *seat_steps]
    return RevisionResponse(
        bid_round=BidRound(
            no=round_no, draft_no=draft.draft_no, changes=changes, answered=answered_ids(changes)
        ),
        round=board_round,
        claims=claims,
        draft_no=draft.draft_no,
        tracker=tracker,
        verdict=final_verdict(board_round, tracker),
        stop=decide_stop(state, [*state.rounds, board_round], round_no, steps),
        steps=steps,
    )
