"""Stage 3: the board chosen for this brief reviews the draft, all seats at the same time.

Only seats in board_plan run; unselected seats never run and never count. Code turns every
answer into a score, vote or gate outcome and fills the objection tracker.
"""

import asyncio
from typing import cast

from agents import board_seat
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
from domain.loop import final_verdict
from llm.client import AgentResult, Runtime
from schemas.answers import GateSeatAnswer, ScoringSeatAnswer
from schemas.board import BoardPlan, PlannedSeat, SeatResult
from schemas.case_file import CaseFile
from schemas.responses import BoardResponse
from schemas.state import RunState, TrackerItem
from schemas.step import StepRecord
from services.logs import log_step

FIRST_ROUND = 1
NO_DRAFT = "There is no draft to review yet. Please run the proposal team first."
TOO_FEW = "Fewer than 2 board seats answered, so the board could not review the draft."
NOT_RETRYABLE = "That seat is not waiting for a retry."

SeatAgent = AgentResult[ScoringSeatAnswer] | AgentResult[GateSeatAnswer]


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


async def ask(
    seat: PlannedSeat, case_file: CaseFile, state: RunState, runtime: Runtime
) -> SeatAgent:
    return await board_seat.run(seat, state.claims, case_file, state.draft_no, runtime)


def described(agent: SeatAgent, result: SeatResult, state: RunState) -> StepRecord:
    log_step(state.run_id, agent.step)
    return board_seat.describe(agent.step, result, state.draft_no, len(state.claims))


async def review(state: RunState, runtime: Runtime) -> BoardResponse:
    case_file, plan = require_draft(state)
    seats = plan.seats
    answers = await asyncio.gather(*(ask(seat, case_file, state, runtime) for seat in seats))
    claim_ids = {c.id for c in state.claims}
    tracker: list[TrackerItem] = []
    results: list[SeatResult] = []
    steps: list[StepRecord] = []
    for seat, agent in zip(seats, answers, strict=True):
        result, tracker = assess(seat, agent, claim_ids, tracker, FIRST_ROUND)
        results.append(result)
        steps.append(described(agent, result, state))
    if answered_count(results) < MIN_SEATS_ANSWERED:
        raise StepFailed(TOO_FEW)
    board_round = build_round(FIRST_ROUND, results)
    verdict = final_verdict(board_round, tracker)
    return BoardResponse(round=board_round, tracker=tracker, verdict=verdict, steps=steps)


async def retry_seat(state: RunState, seat_id: str, runtime: Runtime) -> BoardResponse:
    """Run one Not reviewed seat again; its new items join the tracker and the round is
    recomputed from all seats."""
    case_file, plan = require_draft(state)
    seat = next((s for s in plan.seats if s.id == seat_id), None)
    latest = state.rounds[-1] if state.rounds else None
    current = next((s for s in latest.seats if s.seat_id == seat_id), None) if latest else None
    if seat is None or latest is None or current is None or current.status != "not_reviewed":
        raise InputBlocked(NOT_RETRYABLE)
    agent = await ask(seat, case_file, state, runtime)
    claim_ids = {c.id for c in state.claims}
    result, tracker = assess(seat, agent, claim_ids, state.tracker, latest.no)
    step = described(agent, result, state)
    board_round = replace_seat(latest, result)
    verdict = final_verdict(board_round, tracker)
    return BoardResponse(round=board_round, tracker=tracker, verdict=verdict, steps=[step])
