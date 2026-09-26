"""Device model tests."""

from __future__ import annotations

from android_flasher.devices.detection import DeviceState
from android_flasher.devices.identification import (
    DeviceCapabilities,
    DeviceIdentity,
)


def test_device_identity_constructs() -> None:
    identity = DeviceIdentity(
        state=DeviceState.FASTBOOT_DEVICE,
        transport="fastboot",
        serial="SER1",
    )
    assert identity.serial == "SER1"
    assert identity.to_dict()["serial"] == "SER1"


def test_device_capabilities_defaults() -> None:
    caps = DeviceCapabilities()
    assert hasattr(caps, "supports_ab")
    assert hasattr(caps, "supports_fastbootd")
    assert hasattr(caps, "supports_dynamic_partitions")


def test_device_identity_with_slot() -> None:
    identity = DeviceIdentity(
        state=DeviceState.FASTBOOT_DEVICE,
        transport="fastboot",
        serial="SER1",
        current_slot="a",
        slot_support=True,
    )
    assert identity.current_slot == "a"
    assert identity.slot_support is True
