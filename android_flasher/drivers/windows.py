"""Windows driver detection.

Best-effort detection using the presence of the platform tools
executables and generic USB device enumeration via the Windows
registry is out of scope here. Instead we report whether adb and
fastboot are visible, which is the practical signal users need.
"""

from __future__ import annotations

import shutil

from android_flasher.drivers.detector import DriverReport, DriverStatus


def detect_windows_drivers() -> DriverReport:
    report = DriverReport(platform="windows")
    adb = shutil.which("adb")
    fastboot = shutil.which("fastboot")

    report.adb_driver = (
        DriverStatus.PRESENT if adb else DriverStatus.UNKNOWN
    )
    report.fastboot_driver = (
        DriverStatus.PRESENT if fastboot else DriverStatus.UNKNOWN
    )

    if not adb:
        report.notes.append(
            "adb was not found on PATH. Install Android SDK Platform Tools "
            "and/or the OEM USB driver."
        )
    if not fastboot:
        report.notes.append(
            "fastboot was not found on PATH. Install Android SDK Platform Tools."
        )
    return report
