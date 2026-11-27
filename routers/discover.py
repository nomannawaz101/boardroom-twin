from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from config import RunMode
from llm.client import Runtime
from schemas.requests import DiscoverRequest
from schemas.responses import DiscoverResponse
from services.discover import discover
from services.runtime import current_mode, make_runtime, today

router = APIRouter()


@router.post("/api/discover", response_model=DiscoverResponse)
async def discover_route(
    body: DiscoverRequest,
    runtime: Annotated[Runtime, Depends(make_runtime)],
    mode: Annotated[RunMode, Depends(current_mode)],
    day: Annotated[date, Depends(today)],
) -> DiscoverResponse:
    return await discover(body, runtime, mode, day)
