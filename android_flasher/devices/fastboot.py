"""Fastboot client.

Encapsulates every fastboot invocation. The GUI never builds fastboot
commands directly. All subprocess calls use shell=False and argument
lists.

Parsing helpers (``_parse_devices``, ``_parse_getvar``) are exposed
as methods so they can be tested without a physical device.

``FastbootDevice`` exposes two semantic properties used by other
modules:

    is_ready       — device is reachable in any fastboot mode
    is_fastbootd   — device is specifically in fastbootd (userspace)

Naming:
    ``devices()``       — canonical API.
    ``list_devices()``  — alias used by ``DeviceDetector``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from android_flasher.logging.logger import get_logger
from android_flasher.utils.subprocess import CommandResult, run_command
from android_flasher.utils.validators import clean_line, clean_output


log = get_logger(__name__)


@dataclass
class FastbootDevice:
    """A single device as reported by ``fastboot devices``."""

    serial: str
    mode: str = "fastboot"

    # ------------------------------------------------------------------
    # Semantic state helpers
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        """True if the device is reachable in any fastboot mode."""
        return self.mode in ("fastboot", "fastbootd")

    @property
    def is_fastbootd(self) -> bool:
        """True if the device is specifically in fastbootd (userspace)."""
        return self.mode == "fastbootd"

    # ------------------------------------------------------------------
    # Serialization and tuple-like access
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {"serial": self.serial, "mode": self.mode}

    def __getitem__(self, index: int) -> str:
        fields = (self.serial, self.mode)
        if index < 0 or index >= len(fields):
            raise IndexError(index)
        return fields[index]

    def __iter__(self) -> Iterator[str]:
        return iter((self.serial, self.mode))

    def __len__(self) -> int:
        return 2


class FastbootClient:
    """Thin wrapper around the fastboot executable."""

    def __init__(self, fastboot_path: Path, *, timeout: int = 60) -> None:
        self._fastboot_path = Path(fastboot_path)
        self._timeout = int(timeout)

    @property
    def path(self) -> Path:
        return self._fastboot_path

    def _run(self, args: list[str], *, timeout: Optional[int] = None) -> CommandResult:
        argv = [str(self._fastboot_path), *args]
        return run_command(
            argv,
            timeout=timeout if timeout is not None else self._timeout,
        )

    # ------------------------------------------------------------------
    # Device listing — canonical API plus alias
    # ------------------------------------------------------------------

    def devices(self) -> list[FastbootDevice]:
        result = self._run(["devices"])
        return self._parse_devices(result.stdout or "")

    def list_devices(self) -> list[FastbootDevice]:
        """Alias for ``devices()`` used by ``DeviceDetector``."""
        return self.devices()

    # ------------------------------------------------------------------
    # getvar
    # ------------------------------------------------------------------

    def getvar(self, name: str) -> Optional[str]:
        result = self._run(["getvar", name])
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        parsed = self._parse_getvar(combined)
        return parsed.get(name)

    def getvar_all(self) -> dict[str, str]:
        result = self._run(["getvar", "all"])
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        return self._parse_getvar(combined)

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_devices(output: str) -> list[FastbootDevice]:
        devices: list[FastbootDevice] = []
        if not output:
            return devices
        for raw_line in clean_output(output).split("\n"):
            line = clean_line(raw_line)
            if not line:
                continue
            parts = line.split()
            if not parts:
                continue
            serial = parts[0]
            mode = parts[1] if len(parts) > 1 else "fastboot"
            devices.append(FastbootDevice(serial=serial, mode=mode))
        return devices

    @staticmethod
    def _parse_getvar(output: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        if not output:
            return parsed
        for raw_line in clean_output(output).split("\n"):
            line = clean_line(raw_line)
            if not line:
                continue
            if line.startswith("OKAY") or line.startswith("FAILED"):
                continue
            if line.lower().startswith("finished"):
                continue
            if line.startswith("(bootloader)"):
                line = line[len("(bootloader)"):].strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key:
                parsed[key] = value
        return parsed
