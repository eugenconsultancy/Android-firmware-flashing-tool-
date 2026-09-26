"""Audit logging for command execution.

Records every subprocess command invoked through the application.
Never records secrets, credentials, or environment dumps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from android_flasher.utils.subprocess import CommandResult


class AuditRecorder:
    """Append-only JSON Lines audit log of executed commands."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        result: CommandResult,
        *,
        purpose: Optional[str] = None,
        device_serial: Optional[str] = None,
    ) -> None:
        """Record a command execution result."""
        entry: dict[str, Any] = {
            "purpose": purpose,
            "device_serial": device_serial,
            "argv": list(result.argv),
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "error": result.error,
        }
        try:
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            # Audit failures should not break the application.
            pass
