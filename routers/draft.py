from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from llm.client import Runtime
from schemas.responses import DraftResponse
from schemas.state import RunState
from services.draft import draft
from services.runtime import make_runtime, today

router = APIRouter()


@router.post("/api/draft", response_model=DraftResponse)
async def draft_route(
    state: RunState,
    runtime: Annotated[Runtime, Depends(make_runtime)],
    day: Annotated[date, Depends(today)],
) -> DraftResponse:
    return await draft(state, runtime, day)
