"""Normalized device identity and capability model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from android_flasher.config.settings import Settings
from android_flasher.devices.adb import AdbClient
from android_flasher.devices.bootloader import BootloaderInfo, detect_bootloader
from android_flasher.devices.detection import DetectionResult, DeviceState
from android_flasher.devices.fastboot import FastbootClient
from android_flasher.devices.properties import AndroidProperties, collect_properties
from android_flasher.devices.slots import SlotInfo, detect_slots, detect_slots_from_adb
from android_flasher.logging.logger import get_logger
from android_flasher.platform_tools.manager import PlatformToolManager

log = get_logger(__name__)


@dataclass
class DeviceCapabilities:
    """Capabilities detected (or unknown) for a device.

    A value of ``None`` means "not determined".
    """

    supports_adb: Optional[bool] = None
    supports_fastboot: Optional[bool] = None
    supports_fastbootd: Optional[bool] = None
    supports_getvar: Optional[bool] = None
    supports_slot_management: Optional[bool] = None
    supports_ab: Optional[bool] = None
    supports_dynamic_partitions: Optional[bool] = None
    supports_update: Optional[bool] = None
    supports_flash: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "supports_adb": self.supports_adb,
            "supports_fastboot": self.supports_fastboot,
            "supports_fastbootd": self.supports_fastbootd,
            "supports_getvar": self.supports_getvar,
            "supports_slot_management": self.supports_slot_management,
            "supports_ab": self.supports_ab,
            "supports_dynamic_partitions": self.supports_dynamic_partitions,
            "supports_update": self.supports_update,
            "supports_flash": self.supports_flash,
        }


@dataclass
class DeviceIdentity:
    """Normalized device information for the application."""

    transport: Optional[str] = None
    state: DeviceState = DeviceState.NO_DEVICE
    serial: Optional[str] = None

    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    device_codename: Optional[str] = None
    product: Optional[str] = None
    variant: Optional[str] = None

    android_version: Optional[str] = None
    sdk_version: Optional[str] = None
    build_id: Optional[str] = None
    fingerprint: Optional[str] = None

    bootloader_version: Optional[str] = None
    bootloader_state: Optional[str] = None

    slot_support: Optional[bool] = None
    current_slot: Optional[str] = None
    slot_count: Optional[int] = None

    fastboot_version: Optional[str] = None

    capabilities: DeviceCapabilities = field(default_factory=DeviceCapabilities)
    properties: Optional[AndroidProperties] = None
    slots: Optional[SlotInfo] = None
    bootloader: Optional[BootloaderInfo] = None
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "transport": self.transport,
            "state": self.state.value,
            "serial": self.serial,
            "manufacturer": self.manufacturer,
            "brand": self.brand,
            "model": self.model,
            "device_codename": self.device_codename,
            "product": self.product,
            "variant": self.variant,
            "android_version": self.android_version,
            "sdk_version": self.sdk_version,
            "build_id": self.build_id,
            "fingerprint": self.fingerprint,
            "bootloader_version": self.bootloader_version,
            "bootloader_state": self.bootloader_state,
            "slot_support": self.slot_support,
            "current_slot": self.current_slot,
            "slot_count": self.slot_count,
            "fastboot_version": self.fastboot_version,
            "capabilities": self.capabilities.to_dict(),
            "message": self.message,
        }


class DeviceIdentifier:
    """Builds a full DeviceIdentity from a DetectionResult."""

    def __init__(self, settings: Settings, tool_manager: PlatformToolManager) -> None:
        self._settings = settings
        self._tools = tool_manager

    def identify(self, detection: DetectionResult) -> DeviceIdentity:
        """Identify the device described by a detection result."""
        identity = DeviceIdentity(state=detection.state, message=detection.message)

        primary = detection.primary
        if primary is None:
            identity.capabilities = DeviceCapabilities(
                supports_adb=False,
                supports_fastboot=False,
            )
            return identity

        identity.serial = primary.serial
        identity.transport = primary.transport

        if primary.transport == "adb":
            self._populate_from_adb(identity, primary.serial)
        elif primary.transport in ("fastboot", "fastbootd"):
            self._populate_from_fastboot(identity, primary.serial)

        self._derive_capabilities(identity, detection)
        self._populate_fastboot_version(identity)
        return identity

    # ------------------------------------------------------------------
    # ADB
    # ------------------------------------------------------------------

    def _populate_from_adb(self, identity: DeviceIdentity, serial: Optional[str]) -> None:
        adb_path = self._tools.adb_path()
        if adb_path is None:
            return
        client = AdbClient(adb_path, timeout=self._settings.timeouts.adb)

        props = collect_properties(client, serial=serial)
        identity.properties = props
        identity.manufacturer = props.manufacturer
        identity.brand = props.brand
        identity.model = props.model
        identity.device_codename = props.device
        identity.product = props.product
        identity.android_version = props.android_version
        identity.sdk_version = props.sdk_version
        identity.build_id = props.build_id
        identity.fingerprint = props.fingerprint

        slots = detect_slots_from_adb(props.slot_suffix)
        identity.slots = slots
        identity.slot_support = slots.slot_support
        identity.current_slot = slots.current_slot

        # Bootloader state from properties.
        if props.boot_locked is not None:
            identity.bootloader_state = "LOCKED" if props.boot_locked == "1" else "UNLOCKED"
        elif props.vbmeta_device_state:
            identity.bootloader_state = props.vbmeta_device_state.upper()

    # ------------------------------------------------------------------
    # Fastboot
    # ------------------------------------------------------------------

    def _populate_from_fastboot(self, identity: DeviceIdentity, serial: Optional[str]) -> None:
        fastboot_path = self._tools.fastboot_path()
        if fastboot_path is None:
            return
        client = FastbootClient(fastboot_path, timeout=self._settings.timeouts.fastboot)

        identity.product = client.getvar("product", serial=serial)
        identity.variant = client.getvar("variant", serial=serial)
        identity.device_codename = identity.product

        slots = detect_slots(client, serial=serial)
        identity.slots = slots
        identity.slot_support = slots.slot_support
        identity.current_slot = slots.current_slot
        identity.slot_count = slots.slot_count

        bootloader = detect_bootloader(client, serial=serial)
        identity.bootloader = bootloader
        identity.bootloader_version = bootloader.version
        identity.bootloader_state = bootloader.state.value

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def _derive_capabilities(
        self,
        identity: DeviceIdentity,
        detection: DetectionResult,
    ) -> None:
        caps = DeviceCapabilities()

        caps.supports_adb = bool(detection.adb_devices) or identity.transport == "adb"
        caps.supports_fastboot = (
            bool(detection.fastboot_devices) or identity.transport == "fastboot"
        )
        caps.supports_fastbootd = identity.transport == "fastbootd"

        if identity.transport in ("fastboot", "fastbootd"):
            caps.supports_getvar = True  # Fastboot transport responded.

        if identity.slot_support is not None:
            caps.supports_ab = identity.slot_support
            caps.supports_slot_management = identity.slot_support

        # Dynamic partitions: inferred from dynamic partition properties
        # if present; otherwise left as unknown.
        if identity.properties is not None:
            dynamic = identity.properties.raw.get("ro.boot.dynamic_partitions")
            if dynamic is not None:
                caps.supports_dynamic_partitions = dynamic.lower() in {"true", "1", "yes"}

        # Phase 1 never flashes; capability remains unknown unless detected.
        caps.supports_flash = None
        caps.supports_update = None

        identity.capabilities = caps

    def _populate_fastboot_version(self, identity: DeviceIdentity) -> None:
        tool = self._tools.report.get("fastboot") if self._tools.report else None
        if tool is not None and tool.version:
            identity.fastboot_version = tool.version
