"""Controlled subprocess execution.

Runs a ``CommandSpec`` as a subprocess with:

    - shell=False (always)
    - argument arrays (never shell strings)
    - timeouts
    - stdout/stderr capture
    - cancellation via ``cancel()``
    - structured logging

This module intentionally does not reuse ``utils.subprocess.run_command``
because the executor needs streaming and cancellation. It still enforces
the same safety properties (no shell, argument list).
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from android_flasher.core.command_builder import CommandSpec
from android_flasher.logging.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums and result model
# ---------------------------------------------------------------------------

class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExecutionResult:
    """Result of a single command execution."""

    status: ExecutionStatus
    returncode: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    argv: list[str] = field(default_factory=list)
    error: str = ""
    cancelled: bool = False
    timed_out: bool = False

    def ok(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "argv": list(self.argv),
            "error": self.error,
            "cancelled": self.cancelled,
            "timed_out": self.timed_out,
        }


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class CommandExecutor:
    """Executes ``CommandSpec`` objects with cancellation support."""

    def __init__(
        self,
        *,
        default_timeout: int = 900,
        output_limit: int = 65536,
        cancel_grace_seconds: int = 3,
    ) -> None:
        self._default_timeout = int(default_timeout)
        self._output_limit = int(output_limit)
        self._cancel_grace = int(cancel_grace_seconds)

        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._cancelled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        spec: CommandSpec,
        *,
        cwd: Optional[Path] = None,
        env: Optional[dict[str, str]] = None,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> ExecutionResult:
        """Execute a single command specification.

        ``on_output`` receives stdout lines as they are produced.
        """
        if not spec.argv:
            return ExecutionResult(
                status=ExecutionStatus.SKIPPED,
                argv=[],
                error="empty command",
            )

        timeout = spec.timeout_seconds or self._default_timeout

        self._cancelled = False
        start = time.monotonic()

        try:
            popen = subprocess.Popen(
                spec.argv,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
                env=env,
                text=True,
                bufsize=1,
            )
        except (OSError, ValueError) as exc:
            duration = time.monotonic() - start
            log.error("Cannot start command %s: %s", spec.argv, exc)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                argv=list(spec.argv),
                error=str(exc),
                duration_seconds=duration,
            )

        with self._lock:
            self._process = popen

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        def read_stream(stream, sink: list[str], is_stdout: bool) -> None:
            if stream is None:
                return
            try:
                for line in iter(stream.readline, ""):
                    sink.append(line)
                    if on_output and is_stdout:
                        try:
                            on_output(line.rstrip("\n"))
                        except Exception:  # noqa: BLE001 - defensive
                            log.exception("on_output callback failed")
                    if sum(len(c) for c in sink) > self._output_limit:
                        sink.append("\n[output truncated]\n")
                        break
            except Exception:  # noqa: BLE001 - defensive
                log.exception("stream read failed")
            finally:
                try:
                    stream.close()
                except Exception:  # noqa: BLE001 - defensive
                    pass

        t_out = threading.Thread(
            target=read_stream, args=(popen.stdout, stdout_chunks, True), daemon=True
        )
        t_err = threading.Thread(
            target=read_stream, args=(popen.stderr, stderr_chunks, False), daemon=True
        )
        t_out.start()
        t_err.start()

        timed_out = False
        cancelled = False
        returncode: Optional[int] = None

        while True:
            if self._cancelled:
                cancelled = True
                self._terminate(popen)
                break

            try:
                returncode = popen.wait(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if timeout > 0 and (time.monotonic() - start) > timeout:
                    timed_out = True
                    self._terminate(popen)
                    break
                continue

        # Give reader threads a moment to drain.
        t_out.join(timeout=2.0)
        t_err.join(timeout=2.0)

        with self._lock:
            self._process = None

        duration = time.monotonic() - start
        stdout_text = "".join(stdout_chunks)
        stderr_text = "".join(stderr_chunks)

        if cancelled:
            status = ExecutionStatus.CANCELLED
        elif timed_out:
            status = ExecutionStatus.TIMEOUT
        elif returncode == 0:
            status = ExecutionStatus.SUCCESS
        else:
            status = ExecutionStatus.FAILED

        result = ExecutionResult(
            status=status,
            returncode=returncode,
            stdout=stdout_text,
            stderr=stderr_text,
            duration_seconds=duration,
            argv=list(spec.argv),
            cancelled=cancelled,
            timed_out=timed_out,
            error=stderr_text.strip() if status != ExecutionStatus.SUCCESS else "",
        )

        log.info(
            "executed argv=%s status=%s rc=%s duration=%.2fs",
            spec.argv,
            status.value,
            returncode,
            duration,
        )
        return result

    def cancel(self) -> None:
        """Request cancellation of the currently running command."""
        self._cancelled = True
        with self._lock:
            process = self._process
        if process is not None:
            self._terminate(process)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _terminate(self, process: subprocess.Popen) -> None:
        try:
            process.terminate()
        except Exception:  # noqa: BLE001 - defensive
            pass
        try:
            process.wait(timeout=self._cancel_grace)
        except Exception:  # noqa: BLE001 - defensive
            try:
                process.kill()
            except Exception:  # noqa: BLE001 - defensive
                pass
