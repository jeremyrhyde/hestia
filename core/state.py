"""SQLite-backed persistence layer.

The :class:`StateStore` owns the database connection and exposes async
CRUD methods for the four stored entity types:

- ``devices``  — current ``DeviceInfo`` per device
- ``scenes``   — ``Scene`` definitions
- ``schedules``— ``Schedule`` definitions
- ``event_log``— append-only history of every ``Event`` published

Pydantic models are stored as JSON in a single ``data`` column. Returned
rows are reconstructed into Pydantic models so callers never see raw
dicts.

The store also subscribes to the event bus on :meth:`start`. It logs
every published ``Event`` and, when a ``DEVICE_STATE_CHANGED`` event
fires, auto-updates the device row with the new state. This keeps the
database in sync without each subsystem having to call ``upsert_device``
directly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from core.events import EventBus
from schemas.device import DeviceInfo, DeviceState
from schemas.events import Event, EventType
from schemas.scene import Scene
from schemas.schedule import Schedule

logger = logging.getLogger(__name__)


_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS devices (
        id TEXT PRIMARY KEY,
        data JSON NOT NULL,
        updated_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scenes (
        id TEXT PRIMARY KEY,
        data JSON NOT NULL,
        updated_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schedules (
        id TEXT PRIMARY KEY,
        data JSON NOT NULL,
        updated_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        source TEXT NOT NULL,
        device_id TEXT,
        data JSON NOT NULL,
        timestamp TIMESTAMP NOT NULL
    )
    """,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StateStore:
    """Async SQLite façade.

    Construction does no I/O. Call :meth:`start` to open the connection,
    create tables, and wire up bus subscriptions. Call :meth:`close` on
    shutdown.
    """

    def __init__(self, db_path: str, event_bus: EventBus) -> None:
        self._db_path = db_path
        self._bus = event_bus
        self._conn: aiosqlite.Connection | None = None
        # Subscriptions we registered, so close() can unsubscribe cleanly.
        self._subscriptions: list[tuple[EventType, Any]] = []

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def connection(self) -> aiosqlite.Connection:
        """Return the live connection.

        Raises:
            RuntimeError: if :meth:`start` has not been called yet.
        """

        if self._conn is None:
            raise RuntimeError("StateStore.start() has not been called")
        return self._conn

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Open the SQLite connection, create tables, subscribe to the bus."""

        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(self._db_path)
        # Return rows as tuples is fine; we don't need a row factory because
        # we always read explicit columns.
        for stmt in _SCHEMA_STATEMENTS:
            await self._conn.execute(stmt)
        await self._conn.commit()

        # Subscribe to every known event type for the event log, plus a
        # dedicated handler for state-changed events that updates the
        # devices table.
        for event_type in EventType:
            self._bus.subscribe(event_type, self._on_any_event)
            self._subscriptions.append((event_type, self._on_any_event))

        self._bus.subscribe(
            EventType.DEVICE_STATE_CHANGED, self._on_state_changed
        )
        self._subscriptions.append(
            (EventType.DEVICE_STATE_CHANGED, self._on_state_changed)
        )

    async def close(self) -> None:
        """Unsubscribe from the bus and close the SQLite connection."""

        for event_type, cb in self._subscriptions:
            self._bus.unsubscribe(event_type, cb)
        self._subscriptions.clear()

        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Bus subscribers
    # ------------------------------------------------------------------
    async def _on_any_event(self, event: Event) -> None:
        """Append every published event to ``event_log``."""

        try:
            await self.log_event(event)
        except Exception:  # pragma: no cover - logging path
            logger.exception("failed to log event %s", event.type.value)

    async def _on_state_changed(self, event: Event) -> None:
        """Persist new device state when ``DEVICE_STATE_CHANGED`` fires.

        The event's ``data`` payload is expected to contain a ``state`` key
        holding a serialized :class:`DeviceState` (dict or model). If the
        device is not yet in the table, this is a no-op — devices are
        registered separately via :meth:`upsert_device`.
        """

        if not event.device_id:
            return
        raw_state = event.data.get("state")
        if raw_state is None:
            return

        try:
            new_state = (
                raw_state
                if isinstance(raw_state, DeviceState)
                else DeviceState.model_validate(raw_state)
            )
        except Exception:
            logger.exception(
                "DEVICE_STATE_CHANGED for %s had invalid state payload",
                event.device_id,
            )
            return

        existing = await self.get_device(event.device_id)
        if existing is None:
            # Nothing to update — device hasn't been registered yet.
            return
        existing.state = new_state
        await self.upsert_device(existing)

    # ------------------------------------------------------------------
    # Device CRUD
    # ------------------------------------------------------------------
    async def upsert_device(self, info: DeviceInfo) -> None:
        payload = info.model_dump_json()
        await self.connection.execute(
            """
            INSERT INTO devices (id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (info.id, payload, _now().isoformat()),
        )
        await self.connection.commit()

    async def get_device(self, device_id: str) -> DeviceInfo | None:
        async with self.connection.execute(
            "SELECT data FROM devices WHERE id = ?", (device_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return DeviceInfo.model_validate_json(row[0])

    async def list_devices(self) -> list[DeviceInfo]:
        async with self.connection.execute(
            "SELECT data FROM devices ORDER BY id"
        ) as cursor:
            rows = await cursor.fetchall()
        return [DeviceInfo.model_validate_json(row[0]) for row in rows]

    # ------------------------------------------------------------------
    # Scene CRUD
    # ------------------------------------------------------------------
    async def upsert_scene(self, scene: Scene) -> None:
        payload = scene.model_dump_json()
        await self.connection.execute(
            """
            INSERT INTO scenes (id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (scene.id, payload, _now().isoformat()),
        )
        await self.connection.commit()

    async def get_scene(self, scene_id: str) -> Scene | None:
        async with self.connection.execute(
            "SELECT data FROM scenes WHERE id = ?", (scene_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return Scene.model_validate_json(row[0])

    async def list_scenes(self) -> list[Scene]:
        async with self.connection.execute(
            "SELECT data FROM scenes ORDER BY id"
        ) as cursor:
            rows = await cursor.fetchall()
        return [Scene.model_validate_json(row[0]) for row in rows]

    async def delete_scene(self, scene_id: str) -> None:
        await self.connection.execute(
            "DELETE FROM scenes WHERE id = ?", (scene_id,)
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Schedule CRUD
    # ------------------------------------------------------------------
    async def upsert_schedule(self, schedule: Schedule) -> None:
        payload = schedule.model_dump_json()
        await self.connection.execute(
            """
            INSERT INTO schedules (id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (schedule.id, payload, _now().isoformat()),
        )
        await self.connection.commit()

    async def get_schedule(self, schedule_id: str) -> Schedule | None:
        async with self.connection.execute(
            "SELECT data FROM schedules WHERE id = ?", (schedule_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return Schedule.model_validate_json(row[0])

    async def list_schedules(self) -> list[Schedule]:
        async with self.connection.execute(
            "SELECT data FROM schedules ORDER BY id"
        ) as cursor:
            rows = await cursor.fetchall()
        return [Schedule.model_validate_json(row[0]) for row in rows]

    async def delete_schedule(self, schedule_id: str) -> None:
        await self.connection.execute(
            "DELETE FROM schedules WHERE id = ?", (schedule_id,)
        )
        await self.connection.commit()

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------
    async def log_event(self, event: Event) -> None:
        # Use mode="json" so datetime/enum values become JSON-friendly
        # primitives instead of raw Python objects.
        data_json = json.dumps(event.data, default=_json_default)
        await self.connection.execute(
            """
            INSERT INTO event_log (type, source, device_id, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.type.value,
                event.source,
                event.device_id,
                data_json,
                event.timestamp.isoformat(),
            ),
        )
        await self.connection.commit()

    async def list_events(self, limit: int | None = None) -> list[Event]:
        """Return logged events newest-last (insertion order)."""

        sql = "SELECT type, source, device_id, data, timestamp FROM event_log ORDER BY id"
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        async with self.connection.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
        events: list[Event] = []
        for type_value, source, device_id, data_json, timestamp in rows:
            events.append(
                Event(
                    type=EventType(type_value),
                    source=source,
                    device_id=device_id,
                    data=json.loads(data_json),
                    timestamp=datetime.fromisoformat(timestamp),
                )
            )
        return events


def _json_default(value: Any) -> Any:
    """JSON encoder fallback for objects ``json.dumps`` can't handle."""

    if isinstance(value, datetime):
        return value.isoformat()
    # Pydantic models with a model_dump method.
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
