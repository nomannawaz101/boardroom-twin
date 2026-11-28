"""Board votes: the board chosen for this brief reviews a draft, all seats at the same time.

Only seats in board_plan run; unselected seats never run and never count. Code turns every
answer into a score, vote or gate outcome and keeps the objection tracker. The same vote serves
board round 1, every re-vote after a Bid Manager round, and Retry this seat.
"""

import asyncio
from dataclasses import dataclass
from typing import cast

from agents import board_seat
from agents.board_seat import Review
from config import MIN_SEATS_ANSWERED
from domain.board_round import (
    answered_count,
    build_round,
    not_reviewed,
    replace_seat,
    review_gate,
    review_scoring,
)
from domain.errors import InputBlocked, StepFailed
from domain.loop import final_verdict, max_bid_rounds, stop_decision
from domain.tracker import flag_decisions, open_items
from llm.client import AgentResult, Runtime
from schemas.answers import GateSeatAnswer, ScoringSeatAnswer
from schemas.board import BoardPlan, BoardRound, PlannedSeat, SeatResult
from schemas.case_file import CaseFile
from schemas.claims import Claim
from schemas.responses import BoardResponse
from schemas.revision import AppliedChange, StopDecision
from schemas.state import RunState, TrackerItem
from schemas.step import StepRecord
from services.logs import log_step

FIRST_ROUND = 1
NO_DRAFT = "There is no draft to review yet. Please run the proposal team first."
TOO_FEW = "Fewer than 2 board seats answered, so the board could not review the draft."
NOT_RETRYABLE = "That seat is not waiting for a retry."

SeatAgent = AgentResult[ScoringSeatAnswer] | AgentResult[GateSeatAnswer]


@dataclass(frozen=True)
class Draft:
    """The draft a vote is about."""

    claims: list[Claim]
    draft_no: int
    changes: list[AppliedChange]


def require_draft(state: RunState) -> tuple[CaseFile, BoardPlan]:
    if state.case_file is None or state.board_plan is None or not state.claims:
        raise StepFailed(NO_DRAFT)
    return state.case_file, state.board_plan


def assess(
    seat: PlannedSeat,
    result: SeatAgent,
    claim_ids: set[str],
    tracker: list[TrackerItem],
    round_no: int,
) -> tuple[SeatResult, list[TrackerItem]]:
    """Turn one seat's answer into its result. No answer means Not reviewed, except that a gate
    whose last reply only left items out still counts its known answers: a must-have Not met
    blocks (a known result wins); otherwise it is Not reviewed with a partial answer."""
    if result.answer is None and seat.kind == "gate" and result.unchecked is not None:
        return review_gate(seat, cast(GateSeatAnswer, result.unchecked), tracker, round_no)
    if result.answer is None:
        return not_reviewed(seat), tracker
    if seat.kind == "scoring":
        answer = cast(ScoringSeatAnswer, result.answer)
        return review_scoring(seat, answer, claim_ids, tracker, round_no)
    return review_gate(seat, cast(GateSeatAnswer, result.answer), tracker, round_no)


def review_for(
    seat: PlannedSeat, case_file: CaseFile, draft: Draft, tracker: list[TrackerItem]
) -> Review:
    return Review(
        claims=draft.claims,
        case_file=case_file,
        draft_no=draft.draft_no,
        open_items=open_items(tracker, seat.id),
        changes=draft.changes,
    )


def described(run_id: str, agent: SeatAgent, result: SeatResult, draft: Draft) -> StepRecord:
    log_step(run_id, agent.step)
    return board_seat.describe(agent.step, result, draft.draft_no, len(draft.claims))


async def vote(
    state: RunState, draft: Draft, tracker: list[TrackerItem], round_no: int, runtime: Runtime
) -> tuple[BoardRound, list[TrackerItem], list[StepRecord]]:
    """Every selected seat reviews the draft at the same time; code assesses them in plan
    order. Fewer than 2 answers stops the run with a Retry card (rule 4.4.6)."""
    case_file, plan = require_draft(state)
    reviews = [review_for(seat, case_file, draft, tracker) for seat in plan.seats]
    answers = await asyncio.gather(
        *(
            board_seat.run(seat, review, runtime)
            for seat, review in zip(plan.seats, reviews, strict=True)
        )
    )
    claim_ids = {c.id for c in draft.claims}
    results: list[SeatResult] = []
    steps: list[StepRecord] = []
    for seat, agent in zip(plan.seats, answers, strict=True):
        result, tracker = assess(seat, agent, claim_ids, tracker, round_no)
        results.append(result)
        steps.append(described(state.run_id, agent, result, draft))
    if answered_count(results) < MIN_SEATS_ANSWERED:
        raise StepFailed(TOO_FEW)
    return build_round(round_no, results), flag_decisions(tracker, contract_type(state)), steps


def run_cost(steps: list[StepRecord]) -> float:
    return sum(s.cost_usd for s in steps)


def decide_stop(
    state: RunState,
    rounds: list[BoardRound],
    bid_rounds_done: int,
    new_steps: list[StepRecord],
    tracker: list[TrackerItem],
) -> StopDecision:
    limit = max_bid_rounds(lite=state.mode == "lite")
    cost = run_cost([*state.steps, *new_steps])
    return stop_decision(rounds, bid_rounds_done, limit, cost, tracker)


def contract_type(state: RunState) -> str | None:
    return state.flags.contract_type if state.flags else None


async def review(state: RunState, runtime: Runtime) -> BoardResponse:
    """Board round 1 on draft 1. The tracker starts here."""
    require_draft(state)
    draft = Draft(claims=state.claims, draft_no=state.draft_no, changes=[])
    board_round, tracker, steps = await vote(state, draft, [], FIRST_ROUND, runtime)
    return BoardResponse(
        round=board_round,
        tracker=tracker,
        verdict=final_verdict(board_round, tracker),
        stop=decide_stop(state, [board_round], 0, steps, tracker),
        steps=steps,
    )


async def retry_seat(state: RunState, seat_id: str, runtime: Runtime) -> BoardResponse:
    """Run one Not reviewed seat of the latest vote again; its re-reads and new items join the
    tracker and the round is recomputed from all seats."""
    case_file, plan = require_draft(state)
    seat = next((s for s in plan.seats if s.id == seat_id), None)
    latest = state.rounds[-1] if state.rounds else None
    current = next((s for s in latest.seats if s.seat_id == seat_id), None) if latest else None
    if seat is None or latest is None or current is None or current.status != "not_reviewed":
        raise InputBlocked(NOT_RETRYABLE)
    changes = state.revisions[-1].changes if state.revisions and latest.no > FIRST_ROUND else []
    draft = Draft(claims=state.claims, draft_no=state.draft_no, changes=changes)
    agent = await board_seat.run(seat, review_for(seat, case_file, draft, state.tracker), runtime)
    claim_ids = {c.id for c in state.claims}
    result, tracker = assess(seat, agent, claim_ids, state.tracker, latest.no)
    tracker = flag_decisions(tracker, contract_type(state))
    step = described(state.run_id, agent, result, draft)
    board_round = replace_seat(latest, result)
    rounds = [*state.rounds[:-1], board_round]
    return BoardResponse(
        round=board_round,
        tracker=tracker,
        verdict=final_verdict(board_round, tracker),
        stop=decide_stop(state, rounds, len(state.revisions), [step], tracker),
        steps=[step],
    )
