"""Stage 2: Solution Architect, then Delivery Manager, then Proposal Manager; code checks all.

The Risk & Compliance Analyst joins in Phase 5, running beside the Delivery Manager.
"""

from datetime import date
from typing import Any

from pydantic import BaseModel

from agents import delivery_manager, proposal_manager, solution_architect
from domain.claims import assemble_claims
from domain.cost import choose_efforts, choose_rate, estimate_cost, weeks_to_days
from domain.errors import StepFailed
from domain.timeline import choose_start, plan_schedule
from guards.input import recheck_brief
from guards.output import known_numbers, number_guard, numbers_in, quote_guard
from llm.client import AgentResult, Runtime
from schemas.claims import Claim
from schemas.cost import CostEstimate, PhaseEffort
from schemas.responses import DraftResponse
from schemas.state import RunState
from schemas.timeline import Schedule
from services.logs import log_step

DRAFT_NO = 1
STALE_STATE = "This run is missing its case file. Please start again from the brief."


def require[T: BaseModel](result: AgentResult[T], run_id: str) -> T:
    """An agent that failed after every retry fails the stage, so the page offers a Retry card."""
    log_step(run_id, result.step)
    if result.answer is None:
        raise StepFailed()
    return result.answer


def checked_claims(
    claims: list[Claim],
    brief: str,
    tool_results: list[dict[str, Any]],
    efforts: list[PhaseEffort],
) -> tuple[list[Claim], list[str]]:
    """G10 then G9: quotes must be in the brief; numbers must come from the brief or code."""
    quoted = quote_guard(claims, brief)
    extra = [x for e in efforts for x in (e.no, e.engineers, e.weeks)]
    numbered = number_guard(quoted.claims, known_numbers(brief, tool_results, extra))
    flagged = set(quoted.flagged_ids) | set(numbered.flagged_ids)
    return numbered.claims, [c.id for c in numbered.claims if c.id in flagged]


def schedule_for(start: date | None, efforts: list[PhaseEffort]) -> Schedule | None:
    if start is None or not efforts:
        return None
    return plan_schedule(start, [(e.no, weeks_to_days(e.weeks)) for e in efforts])


def code_results(estimate: CostEstimate | None, schedule: Schedule | None) -> list[dict[str, Any]]:
    return [m.model_dump(mode="json") for m in (estimate, schedule) if m is not None]


async def draft(state: RunState, runtime: Runtime, today: date) -> DraftResponse:
    case_file = state.case_file
    if case_file is None or not case_file.is_brief:
        raise StepFailed(STALE_STATE)
    brief = recheck_brief(state.brief)
    brief_numbers = numbers_in(brief)

    sa = await solution_architect.run(case_file, runtime)
    design = require(sa, state.run_id)

    dm = await delivery_manager.run(case_file, design, runtime)
    sizing = require(dm, state.run_id)
    efforts = choose_efforts(sizing, case_file.team)
    rate, currency = choose_rate(sizing.day_rate, case_file.rate, brief_numbers)
    estimate = estimate_cost(efforts, rate, currency) if efforts and rate else None
    start = choose_start([case_file.start, sizing.start], brief_numbers, today)
    schedule = schedule_for(start, efforts)

    pm = await proposal_manager.run(case_file, design, estimate, schedule, runtime)
    written = require(pm, state.run_id)
    tool_results = [call.result for call in dm.step.tool_calls] + code_results(estimate, schedule)
    claims, retagged = checked_claims(
        assemble_claims(written.claims, estimate, schedule), brief, tool_results, efforts
    )

    return DraftResponse(
        design=design,
        efforts=efforts,
        estimate=estimate,
        schedule=schedule,
        claims=claims,
        draft_no=DRAFT_NO,
        retagged=retagged,
        steps=[
            solution_architect.describe(sa.step, design),
            delivery_manager.describe(dm.step, efforts, estimate),
            proposal_manager.describe(pm.step, claims, len(retagged)),
        ],
    )
