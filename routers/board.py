from typing import Annotated

from fastapi import APIRouter, Depends

from llm.client import Runtime
from schemas.requests import SeatRetryRequest
from schemas.responses import BoardResponse
from schemas.state import RunState
from services.board import retry_seat, review
from services.runtime import make_runtime

router = APIRouter()


@router.post("/api/board", response_model=BoardResponse)
async def board_route(
    state: RunState, runtime: Annotated[Runtime, Depends(make_runtime)]
) -> BoardResponse:
    return await review(state, runtime)


@router.post("/api/board/retry", response_model=BoardResponse)
async def board_retry_route(
    body: SeatRetryRequest, runtime: Annotated[Runtime, Depends(make_runtime)]
) -> BoardResponse:
    return await retry_seat(body.state, body.seat_id, runtime)
