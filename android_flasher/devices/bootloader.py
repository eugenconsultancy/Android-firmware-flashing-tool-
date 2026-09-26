"""Bootloader state detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from android_flasher.devices.fastboot import FastbootClient


class BootloaderState(str, Enum):
    """Normalized bootloader lock state."""

    UNLOCKED = "UNLOCKED"
    LOCKED = "LOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass
class BootloaderInfo:
    """Bootloader information from fastboot."""

    state: BootloaderState = BootloaderState.UNKNOWN
    version: Optional[str] = None
    product: Optional[str] = None
    variant: Optional[str] = None
    secure: Optional[str] = None
    raw: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.raw is None:
            self.raw = {}

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "version": self.version,
            "product": self.product,
            "variant": self.variant,
            "secure": self.secure,
        }


def detect_bootloader(client: FastbootClient, serial: Optional[str] = None) -> BootloaderInfo:
    """Query bootloader-related variables via fastboot getvar."""
    info = BootloaderInfo()

    unlocked = client.getvar("unlocked", serial=serial)
    if unlocked is None:
        unlocked = client.getvar("device-unlocked", serial=serial)

    if unlocked is not None:
        info.raw["unlocked"] = unlocked
        info.state = _interpret_lock_state(unlocked)

    version = client.getvar("version-bootloader", serial=serial)
    if version:
        info.version = version.strip()
        info.raw["version-bootloader"] = version

    product = client.getvar("product", serial=serial)
    if product:
        info.product = product.strip()
        info.raw["product"] = product

    variant = client.getvar("variant", serial=serial)
    if variant:
        info.variant = variant.strip()
        info.raw["variant"] = variant

    secure = client.getvar("secure", serial=serial)
    if secure:
        info.secure = secure.strip()
        info.raw["secure"] = secure

    return info


def _interpret_lock_state(value: str) -> BootloaderState:
    normalized = value.strip().lower()
    if normalized in {"yes", "true", "1", "unlocked"}:
        return BootloaderState.UNLOCKED
    if normalized in {"no", "false", "0", "locked"}:
        return BootloaderState.LOCKED
    return BootloaderState.UNKNOWN
