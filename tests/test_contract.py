"""Pantheon module contract: unique port, UI at `/`, API under `/api/`,
`/health` at the root, and only relative URLs in the web UI — so the same
files work standalone (http://pi:8003/) and behind Pantheon's gateway
(http://pi:8000/hestia/). See pantheon/docs/module-contract.md."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient

from config import Settings
from main import build_app


def test_default_port_is_8003(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert Settings(_env_file=None).PORT == 8003


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


def test_ui_served_at_root_without_shadowing_health(tmp_path):
    client = TestClient(build_app(_settings(tmp_path)))  # no `with`: lifespan not run
    root = client.get("/")
    assert root.status_code == 200
    assert "contract-test-ui" in root.text
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ui/").status_code == 404


WEB = Path(__file__).resolve().parent.parent / "web"

# Root-absolute URLs break under a gateway prefix (/hestia/...).
_ABSOLUTE = [
    re.compile(r'(?:href|src)="/(?!/)'),
    re.compile(r"""(?:fetch|_json)\(\s*['"`]/(?!/)"""),
    re.compile(r'"(?:start_url|scope|src)":\s*"/(?!/)'),
    re.compile(r"location\.host\}?/"),
    re.compile(r"""['"`]/(?:api|health|ws)\b"""),
]


def test_web_ui_uses_only_relative_urls():
    offenders = []
    for f in sorted(WEB.rglob("*")):
        if f.suffix not in {".html", ".js", ".webmanifest"}:
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if any(p.search(line) for p in _ABSOLUTE):
                offenders.append(f"{f.relative_to(WEB)}:{n}: {line.strip()}")
    assert offenders == []
