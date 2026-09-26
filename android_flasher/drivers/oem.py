"""OEM driver guidance.

This module contains *data*, not logic. It maps manufacturer names to
documentation hints. The flashing engine does not depend on
manufacturer-specific behaviour.
"""

from __future__ import annotations

from typing import Optional


_OEM_GUIDANCE: dict[str, str] = {
    "google": (
        "Install the Google USB Driver on Windows. On Linux, ensure udev "
        "rules grant access to 18d1:* devices."
    ),
    "samsung": (
        "Install the Samsung Android USB Driver on Windows. Samsung "
        "devices may expose a different fastboot transport."
    ),
    "xiaomi": (
        "Xiaomi devices often require an unlocked bootloader and the "
        "Mi USB Driver on Windows."
    ),
    "motorola": (
        "Install the Motorola USB Driver on Windows."
    ),
    "oneplus": (
        "OnePlus devices generally work with the Google USB Driver on "
        "Windows."
    ),
}


def guidance_for(manufacturer: Optional[str]) -> str:
    """Return OEM guidance for a manufacturer name, if known."""
    if not manufacturer:
        return ""
    return _OEM_GUIDANCE.get(manufacturer.strip().lower(), "")
