"""Partition manager: ties device and firmware partition models together."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from android_flasher.devices.fastboot import FastbootClient
from android_flasher.devices.identification import DeviceIdentity
from android_flasher.firmware.metadata import FirmwareMetadata
from android_flasher.logging.logger import get_logger
from android_flasher.partitions.discovery import PartitionDiscovery
from android_flasher.partitions.dynamic import DynamicPartitionModel
from android_flasher.partitions.logical import LogicalPartitionSet
from android_flasher.partitions.mapping import PartitionMap, PartitionRecord

log = get_logger(__name__)


@dataclass
class PartitionAnalysis:
    """Combined device + firmware partition analysis."""

    device: Optional[PartitionMap] = None
    firmware: Optional[PartitionMap] = None
    dynamic: Optional[DynamicPartitionModel] = None
    logical: Optional[LogicalPartitionSet] = None
    matched: list[str] = field(default_factory=list)
    firmware_only: list[str] = field(default_factory=list)
    device_only: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "device": self.device.to_dict() if self.device else None,
            "firmware": self.firmware.to_dict() if self.firmware else None,
            "dynamic": self.dynamic.to_dict() if self.dynamic else None,
            "logical": self.logical.to_dict() if self.logical else None,
            "matched": list(self.matched),
            "firmware_only": list(self.firmware_only),
            "device_only": list(self.device_only),
            "warnings": list(self.warnings),
        }


class PartitionManager:
    """Combines device and firmware partition models."""

    def __init__(self) -> None:
        self._discovery = PartitionDiscovery()

    def analyze(
        self,
        identity: Optional[DeviceIdentity],
        firmware: Optional[FirmwareMetadata],
        fastboot_client: Optional[FastbootClient] = None,
    ) -> PartitionAnalysis:
        analysis = PartitionAnalysis()

        if identity is not None:
            analysis.device = self._discovery.discover_from_device(identity, fastboot_client)

        if firmware is not None:
            analysis.firmware = self._discovery.discover_from_firmware(firmware)

        if analysis.firmware is not None:
            analysis.dynamic = DynamicPartitionModel.from_map(analysis.firmware)
            analysis.logical = LogicalPartitionSet.from_names(
                analysis.dynamic.logical_names,
                source=analysis.dynamic.source,
            )

        self._diff(analysis)
        return analysis

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _diff(analysis: PartitionAnalysis) -> None:
        if analysis.device is None or analysis.firmware is None:
            return

        device_names = set(analysis.device.names())
        firmware_names = set(analysis.firmware.names())

        analysis.matched = sorted(device_names & firmware_names)
        analysis.firmware_only = sorted(firmware_names - device_names)
        analysis.device_only = sorted(device_names - firmware_names)

        if analysis.firmware_only:
            analysis.warnings.append(
                "Firmware references partitions not present in the device model: "
                + ", ".join(analysis.firmware_only)
            )

        if analysis.device.has_dynamic and not analysis.firmware.has_dynamic:
            analysis.warnings.append(
                "Device uses dynamic partitions but the firmware does not declare any."
            )
