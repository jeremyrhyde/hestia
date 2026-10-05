"""Pantheon module contract: unique port, UI at `/`, API under `/api/`,
`/health` at the root, and only relative URLs in the web UI — so the same
files work standalone (http://pi:8003/) and behind Pantheon's gateway
(http://pi:8000/hestia/). See pantheon/docs/module-contract.md."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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


FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

# Root-absolute URLs break under a gateway prefix (/hestia/...).
_ABSOLUTE = [
    re.compile(r'(?:href|src)="/(?!/)'),
    re.compile(r"""fetch\(\s*['"`]/(?!/)"""),
    re.compile(r'"(?:start_url|scope|src)":\s*"/(?!/)'),
    re.compile(r"location\.host\}?/"),
    re.compile(r"""base:\s*['"]/"""),
]
# Vite's dev entry; rewritten relative to `base` at build time.
_ALLOWED = {'<script type="module" src="/src/main.ts"></script>'}


def test_stray_websocket_is_closed_cleanly_not_500(tmp_path):
    client = TestClient(build_app(_settings(tmp_path)))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws"):
            pass


def test_frontend_uses_only_relative_urls():
    files = [
        FRONTEND / "index.html",
        FRONTEND / "vite.config.ts",
        *sorted((FRONTEND / "public").glob("*.webmanifest")),
        *sorted((FRONTEND / "src").rglob("*.ts")),
        *sorted((FRONTEND / "src").rglob("*.svelte")),
    ]
    offenders = []
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip() in _ALLOWED:
                continue
            if any(p.search(line) for p in _ABSOLUTE):
                offenders.append(f"{f.relative_to(FRONTEND)}:{n}: {line.strip()}")
    assert offenders == []


def test_built_ui_is_relative():
    built = FRONTEND / "dist" / "index.html"
    if not built.exists():
        pytest.skip("frontend not built (run `make build`)")
    absolute = re.compile(r'(?:href|src)="/(?!/)')
    assert absolute.findall(built.read_text(encoding="utf-8")) == []


def test_default_web_dir_is_the_frontend_build(monkeypatch):
    monkeypatch.delenv("WEB_DIR", raising=False)
    assert Settings(_env_file=None).WEB_DIR == "./frontend/dist"


def test_ui_cache_headers(tmp_path):
    settings = _settings(tmp_path)
    assets = Path(settings.WEB_DIR) / "assets"
    assets.mkdir()
    (assets / "index-abc123.js").write_text("console.log(1)")
    client = TestClient(build_app(settings))
    hashed = client.get("/assets/index-abc123.js")
    assert hashed.status_code == 200
    assert hashed.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert client.get("/").headers["cache-control"] == "no-cache"


def test_missing_web_dir_warning_names_make_build(tmp_path, caplog):
    settings = Settings(
        _env_file=None,
        WEB_DIR=str(tmp_path / "missing"),
        DB_PATH=str(tmp_path / "t.db"),
        DEVICES_CONFIG_PATH=str(tmp_path / "none.yaml"),
    )
    with caplog.at_level("WARNING"):
        build_app(settings)
    assert "make build" in caplog.text
