from pydantic import BaseModel

from schemas.state import RunState


class DiscoverRequest(BaseModel):
    """Stage 1 input. Limits are checked by guards/input.py so the user gets the exact message."""

    client: str
    country: str
    brief: str
    confirmed_fake: bool = False
    passcode: str | None = None


class SeatRetryRequest(BaseModel):
    """Retry this seat: run one Not reviewed seat again and recompute the round."""

    state: RunState
    seat_id: str
