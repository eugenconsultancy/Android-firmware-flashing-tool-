"""ADB client.

Encapsulates every adb invocation. The GUI never builds adb commands
directly. All subprocess calls use shell=False and argument lists.

The parsing helpers (``_parse_devices``, ``_parse_getprop``) are
exposed as methods so they can be tested without a physical device.

``AdbDevice`` supports both attribute access (``dev.serial``) and
index access (``dev[0]``) for backwards compatibility with earlier
phase tests. It also exposes three semantic properties used by
``DeviceDetector``:

    is_ready         — device is authorized and reachable
    is_unauthorized  — user has not accepted the USB debugging prompt
    is_offline       — adb reports the device as offline

Naming:
    ``devices()``       — canonical API.
    ``list_devices()``  — alias used by ``DeviceDetector``.
    Both return the same list.
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
class AdbDevice:
    """A single device as reported by ``adb devices``."""

    serial: str
    state: str = "device"
    product: Optional[str] = None
    model: Optional[str] = None
    device: Optional[str] = None
    transport_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Semantic state helpers
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        """True if the device is authorized and reachable."""
        return self.state == "device"

    @property
    def is_unauthorized(self) -> bool:
        """True if the user has not accepted the USB debugging prompt."""
        return self.state == "unauthorized"

    @property
    def is_offline(self) -> bool:
        """True if adb reports the device as offline."""
        return self.state == "offline"

    # ------------------------------------------------------------------
    # Serialization and tuple-like access
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "serial": self.serial,
            "state": self.state,
            "product": self.product,
            "model": self.model,
            "device": self.device,
            "transport_id": self.transport_id,
        }

    def __getitem__(self, index: int) -> str:
        fields = (self.serial, self.state)
        if index < 0 or index >= len(fields):
            raise IndexError(index)
        return fields[index]

    def __iter__(self) -> Iterator[str]:
        return iter((self.serial, self.state))

    def __len__(self) -> int:
        return 2


class AdbClient:
    """Thin wrapper around the adb executable."""

    def __init__(self, adb_path: Path, *, timeout: int = 30) -> None:
        self._adb_path = Path(adb_path)
        self._timeout = int(timeout)

    @property
    def path(self) -> Path:
        return self._adb_path

    def _run(self, args: list[str], *, timeout: Optional[int] = None) -> CommandResult:
        argv = [str(self._adb_path), *args]
        return run_command(
            argv,
            timeout=timeout if timeout is not None else self._timeout,
        )

    # ------------------------------------------------------------------
    # Device listing — canonical API plus alias
    # ------------------------------------------------------------------

    def devices(self) -> list[AdbDevice]:
        """Return the parsed output of ``adb devices -l``."""
        result = self._run(["devices", "-l"])
        return self._parse_devices(result.stdout or "")

    def list_devices(self) -> list[AdbDevice]:
        """Alias for ``devices()`` used by ``DeviceDetector``."""
        return self.devices()

    # ------------------------------------------------------------------
    # Property access
    # ------------------------------------------------------------------

    def getprop(self, key: str) -> Optional[str]:
        result = self._run(["shell", "getprop", key])
        if not result.ok:
            return None
        return clean_line(result.stdout or "") or None

    def get_all_props(self) -> dict[str, str]:
        result = self._run(["shell", "getprop"])
        if not result.ok:
            return {}
        return self._parse_getprop(result.stdout or "")

    def get_state(self) -> Optional[str]:
        result = self._run(["get-state"])
        if not result.ok:
            return None
        return clean_line(result.stdout or "") or None

    # ------------------------------------------------------------------
    # Reboot helpers
    # ------------------------------------------------------------------

    def reboot(self, target: Optional[str] = None) -> CommandResult:
        args = ["reboot"]
        if target:
            args.append(target)
        return self._run(args)

    def reboot_bootloader(self) -> CommandResult:
        return self.reboot("bootloader")

    def reboot_fastboot(self) -> CommandResult:
        return self.reboot("fastboot")

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_devices(output: str) -> list[AdbDevice]:
        devices: list[AdbDevice] = []
        if not output:
            return devices
        for raw_line in clean_output(output).split("\n"):
            line = clean_line(raw_line)
            if not line:
                continue
            if line.startswith("List of devices"):
                continue
            if line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            state = parts[1]
            attributes: dict[str, str] = {}
            for token in parts[2:]:
                if ":" in token:
                    key, _, value = token.partition(":")
                    attributes[key.strip()] = value.strip()
            devices.append(
                AdbDevice(
                    serial=serial,
                    state=state,
                    product=attributes.get("product"),
                    model=attributes.get("model"),
                    device=attributes.get("device"),
                    transport_id=attributes.get("transport_id"),
                )
            )
        return devices

    @staticmethod
    def _parse_getprop(output: str) -> dict[str, str]:
        props: dict[str, str] = {}
        if not output:
            return props
        for raw_line in clean_output(output).split("\n"):
            line = clean_line(raw_line)
            if not line or not line.startswith("[") or "]" not in line:
                continue
            key_part, _, rest = line.partition("]")
            key = key_part.lstrip("[").strip()
            value = rest.strip()
            if value.startswith(":") or value.startswith("="):
                value = value[1:].strip()
            props[key] = value
        return props
