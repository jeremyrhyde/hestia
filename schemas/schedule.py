"""Schedule schema.

A schedule is a time-of-day trigger that fires a scene. Schedules are stored
in SQLite, surfaced through the API, and processed by the in-process
scheduler in ``core/scheduler.py``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Schedule(BaseModel):
    """A time-based trigger for a scene.

    Fields:
        id: Stable slug, e.g. ``"morning-weekday"``.
        name: Human-readable label.
        scene_id: ID of the :class:`schemas.scene.Scene` to fire.
        time: Time-of-day in ``"HH:MM"`` 24h format. May be upgraded to a cron
            expression in a future iteration; downstream code should treat the
            value as opaque and use the scheduler's helpers to interpret it.
        days: Optional list of three-letter weekday codes
            (``"mon"``, ``"tue"``, ..., ``"sun"``). ``None`` means every day.
        enabled: Whether the schedule is currently active. Toggleable from the
            UI without deleting the row.

    Example:
        >>> Schedule(id="bedtime", name="Bedtime", scene_id="bedtime",
        ...          time="23:00").model_dump()  # doctest: +ELLIPSIS
        {'id': 'bedtime', 'name': 'Bedtime', 'scene_id': 'bedtime', 'time': '23:00', 'days': None, 'enabled': True}
    """

    id: str
    name: str
    scene_id: str
    time: str
    days: list[str] | None = None
    enabled: bool = Field(default=True)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "bedtime",
                    "name": "Bedtime",
                    "scene_id": "bedtime",
                    "time": "23:00",
                    "days": None,
                    "enabled": True,
                },
                {
                    "id": "morning-weekday",
                    "name": "Weekday morning",
                    "scene_id": "morning",
                    "time": "07:00",
                    "days": ["mon", "tue", "wed", "thu", "fri"],
                    "enabled": True,
                },
            ]
        },
    )
