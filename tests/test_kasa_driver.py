"""Standalone integration test for :class:`KasaDriver`.

Usage::

    KASA_HOST=192.168.1.42 uv run python tests/test_kasa_driver.py
    uv run python tests/test_kasa_driver.py --host 192.168.1.42
    uv run python tests/test_kasa_driver.py --mock

Live mode requires a Kasa plug or bulb on the same LAN as this machine.
With ``--mock``, no host is needed.

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

from drivers.kasa_driver import KasaDriver  # noqa: E402
from schemas import DeviceAction  # noqa: E402


def _print_state(label: str, state) -> None:
    print(f"  [{label}] {json.dumps(state.model_dump(), indent=2)}")


async def main(host: str, kind: str, mock: bool) -> int:
    print(f"--- KasaDriver test (mock={mock}, host={host}, kind={kind}) ---")

    driver = KasaDriver(
        device_id="kasa-test",
        name="Test kasa",
        host=host,
        kind=kind,  # type: ignore[arg-type]
    )
    if mock:
        driver._mock = True  # type: ignore[attr-defined]

    info = await driver.get_info()
    print(f"  device_info: {info.id} / {info.name} / {info.driver_name}")
    print(f"  capabilities: {[c.value for c in info.capabilities]}")
    _print_state("initial", info.state)

    state = await driver.execute(DeviceAction(action="turn_on"))
    await asyncio.sleep(1)
    state = await driver.get_state()
    _print_state("after turn_on", state)
    assert state.power is True, f"expected power=True, got {state.power}"

    state = await driver.execute(DeviceAction(action="turn_off"))
    _print_state("after turn_off", state)
    assert state.power is False, f"expected power=False, got {state.power}"

    state = await driver.execute(DeviceAction(action="toggle"))
    _print_state("after toggle", state)
    assert state.power is True, f"expected power=True, got {state.power}"

    if kind == "bulb":
        state = await driver.execute(
            DeviceAction(action="set_brightness", params={"level": 50})
        )
        _print_state("after set_brightness=50", state)
        # Note: the underlying device may not have actually accepted the
        # brightness if it's a non-dimmable bulb — we just verify the call
        # path doesn't crash.

    # unknown verb should raise
    try:
        await driver.execute(DeviceAction(action="explode"))
    except ValueError:
        print("  unknown verb correctly rejected")
    else:
        print("  ERROR: unknown verb was not rejected")
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
        "--host",
        default=os.environ.get("KASA_HOST", "192.168.1.42"),
        help="Kasa device IP/hostname (or env KASA_HOST)",
    )
    p.add_argument(
        "--kind",
        choices=("plug", "bulb"),
        default=os.environ.get("KASA_KIND", "plug"),
        help='"plug" or "bulb" (default: plug, or env KASA_KIND)',
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help="Force software-only mode (no Kasa device required)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(main(args.host, args.kind, args.mock)))
