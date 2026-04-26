"""Tiny WebSocket client for the Hestia /ws endpoint.

Connects to ``ws://localhost:8000/ws`` (configurable via the ``HESTIA_WS``
env var) and prints every event the server pushes, prefixed with a local
timestamp. Stays alive until Ctrl-C.

Use this alongside the curl smoke tests or the touchscreen UI to watch
the event flow in real time::

    # Terminal 1
    make run

    # Terminal 2
    uv run python tests/ws_test_client.py
    # or:  make ws-test

    # Terminal 3
    bash tests/api_curl_tests.sh
    # observe events stream into terminal 2
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from datetime import datetime

try:
    import websockets
except ImportError as exc:  # pragma: no cover
    print(
        "ws_test_client requires the 'websockets' package. Run:\n"
        "    uv add websockets",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


WS_URL = os.environ.get("HESTIA_WS", "ws://localhost:8000/ws")


def _stamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


async def listen(url: str) -> None:
    print(f"[{_stamp()}] connecting to {url}")
    async with websockets.connect(url) as ws:
        print(f"[{_stamp()}] connected; press Ctrl-C to exit")
        try:
            async for message in ws:
                try:
                    payload = json.loads(message)
                    pretty = json.dumps(payload, indent=2)
                except Exception:
                    pretty = message
                print(f"[{_stamp()}] event:")
                print(pretty)
                print("-" * 60)
        except asyncio.CancelledError:
            pass


def _install_sigint(loop: asyncio.AbstractEventLoop) -> None:
    """Translate Ctrl-C into a clean loop shutdown."""

    def handler() -> None:
        for task in asyncio.all_tasks(loop):
            task.cancel()

    try:
        loop.add_signal_handler(signal.SIGINT, handler)
    except NotImplementedError:  # pragma: no cover - Windows
        pass


def main() -> None:
    loop = asyncio.new_event_loop()
    _install_sigint(loop)
    try:
        loop.run_until_complete(listen(WS_URL))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except Exception as exc:
        print(f"[{_stamp()}] disconnected: {exc!r}", file=sys.stderr)
        sys.exit(1)
    finally:
        loop.close()
        print(f"[{_stamp()}] bye")


if __name__ == "__main__":
    main()
