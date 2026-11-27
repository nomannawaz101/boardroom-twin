"""Working days and the schedule. Pure code: dates are decided here, never by a model."""

import math
from collections.abc import Collection
from datetime import date, timedelta

from schemas.timeline import PhaseDates, Schedule

SATURDAY = 5


def is_working_day(day: date, holidays: Collection[date] = ()) -> bool:
    return day.weekday() < SATURDAY and day not in holidays


def count_working_days(start: date, end: date, holidays: Collection[date] = ()) -> int:
    """Both ends are included; a reversed range has no working days."""
    span = (end - start).days + 1
    return sum(is_working_day(start + timedelta(days=i), holidays) for i in range(max(span, 0)))


def add_working_days(start: date, days: int, holidays: Collection[date] = ()) -> date:
    """Return the date that is `days` working days after `start` (start itself not counted)."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if is_working_day(current, holidays):
            remaining -= 1
    return current


def first_working_day(day: date, holidays: Collection[date] = ()) -> date:
    return day if is_working_day(day, holidays) else add_working_days(day, 1, holidays)


def choose_start(
    candidates: list[date | None], brief_numbers: set[float], today: date
) -> date | None:
    """The first proposed start whose day of the month the brief states and that is not past.

    A model may add the year to "Dec 7", but never a day the brief does not give.
    """
    for candidate in candidates:
        if candidate is not None and candidate >= today and float(candidate.day) in brief_numbers:
            return candidate
    return None


def plan_schedule(
    start: date, phase_days: list[tuple[int, float]], holidays: Collection[date] = ()
) -> Schedule:
    """Phases run one after another; a part day counts as a whole working day.

    Go-live is `start + total working days`, the first working day after the work ends.
    """
    phases: list[PhaseDates] = []
    cursor = first_working_day(start, holidays)
    for no, days in phase_days:
        length = max(math.ceil(days), 1)
        end = add_working_days(cursor, length - 1, holidays)
        phases.append(PhaseDates(no=no, start=cursor, end=end, working_days=length))
        cursor = add_working_days(end, 1, holidays)
    first = phases[0].start if phases else cursor
    return Schedule(start=first, go_live=cursor, phases=phases, holidays_checked=bool(holidays))
