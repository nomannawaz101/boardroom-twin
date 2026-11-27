from pydantic import BaseModel

from config import RunMode


class HealthResponse(BaseModel):
    status: str
    mode: RunMode
    features: dict[str, bool]
    version: str
    agents: int
    tools: int
    models: dict[str, str]  # badges of the configured main and fast models


class VersionResponse(BaseModel):
    commit: str
