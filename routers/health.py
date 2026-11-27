from fastapi import APIRouter

from schemas.health import HealthResponse
from services.health import health

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health_route() -> HealthResponse:
    return health()
