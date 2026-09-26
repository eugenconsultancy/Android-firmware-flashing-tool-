"""Device detection across ADB and Fastboot transports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from android_flasher.config.settings import Settings
from android_flasher.devices.adb import AdbClient, AdbDevice
from android_flasher.devices.fastboot import FastbootClient, FastbootDevice
from android_flasher.logging.logger import get_logger
from android_flasher.platform_tools.manager import PlatformToolManager

log = get_logger(__name__)


class DeviceState(str, Enum):
    """Normalized device state."""

    NO_DEVICE = "NO_DEVICE"
    ADB_DEVICE = "ADB_DEVICE"
    ADB_UNAUTHORIZED = "ADB_UNAUTHORIZED"
    ADB_OFFLINE = "ADB_OFFLINE"
    FASTBOOT_DEVICE = "FASTBOOT_DEVICE"
    FASTBOOTD_DEVICE = "FASTBOOTD_DEVICE"
    MULTIPLE_DEVICES = "MULTIPLE_DEVICES"
    UNKNOWN = "UNKNOWN"


@dataclass
class DetectedDevice:
    """A detected device with its transport information."""

    state: DeviceState
    serial: Optional[str] = None
    transport: Optional[str] = None  # "adb" | "fastboot" | "fastbootd"
    adb: Optional[AdbDevice] = None
    fastboot: Optional[FastbootDevice] = None
    message: str = ""

    @property
    def is_present(self) -> bool:
        return self.state not in (DeviceState.NO_DEVICE, DeviceState.UNKNOWN)


@dataclass
class DetectionResult:
    """Full detection result across all transports."""

    state: DeviceState
    primary: Optional[DetectedDevice] = None
    adb_devices: list[AdbDevice] = field(default_factory=list)
    fastboot_devices: list[FastbootDevice] = field(default_factory=list)
    message: str = ""

    @property
    def has_device(self) -> bool:
        return self.primary is not None and self.primary.is_present

    @property
    def has_multiple(self) -> bool:
        return self.state == DeviceState.MULTIPLE_DEVICES


class DeviceDetector:
    """Detects connected devices via ADB and Fastboot."""

    def __init__(
        self,
        settings: Settings,
        tool_manager: PlatformToolManager,
    ) -> None:
        self._settings = settings
        self._tools = tool_manager

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self) -> DetectionResult:
        """Run detection across ADB and Fastboot."""
        adb_devices: list[AdbDevice] = []
        fastboot_devices: list[FastbootDevice] = []

        adb_path = self._tools.adb_path()
        if adb_path is not None:
            client = AdbClient(adb_path, timeout=self._settings.timeouts.adb)
            adb_devices = client.list_devices()

        fastboot_path = self._tools.fastboot_path()
        if fastboot_path is not None:
            client = FastbootClient(fastboot_path, timeout=self._settings.timeouts.fastboot)
            fastboot_devices = client.list_devices()

        return self._classify(adb_devices, fastboot_devices)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(
        self,
        adb_devices: list[AdbDevice],
        fastboot_devices: list[FastbootDevice],
    ) -> DetectionResult:
        total = len(adb_devices) + len(fastboot_devices)

        if total == 0:
            return DetectionResult(
                state=DeviceState.NO_DEVICE,
                message="No device detected. Connect a device or reboot to bootloader.",
                adb_devices=adb_devices,
                fastboot_devices=fastboot_devices,
            )

        if total > 1:
            return DetectionResult(
                state=DeviceState.MULTIPLE_DEVICES,
                message=(
                    f"{total} devices detected. "
                    "Disconnect all but one device for accurate identification."
                ),
                adb_devices=adb_devices,
                fastboot_devices=fastboot_devices,
            )

        # Exactly one device.
        if adb_devices:
            device = adb_devices[0]
            primary = self._from_adb(device)
            return DetectionResult(
                state=primary.state,
                primary=primary,
                message=primary.message,
                adb_devices=adb_devices,
                fastboot_devices=fastboot_devices,
            )

        device = fastboot_devices[0]
        primary = self._from_fastboot(device)
        return DetectionResult(
            state=primary.state,
            primary=primary,
            message=primary.message,
            adb_devices=adb_devices,
            fastboot_devices=fastboot_devices,
        )

    @staticmethod
    def _from_adb(device: AdbDevice) -> DetectedDevice:
        if device.is_ready:
            return DetectedDevice(
                state=DeviceState.ADB_DEVICE,
                serial=device.serial,
                transport="adb",
                adb=device,
                message=f"ADB device ready: {device.serial}",
            )
        if device.is_unauthorized:
            return DetectedDevice(
                state=DeviceState.ADB_UNAUTHORIZED,
                serial=device.serial,
                transport="adb",
                adb=device,
                message="Device is unauthorized. Accept the USB debugging prompt.",
            )
        if device.is_offline:
            return DetectedDevice(
                state=DeviceState.ADB_OFFLINE,
                serial=device.serial,
                transport="adb",
                adb=device,
                message="Device is offline. Try reconnecting or restarting adb.",
            )
        return DetectedDevice(
            state=DeviceState.UNKNOWN,
            serial=device.serial,
            transport="adb",
            adb=device,
            message=f"Device in unexpected ADB state: {device.state}",
        )

    @staticmethod
    def _from_fastboot(device: FastbootDevice) -> DetectedDevice:
        if device.mode == "fastbootd":
            return DetectedDevice(
                state=DeviceState.FASTBOOTD_DEVICE,
                serial=device.serial,
                transport="fastbootd",
                fastboot=device,
                message=f"FastbootD device ready: {device.serial}",
            )
        return DetectedDevice(
            state=DeviceState.FASTBOOT_DEVICE,
            serial=device.serial,
            transport="fastboot",
            fastboot=device,
            message=f"Fastboot device ready: {device.serial}",
        )
