"""Spotify Connect driver.

Wraps a Spotify Connect endpoint via the Web API (using ``spotipy``) and
exposes it through the :class:`DeviceDriver` interface.

The reference module in ``reference/spotify_module/`` did three things:
1. Auth + token cache management via :class:`spotipy.oauth2.SpotifyOAuth`.
2. ``spotifyd`` lifecycle management (download, run, stop) so the Pi has a
   Connect endpoint to send commands to.
3. Playback control (play/pause/next/prev/volume).

This driver only handles **#1 and #3**. Step 2 — actually running the Connect
endpoint on the Pi — is a deployment concern (systemd service, separate
process), not a driver concern. The driver just needs to find the named
endpoint among Spotify's ``/me/player/devices`` listing and send commands to
it.

Sync ``spotipy`` calls are wrapped in :func:`asyncio.to_thread` so the driver
methods stay async.

Mock fallback
-------------

If authentication fails (no cached token, bad credentials, or no network),
the driver flips into mock mode where it emits a fake "Mock Song" track and
keeps an internal ``is_playing`` boolean. Real hardware tests can be skipped
on macOS by passing ``--mock`` to the test script.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from drivers.base import DeviceDriver
from schemas.device import (
    DeviceAction,
    DeviceCapability,
    DeviceInfo,
    DeviceState,
    DeviceType,
    StandardAction,
)

logger = logging.getLogger(__name__)

try:
    import spotipy  # type: ignore[import-not-found]
    from spotipy.oauth2 import SpotifyOAuth  # type: ignore[import-not-found]

    _SPOTIPY_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    spotipy = None  # type: ignore[assignment]
    SpotifyOAuth = None  # type: ignore[assignment, misc]
    _SPOTIPY_AVAILABLE = False
    logger.debug("spotipy unavailable at import time: %r", exc)


# Spotify scopes needed for playback control.
_SPOTIFY_SCOPE = (
    "user-read-playback-state user-modify-playback-state "
    "playlist-read-private playlist-read-collaborative"
)

_MOCK_ATTRIBUTES: dict[str, Any] = {
    "track": "Mock Song",
    "artist": "Mock",
    "album": "Mock Album",
    "is_playing": False,
    "volume": 50,
    "mock": True,
}


class SpotifyDriver(DeviceDriver):
    """Driver for a Spotify Connect endpoint controlled via the Web API.

    Args:
        device_id: Stable slug for the device (e.g. ``"spotify-pi"``).
        name: Human-readable label.
        client_id: Spotify Web API client ID.
        client_secret: Spotify Web API client secret.
        redirect_uri: OAuth redirect URI registered with the Spotify
            developer dashboard. The library opens this URL during the
            initial OAuth dance to capture the auth code.
        target_device_name: Name of the Connect endpoint to control (case
            insensitive substring match against Spotify's
            ``/me/player/devices``). If ``None``, the first available device
            is used.
        cache_path: Optional path to the OAuth token cache. Defaults to
            ``.spotify_cache`` in the working directory.
        force_mock: If ``True``, do not even attempt auth — always run in
            mock mode. Used by ``tests/test_spotify_driver.py --mock``.

    OAuth caveat
    ------------

    The first time this driver runs it needs to perform an interactive OAuth
    flow: ``spotipy`` opens a browser to ``accounts.spotify.com`` and the
    user pastes the redirect-URI URL back into the terminal. After that, the
    refresh token is cached at ``cache_path`` and subsequent runs are
    non-interactive. Run the test script once on a desktop with the same
    creds, copy the cache file to the Pi, and the Pi can run headless.
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        target_device_name: str | None = None,
        cache_path: str = ".spotify_cache",
        force_mock: bool = False,
    ) -> None:
        self._id = device_id
        self._name = name
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._target_device_name = target_device_name
        self._cache_path = cache_path

        self._sp: Any = None  # spotipy.Spotify
        self._mock = force_mock or not _SPOTIPY_AVAILABLE
        self._mock_state: dict[str, Any] = dict(_MOCK_ATTRIBUTES)
        self._target_device_id: str | None = None

        if self._mock:
            logger.warning(
                "SpotifyDriver(%s): running in MOCK mode (force_mock=%s, spotipy=%s)",
                device_id,
                force_mock,
                _SPOTIPY_AVAILABLE,
            )

    # -- helpers --------------------------------------------------------

    async def _ensure_client(self) -> Any:
        """Build the spotipy client lazily on first use."""

        if self._mock:
            return None
        if self._sp is not None:
            return self._sp

        try:
            auth_manager = SpotifyOAuth(
                client_id=self._client_id,
                client_secret=self._client_secret,
                redirect_uri=self._redirect_uri,
                scope=_SPOTIFY_SCOPE,
                cache_path=self._cache_path,
                open_browser=False,
            )
            self._sp = spotipy.Spotify(auth_manager=auth_manager)
            # Tickle the API once to validate the token / surface auth errors
            # early (instead of on first execute call).
            await asyncio.to_thread(self._sp.current_user)
        except Exception as exc:  # noqa: BLE001 - any failure → mock
            logger.warning(
                "SpotifyDriver(%s): auth failed (%r) — switching to MOCK mode",
                self._id,
                exc,
            )
            self._mock = True
            self._sp = None
            return None
        return self._sp

    async def _resolve_target_device_id(self) -> str | None:
        """Find the Connect device ID to send commands to."""

        if self._mock or self._sp is None:
            return None
        if self._target_device_id is not None:
            return self._target_device_id

        try:
            payload = await asyncio.to_thread(self._sp.devices)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SpotifyDriver(%s): listing devices failed: %r", self._id, exc
            )
            return None

        devices = payload.get("devices", []) if payload else []
        if not devices:
            logger.warning(
                "SpotifyDriver(%s): no Spotify Connect devices visible to this account",
                self._id,
            )
            return None

        if self._target_device_name:
            needle = self._target_device_name.lower()
            for dev in devices:
                if needle in dev["name"].lower():
                    self._target_device_id = dev["id"]
                    return self._target_device_id
            logger.warning(
                "SpotifyDriver(%s): target device %r not found; using first available (%s)",
                self._id,
                self._target_device_name,
                devices[0]["name"],
            )

        self._target_device_id = devices[0]["id"]
        return self._target_device_id

    async def _read_state(self) -> DeviceState:
        if self._mock:
            return DeviceState(
                power=bool(self._mock_state.get("is_playing", False)),
                attributes=dict(self._mock_state),
            )

        client = await self._ensure_client()
        if client is None:
            return DeviceState(power=False, attributes=dict(_MOCK_ATTRIBUTES))

        try:
            playback = await asyncio.to_thread(client.current_playback)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SpotifyDriver(%s): current_playback failed (%r)", self._id, exc
            )
            return DeviceState(power=False, attributes={"mock": False})

        if not playback:
            return DeviceState(
                power=False,
                attributes={
                    "track": None,
                    "artist": None,
                    "album": None,
                    "is_playing": False,
                    "volume": None,
                    "mock": False,
                },
            )

        item = playback.get("item") or {}
        device = playback.get("device") or {}
        attrs: dict[str, Any] = {
            "track": item.get("name"),
            "artist": ", ".join(a["name"] for a in item.get("artists", []))
            if item
            else None,
            "album": (item.get("album") or {}).get("name"),
            "is_playing": bool(playback.get("is_playing")),
            "volume": device.get("volume_percent"),
            "device_name": device.get("name"),
            "mock": False,
        }
        return DeviceState(power=bool(playback.get("is_playing")), attributes=attrs)

    # -- DeviceDriver contract -----------------------------------------

    async def get_info(self) -> DeviceInfo:
        return DeviceInfo(
            id=self._id,
            name=self._name,
            device_type=DeviceType.MEDIA,
            driver_name="SpotifyDriver",
            capabilities=await self.get_capabilities(),
            state=await self.get_state(),
        )

    async def get_state(self) -> DeviceState:
        return await self._read_state()

    async def execute(self, action: DeviceAction) -> DeviceState:
        match action.action:
            case StandardAction.PLAY:
                await self._do_play()
            case StandardAction.PAUSE:
                await self._do_pause()
            case StandardAction.SKIP:
                await self._do_skip()
            case StandardAction.PREVIOUS:
                await self._do_previous()
            case StandardAction.SET_VOLUME:
                level = (action.params or {}).get("level")
                if not isinstance(level, int) or not 0 <= level <= 100:
                    raise ValueError(
                        "SpotifyDriver: set_volume requires params={'level': int 0-100}"
                    )
                await self._do_set_volume(level)
            case "shuffle":
                # Driver-specific verb: demonstrates open-extension pattern.
                enabled = (action.params or {}).get("enabled")
                if not isinstance(enabled, bool):
                    raise ValueError(
                        "SpotifyDriver: shuffle requires params={'enabled': bool}"
                    )
                await self._do_set_shuffle(enabled)
            case _:
                raise ValueError(
                    f"SpotifyDriver does not support action {action.action!r}"
                )
        return await self._read_state()

    async def get_capabilities(self) -> list[DeviceCapability]:
        return [DeviceCapability.MEDIA_CONTROL]

    async def close(self) -> None:
        """No-op lifecycle hook; spotipy holds no persistent connection."""

        self._sp = None

    # -- internal action helpers ---------------------------------------

    async def _do_play(self) -> None:
        if self._mock:
            self._mock_state["is_playing"] = True
            return
        client = await self._ensure_client()
        if client is None:
            self._mock_state["is_playing"] = True
            return
        device_id = await self._resolve_target_device_id()
        if device_id is None:
            logger.warning(
                "SpotifyDriver(%s): play skipped — no target device resolved",
                self._id,
            )
            return

        # Prefer transfer_playback: it moves the existing playback session to
        # the target device. start_playback only resumes an already-playing
        # context — if nothing was playing, it 204s silently with no audio.
        try:
            await asyncio.to_thread(
                client.transfer_playback, device_id, force_play=True
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "SpotifyDriver(%s): transfer_playback failed (%r); falling back to start_playback",
                self._id,
                exc,
            )

        try:
            await asyncio.to_thread(client.start_playback, device_id=device_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SpotifyDriver(%s): play failed (%r)", self._id, exc)

    async def _do_pause(self) -> None:
        if self._mock:
            self._mock_state["is_playing"] = False
            return
        client = await self._ensure_client()
        if client is None:
            self._mock_state["is_playing"] = False
            return
        device_id = await self._resolve_target_device_id()
        try:
            await asyncio.to_thread(client.pause_playback, device_id=device_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SpotifyDriver(%s): pause failed (%r)", self._id, exc)

    async def _do_skip(self) -> None:
        if self._mock:
            self._mock_state["track"] = "Mock Song (next)"
            return
        client = await self._ensure_client()
        if client is None:
            return
        device_id = await self._resolve_target_device_id()
        try:
            await asyncio.to_thread(client.next_track, device_id=device_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SpotifyDriver(%s): skip failed (%r)", self._id, exc)

    async def _do_previous(self) -> None:
        if self._mock:
            self._mock_state["track"] = "Mock Song (prev)"
            return
        client = await self._ensure_client()
        if client is None:
            return
        device_id = await self._resolve_target_device_id()
        try:
            await asyncio.to_thread(client.previous_track, device_id=device_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SpotifyDriver(%s): previous failed (%r)", self._id, exc)

    async def _do_set_volume(self, level: int) -> None:
        if self._mock:
            self._mock_state["volume"] = level
            return
        client = await self._ensure_client()
        if client is None:
            self._mock_state["volume"] = level
            return
        device_id = await self._resolve_target_device_id()
        try:
            await asyncio.to_thread(client.volume, level, device_id=device_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SpotifyDriver(%s): set_volume failed (%r)", self._id, exc
            )

    async def _do_set_shuffle(self, enabled: bool) -> None:
        if self._mock:
            self._mock_state["shuffle"] = enabled
            return
        client = await self._ensure_client()
        if client is None:
            self._mock_state["shuffle"] = enabled
            return
        device_id = await self._resolve_target_device_id()
        try:
            await asyncio.to_thread(client.shuffle, enabled, device_id=device_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "SpotifyDriver(%s): shuffle failed (%r)", self._id, exc
            )
