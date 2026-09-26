"""Driver detection entry point.

Delegates to platform-specific helpers. Detection is best-effort and
is used only to improve diagnostics when a device is physically
connected but not visible to adb or fastboot.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum


class DriverStatus(str, Enum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class DriverReport:
    """Summary of driver availability for the current host."""

    platform: str
    adb_driver: DriverStatus = DriverStatus.UNKNOWN
    fastboot_driver: DriverStatus = DriverStatus.UNKNOWN
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "adb_driver": self.adb_driver.value,
            "fastboot_driver": self.fastboot_driver.value,
            "notes": list(self.notes),
        }


def detect_drivers() -> DriverReport:
    """Detect driver availability on the current platform."""
    platform = sys.platform
    if platform.startswith("win"):
        from android_flasher.drivers.windows import detect_windows_drivers
        return detect_windows_drivers()
    if platform.startswith("linux"):
        from android_flasher.drivers.linux import detect_linux_drivers
        return detect_linux_drivers()
    if platform.startswith("darwin"):
        from android_flasher.drivers.macos import detect_macos_drivers
        return detect_macos_drivers()
    return DriverReport(
        platform=platform,
        adb_driver=DriverStatus.NOT_APPLICABLE,
        fastboot_driver=DriverStatus.NOT_APPLICABLE,
        notes=["Unsupported platform for driver detection."],
    )
