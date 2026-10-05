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
