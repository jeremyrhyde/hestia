"""Pantheon module contract: unique port, UI at `/`, API under `/api/`,
`/health` at the root, and only relative URLs in the web UI — so the same
files work standalone (http://pi:8003/) and behind Pantheon's gateway
(http://pi:8000/hestia/). See pantheon/docs/module-contract.md."""

from __future__ import annotations

from config import Settings


def test_default_port_is_8003(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert Settings(_env_file=None).PORT == 8003
