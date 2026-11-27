from datetime import date

from domain.timeline import choose_start, first_working_day, plan_schedule

TODAY = date(2026, 11, 28)


def test_schedule_runs_phases_back_to_back() -> None:
    schedule = plan_schedule(date(2026, 12, 7), [(1, 10), (2, 10)])
    assert [(p.start, p.end, p.working_days) for p in schedule.phases] == [
        (date(2026, 12, 7), date(2026, 12, 18), 10),
        (date(2026, 12, 21), date(2027, 1, 1), 10),
    ]
    assert schedule.go_live == date(2027, 1, 4)
    assert schedule.holidays_checked is False


def test_holidays_push_the_dates_and_mark_the_schedule_checked() -> None:
    holidays = {date(2026, 12, 25), date(2027, 1, 1)}
    schedule = plan_schedule(date(2026, 12, 7), [(1, 20)], holidays)
    assert schedule.go_live == date(2027, 1, 6)
    assert schedule.holidays_checked is True


def test_a_weekend_start_moves_to_monday_and_part_days_round_up() -> None:
    schedule = plan_schedule(date(2026, 12, 5), [(1, 7.5)])
    assert schedule.start == date(2026, 12, 7)
    assert schedule.phases[0].working_days == 8


def test_first_working_day() -> None:
    assert first_working_day(date(2026, 12, 6)) == date(2026, 12, 7)
    assert first_working_day(date(2026, 12, 7)) == date(2026, 12, 7)


def test_start_must_be_a_day_the_brief_states_and_not_past() -> None:
    brief_numbers = {7.0, 600.0}
    assert choose_start([date(2026, 12, 7)], brief_numbers, TODAY) == date(2026, 12, 7)
    assert choose_start([date(2026, 12, 8)], brief_numbers, TODAY) is None
    assert choose_start([date(2025, 12, 7)], brief_numbers, TODAY) is None
    assert choose_start([None, date(2026, 12, 7)], brief_numbers, TODAY) == date(2026, 12, 7)
