"""Cost maths: people x days x rate. Code decides every cost; a model never does."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import config
from schemas.answers import DeliveryManagerAnswer
from schemas.case_file import Rate, Team
from schemas.cost import CostEstimate, PhaseCost, PhaseEffort

CENT = Decimal(1).scaleb(-config.MONEY_DECIMALS)


class CostInputError(ValueError):
    """Effort or rate that cannot be priced (zero, negative or missing)."""


@dataclass(frozen=True)
class PhaseDays:
    no: int
    engineers: int
    days: float


def to_money(value: Decimal) -> float:
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


def weeks_to_days(weeks: float) -> float:
    return weeks * config.WORKING_DAYS_PER_WEEK


def price_phase(phase: PhaseDays, day_rate: float) -> PhaseCost:
    if phase.engineers <= 0 or phase.days <= 0 or day_rate <= 0:
        raise CostInputError("engineers, days and rate must all be above zero")
    cost = Decimal(str(phase.engineers)) * Decimal(str(phase.days)) * Decimal(str(day_rate))
    return PhaseCost(
        no=phase.no, engineers=phase.engineers, days=phase.days, rate=day_rate, cost=to_money(cost)
    )


def price_phases(phases: list[PhaseDays], day_rate: float, currency: str) -> CostEstimate:
    if not phases:
        raise CostInputError("at least one phase is needed")
    priced = [price_phase(p, day_rate) for p in phases]
    total = sum((Decimal(str(p.cost)) for p in priced), Decimal(0))
    engineer_days = sum(p.engineers * p.days for p in priced)
    return CostEstimate(
        phases=priced, engineer_days=engineer_days, total=to_money(total), currency=currency
    )


def estimate_cost(efforts: list[PhaseEffort], day_rate: float, currency: str) -> CostEstimate:
    """Price the Delivery Manager's phases, given in weeks."""
    days = [PhaseDays(e.no, e.engineers, weeks_to_days(e.weeks)) for e in efforts]
    return price_phases(days, day_rate, currency)


def choose_efforts(answer: DeliveryManagerAnswer, team: Team | None) -> list[PhaseEffort]:
    """The Delivery Manager's phases, numbered by code; else the brief's own team.

    The answer's checks already refuse zero engineers or weeks, so every phase can be priced.
    """
    if answer.phases:
        return [
            PhaseEffort(no=i, engineers=p.engineers, weeks=p.weeks)
            for i, p in enumerate(answer.phases, start=1)
        ]
    if team is not None and team.engineers > 0 and team.weeks > 0:
        return [PhaseEffort(no=1, engineers=team.engineers, weeks=team.weeks)]
    return []


def choose_rate(
    proposed: float | None, stated: Rate | None, brief_numbers: set[float]
) -> tuple[float | None, str]:
    """A day rate is used only if the brief states that number (guard G9 applied to money)."""
    currency = stated.currency if stated is not None else config.DEFAULT_CURRENCY
    candidates = [proposed, stated.amount if stated is not None else None]
    for rate in candidates:
        if rate is not None and rate > 0 and round(rate, config.MONEY_DECIMALS) in brief_numbers:
            return rate, currency
    return None, currency
