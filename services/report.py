"""Stage 5: the final report, assembled by code from the run state. No model call here yet;
the Presales Lead's meeting prep joins in Phase 8."""

from domain.errors import StepFailed
from domain.report import build_report
from schemas.responses import ReportResponse
from schemas.state import RunState

NOT_REVIEWED_YET = "The board has not reviewed the draft yet, so there is nothing to report."


def report(state: RunState) -> ReportResponse:
    if not state.rounds:
        raise StepFailed(NOT_REVIEWED_YET)
    return ReportResponse(report=build_report(state))
