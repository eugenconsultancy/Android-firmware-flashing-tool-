"""Linux driver detection.

On Linux there is no driver concept in the Windows sense; the relevant
signal is whether udev rules permit access. We report whether adb and
fastboot are on PATH and whether the user is in a group that
typically has USB access.
"""

from __future__ import annotations

import grp
import os
import shutil

from android_flasher.drivers.detector import DriverReport, DriverStatus


def detect_linux_drivers() -> DriverReport:
    report = DriverReport(platform="linux")
    adb = shutil.which("adb")
    fastboot = shutil.which("fastboot")

    report.adb_driver = DriverStatus.PRESENT if adb else DriverStatus.UNKNOWN
    report.fastboot_driver = DriverStatus.PRESENT if fastboot else DriverStatus.UNKNOWN

    if not adb:
        report.notes.append("adb was not found on PATH.")
    if not fastboot:
        report.notes.append("fastboot was not found on PATH.")

    try:
        groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]
    except Exception:  # noqa: BLE001 - defensive
        groups = []

    if not any(g in ("plugdev", "adbusers", "android") for g in groups):
        report.notes.append(
            "User is not a member of plugdev / adbusers / android. "
            "USB access may require udev rules and group membership."
        )
    return report
