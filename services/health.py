import config
from agents.registry import registered_count
from domain.status import health_summary
from llm.client import model_badge
from schemas.health import HealthResponse
from tools.registry import TOOLS


def configured_badges() -> dict[str, str]:
    """Badges of the configured models, so the start panel names what will really answer."""
    return {
        "main": model_badge(config.model_for_tier("sonnet")),
        "fast": model_badge(config.model_for_tier(config.FAST_TIER)),
    }


def health() -> HealthResponse:
    """Never calls a model, so an uptime monitor can ping it for free."""
    summary = health_summary(
        config.run_mode(), config.FEATURES, config.APP_VERSION, registered_count(), len(TOOLS)
    )
    return HealthResponse.model_validate(summary | {"models": configured_badges()})
