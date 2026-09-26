"""Parse version strings from adb and fastboot."""

from __future__ import annotations

import re
from typing import Optional

_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")
_REVISION_RE = re.compile(r"Revision\s+([0-9a-fA-F]+)", re.IGNORECASE)


def parse_version(output: str) -> Optional[str]:
    """Extract a semantic version (``X.Y.Z``) from tool output."""
    if not output:
        return None
    match = _VERSION_RE.search(output)
    return match.group(1) if match else None


def parse_revision(output: str) -> Optional[str]:
    """Extract a revision hash from tool output, if present."""
    if not output:
        return None
    match = _REVISION_RE.search(output)
    return match.group(1) if match else None
