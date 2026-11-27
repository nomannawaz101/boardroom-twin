from typing import Annotated

from fastapi import APIRouter, Depends

from llm.client import Runtime
from schemas.requests import RevisionRequest
from schemas.responses import RevisionResponse
from services.revise import revise
from services.runtime import make_runtime

router = APIRouter()


@router.post("/api/revise", response_model=RevisionResponse)
async def revise_route(
    body: RevisionRequest, runtime: Annotated[Runtime, Depends(make_runtime)]
) -> RevisionResponse:
    return await revise(body.state, body.round_no, runtime)
