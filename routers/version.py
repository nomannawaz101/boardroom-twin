from fastapi import APIRouter

import config
from schemas.health import VersionResponse

router = APIRouter()


@router.get("/api/version", response_model=VersionResponse)
def version() -> VersionResponse:
    """Lets anyone check that the deployed commit matches GitHub main."""
    return VersionResponse(commit=config.deployed_commit())
