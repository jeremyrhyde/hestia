"""Configuration schemas for ``devices.yaml``.

Phase 2D needs a typed shape for the device-configuration file the registry
will read on startup. Defining it as a Pydantic model in ``schemas/`` lets
both the driver layer and the (future) API entry point validate the same
structure.

Example ``devices.yaml``::

    devices:
      - id: relay-desk
        name: Desk lamp
        driver: relay
        params:
          pin: 17
          active_high: true

      - id: kasa-living-room
        name: Living room plug
        driver: kasa
        params:
          host: 192.168.1.42
          kind: plug

      - id: spotify-pi
        name: Spotify on Pi
        driver: spotify
        params:
          client_id: <YOUR_SPOTIFY_CLIENT_ID>
          client_secret: <YOUR_SPOTIFY_CLIENT_SECRET>
          redirect_uri: http://localhost:8888/callback
          target_device_name: librespot
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DeviceConfig(BaseModel):
    """One entry in ``devices.yaml``.

    Fields:
        id: Stable slug used as the URL path parameter
            (``/devices/{id}/...``).
        name: Human-readable label.
        driver: Discriminator selecting which concrete ``DeviceDriver``
            subclass to instantiate. Currently one of ``"relay"``, ``"kasa"``,
            or ``"spotify"``. New driver implementations should add a value
            to this ``Literal``.
        params: Driver-specific keyword arguments forwarded to the driver
            constructor (after ``device_id`` and ``name`` are filled in from
            ``id`` and ``name`` above).
    """

    id: str
    name: str
    driver: Literal["relay", "kasa", "spotify"]
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "relay-desk",
                    "name": "Desk lamp",
                    "driver": "relay",
                    "params": {"pin": 17, "active_high": True},
                },
                {
                    "id": "kasa-living-room",
                    "name": "Living room plug",
                    "driver": "kasa",
                    "params": {"host": "192.168.1.42", "kind": "plug"},
                },
            ]
        },
    )


class DevicesConfig(BaseModel):
    """Top-level shape of ``devices.yaml`` — just a list of ``DeviceConfig``.

    Wrapping the list in a model gives us a single Pydantic entry point,
    automatic validation of every entry, and a place to hang future global
    keys (e.g. ``defaults`` per driver) without breaking the file format.
    """

    devices: list[DeviceConfig] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
