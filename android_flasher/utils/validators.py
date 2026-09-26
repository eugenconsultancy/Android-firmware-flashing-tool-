"""Small validation and text-cleaning helpers.

These are deliberately conservative and are used by the UI, the
planner, the device layer, and the safety layer to:

    - reject obviously malformed input before it reaches the engine
    - sanitize raw adb / fastboot output before it is parsed
    - normalize slot suffixes and coerce loose integers safely

Text-cleaning functions are deliberately separate from validation
predicates so callers can pick exactly what they need without coupling
parsing to validation.
"""

from __future__ import annotations

import re
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_SERIAL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_PARTITION_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_SLOT_VALUES = {"a", "b", "_a", "_b"}

# Matches ANSI escape sequences emitted by some terminals/tools.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# Matches an optional sign followed by digits.
_INT_RE = re.compile(r"^[+-]?\d+$")


# ---------------------------------------------------------------------------
# Validation predicates
# ---------------------------------------------------------------------------

def is_valid_serial(value: str) -> bool:
    """Return True if ``value`` is a plausible device serial."""
    if not value:
        return False
    return bool(_SERIAL_RE.match(value))


def is_valid_partition_name(value: str) -> bool:
    """Return True if ``value`` is a plausible partition name."""
    if not value:
        return False
    return bool(_PARTITION_RE.match(value))


def is_valid_slot(value: str) -> bool:
    """Return True if ``value`` is a recognized A/B slot suffix."""
    if not value:
        return False
    return value.lower() in _SLOT_VALUES


# ---------------------------------------------------------------------------
# Slot helpers
# ---------------------------------------------------------------------------

def normalize_slot_suffix(value: Optional[str]) -> str:
    """Return a canonical slot suffix of the form ``_a`` or ``_b``.

    Accepts any of ``"a"``, ``"b"``, ``"_a"``, ``"_b"`` (case
    insensitive) and returns the underscore-prefixed lowercase form.
    Returns an empty string for unknown, empty, or ``None`` input.
    Unknown values are never coerced into ``_a`` or ``_b``.
    """
    if not value:
        return ""
    if not isinstance(value, str):
        value = str(value)
    text = value.strip().lower()
    if not text:
        return ""
    if text in ("a", "_a"):
        return "_a"
    if text in ("b", "_b"):
        return "_b"
    return ""


def slot_suffix_letter(value: Optional[str]) -> str:
    """Return just ``"a"`` or ``"b"`` (no underscore). Empty if unknown."""
    normalized = normalize_slot_suffix(value)
    if not normalized:
        return ""
    return normalized[-1]


def other_slot_suffix(value: Optional[str]) -> str:
    """Return the opposite slot suffix (``_a`` -> ``_b``, ``_b`` -> ``_a``)."""
    normalized = normalize_slot_suffix(value)
    if normalized == "_a":
        return "_b"
    if normalized == "_b":
        return "_a"
    return ""


# ---------------------------------------------------------------------------
# Integer coercion
# ---------------------------------------------------------------------------

def safe_int(value: Any, default: int = 0) -> int:
    """Convert ``value`` to ``int`` without ever raising.

    Accepts int, float, bytes-like, and strings that contain a valid
    integer (with optional surrounding whitespace). Returns ``default``
    on any failure.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        try:
            return int(value)
        except (OverflowError, ValueError):
            return default
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - defensive
            return default
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        if _INT_RE.match(text):
            try:
                return int(text)
            except ValueError:
                return default
        # Try a leading integer inside a longer string (e.g. "0x1f").
        try:
            return int(text, 0)
        except ValueError:
            return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Coerce common truthy/falsey textual representations to bool."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - defensive
            return default
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "yes", "y", "on", "enabled"):
            return True
        if text in ("0", "false", "no", "n", "off", "disabled", ""):
            return False
    return default


# ---------------------------------------------------------------------------
# Text cleaning helpers (used by adb.py / fastboot.py parsers)
# ---------------------------------------------------------------------------

def clean_line(line: str) -> str:
    """Strip whitespace, carriage returns, and newline characters.

    Used by the adb and fastboot clients to sanitize each line of raw
    command output before it is parsed. Never raises; returns an empty
    string for ``None`` or non-string input.
    """
    if not line:
        return ""
    if not isinstance(line, str):
        line = str(line)
    return line.strip("\r\n \t")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from ``text``."""
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return _ANSI_ESCAPE_RE.sub("", text)


def clean_output(text: str) -> str:
    """Normalize multi-line command output.

    - Removes ANSI escape sequences.
    - Normalizes line endings to ``\\n``.
    - Strips trailing whitespace from each line.
    - Removes trailing blank lines.
    """
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = strip_ansi(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def non_empty_lines(text: str) -> list[str]:
    """Return the non-empty, cleaned lines of ``text``."""
    if not text:
        return []
    cleaned = clean_output(text)
    return [line for line in cleaned.split("\n") if line.strip()]


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "is_valid_serial",
    "is_valid_partition_name",
    "is_valid_slot",
    "normalize_slot_suffix",
    "slot_suffix_letter",
    "other_slot_suffix",
    "safe_int",
    "safe_bool",
    "clean_line",
    "strip_ansi",
    "clean_output",
    "non_empty_lines",
]
