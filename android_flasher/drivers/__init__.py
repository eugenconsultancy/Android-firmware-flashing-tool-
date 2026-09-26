"""Driver detection subsystem.

Driver detection is informational. The application detects the
presence or absence of drivers and surfaces guidance; it never
installs drivers silently.
"""

from android_flasher.drivers.detector import DriverReport, DriverStatus, detect_drivers

__all__ = [
    "DriverReport",
    "DriverStatus",
    "detect_drivers",
]
