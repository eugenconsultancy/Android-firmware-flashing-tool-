"""A/B slot detection and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from android_flasher.devices.fastboot import FastbootClient
from android_flasher.utils.validators import normalize_slot_suffix, safe_int


@dataclass
class SlotInfo:
    """Slot configuration discovered from a device."""

    slot_support: bool = False
    current_slot: Optional[str] = None
    slot_count: Optional[int] = None
    slot_suffix: Optional[str] = None
    slot_successful: Optional[str] = None
    slot_unbootable: Optional[str] = None
    slot_retry_count: Optional[str] = None
    source: str = "unknown"

    @property
    def other_slot(self) -> Optional[str]:
        current = self.current_slot
        if current == "_a":
            return "_b"
        if current == "_b":
            return "_a"
        return None

    def to_dict(self) -> dict:
        return {
            "slot_support": self.slot_support,
            "current_slot": self.current_slot,
            "slot_count": self.slot_count,
            "slot_suffix": self.slot_suffix,
            "slot_successful": self.slot_successful,
            "slot_unbootable": self.slot_unbootable,
            "slot_retry_count": self.slot_retry_count,
            "source": self.source,
        }


def detect_slots(client: FastbootClient, serial: Optional[str] = None) -> SlotInfo:
    """Query slot information via fastboot getvar."""
    info = SlotInfo()

    raw_slot = client.getvar("current-slot", serial=serial)
    if raw_slot:
        info.current_slot = normalize_slot_suffix(raw_slot)
        info.slot_support = info.current_slot in {"_a", "_b"}
        info.source = "fastboot"

    raw_count = client.getvar("slot-count", serial=serial)
    if raw_count:
        count = safe_int(raw_count, default=0)
        if count > 0:
            info.slot_count = count
            info.slot_support = count > 1

    raw_suffix = client.getvar("slot-suffixes", serial=serial)
    if raw_suffix:
        info.slot_suffix = raw_suffix.strip()

    raw_success = client.getvar("slot-successful", serial=serial)
    if raw_success:
        info.slot_successful = raw_success.strip()

    raw_unboot = client.getvar("slot-unbootable", serial=serial)
    if raw_unboot:
        info.slot_unbootable = raw_unboot.strip()

    raw_retry = client.getvar("slot-retry-count", serial=serial)
    if raw_retry:
        info.slot_retry_count = raw_retry.strip()

    return info


def detect_slots_from_adb(slot_suffix: Optional[str]) -> SlotInfo:
    """Build SlotInfo from an ADB-reported ``ro.boot.slot_suffix``."""
    info = SlotInfo(source="adb")
    if slot_suffix:
        normalized = normalize_slot_suffix(slot_suffix)
        info.current_slot = normalized
        info.slot_support = normalized in {"_a", "_b"}
    return info
