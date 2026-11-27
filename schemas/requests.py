from pydantic import BaseModel


class DiscoverRequest(BaseModel):
    """Stage 1 input. Limits are checked by guards/input.py so the user gets the exact message."""

    client: str
    country: str
    brief: str
    confirmed_fake: bool = False
    passcode: str | None = None
