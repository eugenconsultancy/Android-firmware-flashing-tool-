"""Android property retrieval and normalization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from android_flasher.devices.adb import AdbClient

# Properties used for identification. The list is intentionally small and
# documented so it can be extended without ambiguity.
IDENTITY_PROPERTIES: tuple[str, ...] = (
    "ro.product.manufacturer",
    "ro.product.brand",
    "ro.product.model",
    "ro.product.device",
    "ro.product.name",
    "ro.build.version.release",
    "ro.build.version.sdk",
    "ro.build.id",
    "ro.build.fingerprint",
    "ro.boot.slot_suffix",
    "ro.boot.verifiedbootstate",
    "ro.boot.flash.locked",
    "ro.boot.vbmeta.device_state",
    "ro.boot.hardware",
    "ro.board.platform",
)


@dataclass
class AndroidProperties:
    """Normalized Android property snapshot."""

    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    device: Optional[str] = None
    product: Optional[str] = None
    android_version: Optional[str] = None
    sdk_version: Optional[str] = None
    build_id: Optional[str] = None
    fingerprint: Optional[str] = None
    slot_suffix: Optional[str] = None
    verified_boot_state: Optional[str] = None
    boot_locked: Optional[str] = None
    vbmeta_device_state: Optional[str] = None
    hardware: Optional[str] = None
    board_platform: Optional[str] = None
    raw: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: dict[str, str]) -> "AndroidProperties":
        return cls(
            manufacturer=raw.get("ro.product.manufacturer"),
            brand=raw.get("ro.product.brand"),
            model=raw.get("ro.product.model"),
            device=raw.get("ro.product.device"),
            product=raw.get("ro.product.name"),
            android_version=raw.get("ro.build.version.release"),
            sdk_version=raw.get("ro.build.version.sdk"),
            build_id=raw.get("ro.build.id"),
            fingerprint=raw.get("ro.build.fingerprint"),
            slot_suffix=raw.get("ro.boot.slot_suffix"),
            verified_boot_state=raw.get("ro.boot.verifiedbootstate"),
            boot_locked=raw.get("ro.boot.flash.locked"),
            vbmeta_device_state=raw.get("ro.boot.vbmeta.device_state"),
            hardware=raw.get("ro.boot.hardware"),
            board_platform=raw.get("ro.board.platform"),
            raw=dict(raw),
        )

    def to_dict(self) -> dict:
        return {
            "manufacturer": self.manufacturer,
            "brand": self.brand,
            "model": self.model,
            "device": self.device,
            "product": self.product,
            "android_version": self.android_version,
            "sdk_version": self.sdk_version,
            "build_id": self.build_id,
            "fingerprint": self.fingerprint,
            "slot_suffix": self.slot_suffix,
            "verified_boot_state": self.verified_boot_state,
            "boot_locked": self.boot_locked,
            "vbmeta_device_state": self.vbmeta_device_state,
            "hardware": self.hardware,
            "board_platform": self.board_platform,
        }


def collect_properties(client: AdbClient, serial: Optional[str] = None) -> AndroidProperties:
    """Collect Android properties from a connected ADB device."""
    raw = client.get_all_props(serial=serial)
    if not raw:
        # Fall back to individual queries.
        raw = {}
        for prop in IDENTITY_PROPERTIES:
            value = client.getprop(prop, serial=serial)
            if value:
                raw[prop] = value
    return AndroidProperties.from_raw(raw)
