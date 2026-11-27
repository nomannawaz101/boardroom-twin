"""Claims: the proposal is a list of these, grouped by the 9 sections."""

from typing import Annotated, Literal, get_args

from pydantic import BaseModel, BeforeValidator

from config import CLAIM_MAX_WORDS
from schemas.common import max_words

Section = Literal[
    "executive_summary",
    "client_situation",
    "proposed_solution",
    "scope",
    "timeline",
    "team_cost",
    "risks",
    "assumptions",
    "next_steps",
]
Origin = Literal["brief", "calculated", "architect", "proposal", "derived", "assumption"]
DEFAULT_ORIGIN: Origin = "derived"
ASSUMPTION_PREFIX = "Confirm with the client: "


def _known_origin(value: object) -> object:
    """An invalid origin from a model becomes `derived` (plan Appendix A)."""
    return value if value in get_args(Origin) else DEFAULT_ORIGIN


SafeOrigin = Annotated[Origin, BeforeValidator(_known_origin)]


class Claim(BaseModel):
    id: str
    section: Section
    text: str
    origin: SafeOrigin = DEFAULT_ORIGIN
    locked: bool = False
    quote: str | None = None


class DraftClaim(BaseModel):
    """A claim as the Proposal Manager writes it; code assigns the id and the lock."""

    section: Section
    text: Annotated[str, max_words(CLAIM_MAX_WORDS)]
    origin: SafeOrigin = DEFAULT_ORIGIN
    quote: str | None = None
