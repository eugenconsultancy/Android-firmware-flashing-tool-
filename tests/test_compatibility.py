"""Compatibility engine tests."""

from __future__ import annotations

from android_flasher.devices.detection import DeviceState
from android_flasher.devices.identification import (
    DeviceCapabilities,
    DeviceIdentity,
)
from android_flasher.firmware.compatibility import (
    CompatibilityEngine,
    CompatibilityStatus,
)
from android_flasher.firmware.metadata import FirmwareMetadata


def _device(**overrides) -> DeviceIdentity:
    identity = DeviceIdentity(
        state=DeviceState.FASTBOOT_DEVICE,
        transport="fastboot",
        serial="SER1",
    )
    identity.capabilities = DeviceCapabilities()
    for k, v in overrides.items():
        setattr(identity, k, v)
    return identity


def test_compatibility_match() -> None:
    device = _device(device_codename="panther", product="panther")
    metadata = FirmwareMetadata(
        source_path="boot.img",
        codename="panther",
        product="panther",
    )
    engine = CompatibilityEngine()
    result = engine.compare(device, metadata)
    assert result.status in (
        CompatibilityStatus.CONFIRMED,
        CompatibilityStatus.LIKELY,
        CompatibilityStatus.UNKNOWN,
    )


def test_compatibility_mismatch() -> None:
    device = _device(device_codename="cheetah", product="cheetah")
    metadata = FirmwareMetadata(
        source_path="boot.img",
        codename="panther",
        product="panther",
    )
    engine = CompatibilityEngine()
    result = engine.compare(device, metadata)
    assert result.status in (
        CompatibilityStatus.MISMATCH,
        CompatibilityStatus.BLOCKED,
    )


def test_compatibility_unknown_when_no_metadata() -> None:
    device = _device(device_codename="cheetah", product="cheetah")
    metadata = FirmwareMetadata(source_path="unknown.img")
    engine = CompatibilityEngine()
    result = engine.compare(device, metadata)
    assert result.status in (
        CompatibilityStatus.UNKNOWN,
        CompatibilityStatus.LIKELY,
    )
