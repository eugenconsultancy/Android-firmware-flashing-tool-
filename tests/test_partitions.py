"""Partition manager tests."""

from __future__ import annotations

from android_flasher.devices.detection import DeviceState
from android_flasher.devices.identification import (
    DeviceCapabilities,
    DeviceIdentity,
)
from android_flasher.firmware.metadata import (
    FirmwareImageEntry,
    FirmwareMetadata,
    ImageType,
)
from android_flasher.partitions.manager import PartitionManager


def _device() -> DeviceIdentity:
    identity = DeviceIdentity(
        state=DeviceState.FASTBOOT_DEVICE,
        transport="fastboot",
        serial="SER1",
    )
    identity.capabilities = DeviceCapabilities()
    return identity


def test_partition_analysis_constructs() -> None:
    manager = PartitionManager()
    analysis = manager.analyze(_device(), FirmwareMetadata(source_path="x"))
    assert analysis is not None


def test_partition_analysis_with_images() -> None:
    metadata = FirmwareMetadata(source_path="boot.img")
    metadata.images.append(
        FirmwareImageEntry(name="boot.img", image_type=ImageType.BOOT, partition="boot")
    )
    manager = PartitionManager()
    analysis = manager.analyze(_device(), metadata)
    assert analysis is not None
