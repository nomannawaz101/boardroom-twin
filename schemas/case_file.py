"""The Business Analyst's case file, including `is_brief` and the five board flags."""

from datetime import date
from typing import Annotated, Literal, get_args

from pydantic import BaseModel

import config
from schemas.common import capped, none_if_not_in

ContractType = Literal["fixed", "tm", "other", "none"]
Seniority = Literal["large", "small"]


class BoardFlags(BaseModel):
    """null means unclear, and an unclear flag makes the seat join (plan section 4.2)."""

    personal_data: bool | None = None
    existing_systems: bool | None = None
    contract_type: Annotated[ContractType | None, none_if_not_in(get_args(ContractType))] = None
    function: str | None = None
    seniority: Annotated[Seniority | None, none_if_not_in(get_args(Seniority))] = None


class Signal(BaseModel):
    text: str
    quote: str


class Rate(BaseModel):
    amount: float
    currency: str = "USD"
    unit: str = "engineer-day"


class Team(BaseModel):
    engineers: int
    weeks: float


class CaseFile(BaseModel):
    client: str = ""
    country: str = ""
    is_brief: bool
    goals: Annotated[list[str], capped(config.LIST_CAP_SHORT)] = []
    warnings: Annotated[list[Signal], capped(config.LIST_CAP_MEDIUM)] = []
    rate: Rate | None = None
    team: Team | None = None
    start: date | None = None
    peak: str | None = None
    flags: BoardFlags = BoardFlags()
