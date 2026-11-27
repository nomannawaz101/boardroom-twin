from fastapi import APIRouter

import config
from domain.status import health_summary
from schemas.health import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Never calls a model, so an uptime monitor can ping it for free."""
    summary = health_summary(config.run_mode(), config.FEATURES, config.APP_VERSION)
    return HealthResponse.model_validate(summary)
