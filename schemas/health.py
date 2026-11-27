from pydantic import BaseModel

from config import RunMode


class HealthResponse(BaseModel):
    status: str
    mode: RunMode
    features: dict[str, bool]
    version: str


class VersionResponse(BaseModel):
    commit: str
