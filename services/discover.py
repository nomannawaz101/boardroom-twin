"""Stage 1: input guards G1 to G8, the Business Analyst, then the board composer."""

import uuid
from datetime import date

from agents import business_analyst
from config import RunMode
from domain.board_composer import compose_board
from domain.errors import NotABrief, StepFailed
from guards.input import check_discover_request
from guards.output import split_signals
from llm.client import Runtime
from schemas.requests import DiscoverRequest
from schemas.responses import DiscoverResponse, InputChecks
from services.logs import log_step


async def discover(
    request: DiscoverRequest, runtime: Runtime, mode: RunMode, today: date
) -> DiscoverResponse:
    checked = check_discover_request(request)  # raises before any AI call
    run_id = uuid.uuid4().hex
    result = await business_analyst.run(checked, today, runtime)
    log_step(run_id, result.step)
    case_file = result.answer
    if case_file is None:
        raise StepFailed()
    if not case_file.is_brief:
        raise NotABrief()
    kept, dropped = split_signals(case_file.warnings, checked.brief)
    case_file = case_file.model_copy(
        update={"client": checked.client, "country": checked.country, "warnings": kept}
    )
    step = business_analyst.describe(result.step, case_file, len(dropped), len(checked.brief))
    return DiscoverResponse(
        run_id=run_id,
        mode=mode,
        brief=checked.brief,
        country_code=checked.country_code,
        checks=InputChecks(injection="notice" if checked.notices else "passed", is_brief=True),
        notices=checked.notices,
        case_file=case_file,
        flags=case_file.flags,
        board_plan=compose_board(case_file.flags),
        ignored_signals=dropped,
        steps=[step],
    )
