"""Application configuration loaded from environment or `.env`.

Uses `pydantic-settings`. Field names are uppercase to match the convention for
environment variables — e.g. setting `PORT=9000` in the environment overrides
the default. A `.env` file in the project root is also honored automatically.

Example:
    >>> from config import Settings
    >>> s = Settings()
    >>> s.PORT
    8000
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from schemas.config import DevicesConfig


class Settings(BaseSettings):
    """Runtime settings for the home automation server.

    Fields:
        HOST: Address the FastAPI server binds to. Default ``"0.0.0.0"``.
        PORT: TCP port the server listens on. Default ``8000``.
        DB_PATH: Filesystem path to the SQLite database. Default
            ``"./home-auto.db"``.
        LOG_LEVEL: Log level passed to uvicorn / loggers. Default ``"info"``.
        WEB_DIR: Directory containing the static frontend served by FastAPI.
            Default ``"./web"``.
        DEVICES_CONFIG_PATH: YAML file describing the registered devices.
            Default ``"./devices.yaml"``. The Phase 3 API entry point reads
            this file at startup to instantiate drivers.
    """

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DB_PATH: str = "./home-auto.db"
    LOG_LEVEL: str = "info"
    WEB_DIR: str = "./web"
    DEVICES_CONFIG_PATH: str = "./devices.yaml"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


def load_devices_config(path: str | Path | None = None) -> DevicesConfig:
    """Read and validate ``devices.yaml`` at *path*.

    Args:
        path: Path to the YAML file. Defaults to ``Settings().DEVICES_CONFIG_PATH``.

    Returns:
        Validated :class:`DevicesConfig`. Returns an empty
        ``DevicesConfig(devices=[])`` if the file does not exist — this lets
        the server boot for the first time before any hardware is wired up.
    """

    if path is None:
        path = Settings().DEVICES_CONFIG_PATH
    p = Path(path)
    if not p.exists():
        return DevicesConfig(devices=[])

    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return DevicesConfig.model_validate(raw)
