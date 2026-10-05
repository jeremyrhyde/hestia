from datetime import datetime

from core.scheduler import next_occurrence
from schemas.schedule import Schedule

MON_0800 = datetime(2026, 10, 5, 8, 0)    # a Monday


def sched(id, time, days=None, enabled=True):
    return Schedule(id=id, name=id.title(), scene_id="s", time=time, days=days, enabled=enabled)


def test_next_occurrence_picks_the_soonest_enabled_match():
    schedules = [sched("bedtime", "23:00"), sched("weekend", "09:00", ["sat", "sun"]),
                 sched("off", "08:30", enabled=False)]
    found, at = next_occurrence(schedules, MON_0800)
    assert found.id == "bedtime" and at == datetime(2026, 10, 5, 23, 0)


def test_next_occurrence_rolls_to_the_next_matching_day():
    found, at = next_occurrence([sched("weekend", "09:00", ["sat"])], MON_0800)
    assert at == datetime(2026, 10, 10, 9, 0)


def test_next_occurrence_none():
    assert next_occurrence([], MON_0800) is None


def test_next_occurrence_at_exactly_now_goes_to_tomorrow():
    found, at = next_occurrence([sched("now", "08:00")], MON_0800)
    assert at == datetime(2026, 10, 6, 8, 0)


def test_next_occurrence_uppercase_day_codes_match():
    found, at = next_occurrence([sched("weekend", "09:00", ["SAT"])], MON_0800)
    assert at == datetime(2026, 10, 10, 9, 0)


def test_next_occurrence_skips_times_the_scheduler_never_fires():
    schedules = [sched("a", "25:00"), sched("b", "7:05"), sched("c", "nope"), sched("d", "12:60")]
    assert next_occurrence(schedules, MON_0800) is None
