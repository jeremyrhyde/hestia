"""Standalone integration test for :class:`SpotifyDriver`.

Usage::

    SPOTIFY_CLIENT_ID=... \\
    SPOTIFY_CLIENT_SECRET=... \\
    SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback \\
    SPOTIFY_TARGET_DEVICE=librespot \\
    uv run python tests/test_spotify_driver.py

    uv run python tests/test_spotify_driver.py --mock

Live mode requires:
- A Spotify Web API app (https://developer.spotify.com/dashboard) with the
  redirect URI registered.
- A Spotify Connect endpoint reachable from your account (e.g. ``spotifyd``
  / ``librespot`` running on the Pi). The first time you run this on a fresh
  cache, ``spotipy`` will print an auth URL — open it in a browser, accept,
  copy the URL it redirects to (containing ``?code=...``), and paste it back
  in the terminal. The token is then cached as ``.spotify_cache``.

With ``--mock``, no creds are needed and no network calls are made.

Exits 0 on success and prints ``PASS``; exits 1 on failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drivers.spotify_driver import SpotifyDriver  # noqa: E402
from schemas import DeviceAction  # noqa: E402


def _print_state(label: str, state) -> None:
    print(f"  [{label}] {json.dumps(state.model_dump(), indent=2)}")


async def main(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    target_device: str | None,
    mock: bool,
) -> int:
    print(f"--- SpotifyDriver test (mock={mock}, target={target_device}) ---")

    driver = SpotifyDriver(
        device_id="spotify-test",
        name="Test Spotify",
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        target_device_name=target_device,
        force_mock=mock,
    )

    info = await driver.get_info()
    print(f"  device_info: {info.id} / {info.name} / {info.driver_name}")
    print(f"  capabilities: {[c.value for c in info.capabilities]}")
    _print_state("initial", info.state)

    # play
    state = await driver.execute(DeviceAction(action="play"))
    await asyncio.sleep(2)
    state = await driver.get_state()
    _print_state("after play", state)
    if mock:
        assert state.power is True, "mock play should set power=True"
        assert state.attributes.get("is_playing") is True

    # set volume
    state = await driver.execute(
        DeviceAction(action="set_volume", params={"level": 40})
    )
    _print_state("after set_volume=40", state)
    if mock:
        assert state.attributes.get("volume") == 40

    # pause
    state = await driver.execute(DeviceAction(action="pause"))
    _print_state("after pause", state)
    if mock:
        assert state.power is False
        assert state.attributes.get("is_playing") is False

    # driver-specific verb passthrough
    state = await driver.execute(
        DeviceAction(action="shuffle", params={"enabled": True})
    )
    _print_state("after shuffle=True", state)
    if mock:
        assert state.attributes.get("shuffle") is True

    # unknown verb should raise
    try:
        await driver.execute(DeviceAction(action="explode"))
    except ValueError:
        print("  unknown verb correctly rejected")
    else:
        print("  ERROR: unknown verb was not rejected")
        return 1

    # set_volume with bad payload should raise
    try:
        await driver.execute(
            DeviceAction(action="set_volume", params={"level": "loud"})
        )
    except ValueError:
        print("  set_volume rejected non-int level")
    else:
        print("  ERROR: set_volume accepted non-int level")
        return 1

    await driver.close()
    print("PASS")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--client-id", default=os.environ.get("SPOTIFY_CLIENT_ID", "")
    )
    p.add_argument(
        "--client-secret", default=os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    )
    p.add_argument(
        "--redirect-uri",
        default=os.environ.get(
            "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
        ),
    )
    p.add_argument(
        "--target-device",
        default=os.environ.get("SPOTIFY_TARGET_DEVICE"),
        help='Connect endpoint name (e.g. "librespot")',
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help="Force software-only mode (no Spotify auth required)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.mock and (not args.client_id or not args.client_secret):
        print(
            "ERROR: live mode requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET"
            " (or pass --mock)",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(
        asyncio.run(
            main(
                args.client_id,
                args.client_secret,
                args.redirect_uri,
                args.target_device,
                args.mock,
            )
        )
    )
