"""macOS driver detection.

macOS does not require OEM drivers for adb/fastboot, but it may prompt
for permission to access the USB device. We report PATH availability.
"""

from __future__ import annotations

import shutil

from android_flasher.drivers.detector import DriverReport, DriverStatus


def detect_macos_drivers() -> DriverReport:
    report = DriverReport(platform="macos")
    adb = shutil.which("adb")
    fastboot = shutil.which("fastboot")

    report.adb_driver = DriverStatus.PRESENT if adb else DriverStatus.UNKNOWN
    report.fastboot_driver = DriverStatus.PRESENT if fastboot else DriverStatus.UNKNOWN

    if not adb:
        report.notes.append("adb was not found on PATH.")
    if not fastboot:
        report.notes.append("fastboot was not found on PATH.")
    report.notes.append(
        "macOS may request permission the first time a USB device is "
        "accessed by the terminal application."
    )
    return report
