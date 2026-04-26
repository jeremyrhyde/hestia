"""Standalone integration test for :class:`RelayDriver`.

Usage::

    uv run python tests/test_relay_driver.py            # live: drives real GPIO
    uv run python tests/test_relay_driver.py --mock     # software-only

Live mode expects a relay board connected to BCM pin 17 (override with
``--pin``). On the Pi you should hear an audible click when the relay
toggles.

Exits 0 on success and prints ``PASS``; exits 1 on failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow ``python tests/test_relay_driver.py`` from a fresh shell.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drivers.relay_driver import RelayDriver  # noqa: E402
from schemas import DeviceAction  # noqa: E402


def _print_state(label: str, state) -> None:
    print(f"  [{label}] {json.dumps(state.model_dump(), indent=2)}")


async def main(pin: int, mock: bool) -> int:
    print(f"--- RelayDriver test (mock={mock}, pin={pin}) ---")

    driver = RelayDriver(
        device_id="relay-test",
        name="Test relay",
        pin=pin,
        active_high=True,
    )
    if mock:
        # Even on a Pi, force software-only when --mock is requested.
        driver._mock = True  # type: ignore[attr-defined]

    info = await driver.get_info()
    print(f"  device_info: {info.id} / {info.name} / {info.driver_name}")
    print(f"  capabilities: {[c.value for c in info.capabilities]}")
    _print_state("initial", info.state)

    # turn on
    state = await driver.execute(DeviceAction(action="turn_on"))
    await asyncio.sleep(1)
    state = await driver.get_state()
    _print_state("after turn_on", state)
    assert state.power is True, f"expected power=True, got {state.power}"

    # turn off
    state = await driver.execute(DeviceAction(action="turn_off"))
    _print_state("after turn_off", state)
    assert state.power is False, f"expected power=False, got {state.power}"

    # toggle
    state = await driver.execute(DeviceAction(action="toggle"))
    _print_state("after toggle", state)
    assert state.power is True, f"expected power=True, got {state.power}"

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
    p.add_argument("--pin", type=int, default=17, help="BCM pin (default: 17)")
    p.add_argument(
        "--mock",
        action="store_true",
        help="Force software-only mode (no GPIO needed)",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(main(args.pin, args.mock)))
