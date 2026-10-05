"""Pantheon module contract: unique port, UI at `/`, API under `/api/`,
`/health` at the root, and only relative URLs in the web UI — so the same
files work standalone (http://pi:8003/) and behind Pantheon's gateway
(http://pi:8000/hestia/). See pantheon/docs/module-contract.md."""

from __future__ import annotations

from config import Settings


def test_default_port_is_8003(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert Settings(_env_file=None).PORT == 8003

from pathlib import Path

from fastapi.routing import APIRoute, APIWebSocketRoute

from main import build_app


def _settings(tmp_path: Path) -> Settings:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>contract-test-ui</title>")
    return Settings(
        _env_file=None,
        WEB_DIR=str(web),
        DB_PATH=str(tmp_path / "t.db"),
        DEVICES_CONFIG_PATH=str(tmp_path / "none.yaml"),
    )


def test_every_route_is_under_api_or_is_health(tmp_path):
    app = build_app(_settings(tmp_path))
    paths = sorted(
        {r.path for r in app.routes if isinstance(r, (APIRoute, APIWebSocketRoute))}
    )
    stray = [p for p in paths if p != "/health" and not p.startswith("/api/")]
    assert stray == []
    assert "/api/ws" in paths
