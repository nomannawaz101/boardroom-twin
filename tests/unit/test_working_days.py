from datetime import date

from tools import working_days


def test_two_full_weeks_have_ten_working_days() -> None:
    assert working_days.count_working_days(date(2026, 12, 7), date(2026, 12, 18)) == 10


def test_weekend_only_range_has_none() -> None:
    assert working_days.count_working_days(date(2026, 12, 12), date(2026, 12, 13)) == 0


def test_holidays_are_skipped() -> None:
    christmas = {date(2026, 12, 25)}
    assert working_days.count_working_days(date(2026, 12, 21), date(2026, 12, 25), christmas) == 4


def test_reversed_range_has_none() -> None:
    assert working_days.count_working_days(date(2026, 12, 18), date(2026, 12, 7)) == 0


def test_add_working_days_jumps_the_weekend() -> None:
    assert working_days.add_working_days(date(2026, 12, 11), 1) == date(2026, 12, 14)


def test_add_zero_days_returns_start() -> None:
    assert working_days.add_working_days(date(2026, 12, 7), 0) == date(2026, 12, 7)
