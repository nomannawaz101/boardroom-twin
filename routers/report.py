from fastapi import APIRouter

from schemas.responses import ReportResponse
from schemas.state import RunState
from services.report import report

router = APIRouter()


@router.post("/api/report", response_model=ReportResponse)
def report_route(state: RunState) -> ReportResponse:
    return report(state)
