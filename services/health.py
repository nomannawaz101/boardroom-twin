import config
from agents.registry import registered_count
from domain.status import health_summary
from schemas.health import HealthResponse
from tools.registry import TOOLS


def health() -> HealthResponse:
    """Never calls a model, so an uptime monitor can ping it for free."""
    summary = health_summary(
        config.run_mode(), config.FEATURES, config.APP_VERSION, registered_count(), len(TOOLS)
    )
    return HealthResponse.model_validate(summary)
