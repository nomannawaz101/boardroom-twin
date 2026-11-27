"""Pure health summary. Lives in domain/ so the first deploy proves nested imports on Vercel."""

HEALTHY = "ok"


def health_summary(mode: str, features: dict[str, bool], version: str) -> dict[str, object]:
    return {"status": HEALTHY, "mode": mode, "features": dict(features), "version": version}
