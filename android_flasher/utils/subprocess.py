"""Low-level subprocess helper.

This module is used by read-only probes (version checks, device
detection). Destructive execution goes through
``android_flasher.core.command_executor.CommandExecutor`` so that
cancellation and streaming are available.

Both modules enforce the same safety property: shell=False, argument
lists only.

Naming note:
    ``RunResult`` is the canonical dataclass. ``CommandResult`` is
    provided as a backwards-compatible alias because earlier phase
    modules (``devices/adb.py``, ``devices/fastboot.py``) import the
    class under that name.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RunResult:
    """Structured result of a subprocess invocation."""

    returncode: Optional[int]
    stdout: str
    stderr: str
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict:
        return {
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
            "ok": self.ok,
        }


CommandResult = RunResult


def run_command(
    argv: list[str],
    *,
    timeout: int = 30,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> RunResult:
    """Run a command with shell=False and return a structured result."""
    if not argv:
        return RunResult(returncode=None, stdout="", stderr="", error="empty argv")

    try:
        completed = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            env=env,
        )
    except FileNotFoundError as exc:
        return RunResult(returncode=None, stdout="", stderr="", error=str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
        return RunResult(
            returncode=None,
            stdout=stdout,
            stderr=stderr,
            error="timeout",
        )
    except OSError as exc:
        return RunResult(returncode=None, stdout="", stderr="", error=str(exc))

    return RunResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def which(name: str) -> Optional[str]:
    """Return the path to an executable on PATH, or None."""
    return shutil.which(name)
