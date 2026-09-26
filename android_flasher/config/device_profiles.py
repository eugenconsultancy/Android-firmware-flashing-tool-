"""Device profile registry.

Profiles are YAML data files under ``profiles/``. They provide hints,
not authority: runtime detection always takes precedence where it is
available.

``DeviceProfile`` exposes convenience accessors (``slots``,
``dynamic_partitions``, ``logical_partitions``, ``firmware_formats``)
that delegate to the nested ``architecture`` / ``firmware`` mappings,
so both ``profile.architecture["slots"]`` and ``profile.slots`` work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

import yaml


@dataclass
class DeviceProfile:
    """A single device profile loaded from YAML."""

    manufacturer: str = ""
    family: str = ""
    codename: str = ""
    product: str = ""
    architecture: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    partitions: dict[str, Any] = field(default_factory=dict)
    firmware: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    source_path: Optional[Path] = None

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        source_path: Optional[Path] = None,
    ) -> "DeviceProfile":
        return cls(
            manufacturer=str(data.get("manufacturer", "") or ""),
            family=str(data.get("family", "") or ""),
            codename=str(data.get("codename", "") or ""),
            product=str(data.get("product", "") or ""),
            architecture=dict(data.get("architecture", {}) or {}),
            capabilities=dict(data.get("capabilities", {}) or {}),
            partitions=dict(data.get("partitions", {}) or {}),
            firmware=dict(data.get("firmware", {}) or {}),
            notes=list(data.get("notes", []) or []),
            source_path=source_path,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "manufacturer": self.manufacturer,
            "family": self.family,
            "codename": self.codename,
            "product": self.product,
            "architecture": dict(self.architecture),
            "capabilities": dict(self.capabilities),
            "partitions": dict(self.partitions),
            "firmware": dict(self.firmware),
            "notes": list(self.notes),
            "source_path": str(self.source_path) if self.source_path else None,
        }

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def slots(self) -> Optional[str]:
        """Slot architecture (``"none"``, ``"ab"``, etc.) or None."""
        return self.architecture.get("slots")

    @property
    def dynamic_partitions(self) -> Optional[bool]:
        value = self.architecture.get("dynamic_partitions")
        if value is None:
            return None
        return bool(value)

    @property
    def logical_partitions(self) -> Optional[bool]:
        value = self.architecture.get("logical_partitions")
        if value is None:
            return None
        return bool(value)

    @property
    def firmware_formats(self) -> list[str]:
        """List of firmware formats the device accepts.

        Reads ``firmware.formats`` from the YAML. Always returns a list
        (empty if not specified) so callers can safely iterate.
        """
        if not isinstance(self.firmware, dict):
            return []
        formats = self.firmware.get("formats")
        if not formats:
            return []
        if isinstance(formats, (list, tuple, set)):
            return [str(f) for f in formats]
        return [str(formats)]


class DeviceProfileRegistry:
    """Loads and queries device profiles from a root directory."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._profiles: dict[str, DeviceProfile] = {}

    def load(self) -> list[DeviceProfile]:
        from android_flasher.logging.logger import get_logger
        log = get_logger(__name__)

        self._profiles.clear()
        if not self._root.is_dir():
            log.warning("Device profile root does not exist: %s", self._root)
            return []

        loaded: list[DeviceProfile] = []
        for path in sorted(self._root.rglob("*.yaml")):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = yaml.safe_load(handle) or {}
                if not isinstance(data, dict):
                    log.warning("Skipping non-mapping profile: %s", path)
                    continue
                profile = DeviceProfile.from_dict(data, source_path=path)
                key = (profile.codename or profile.product or path.stem).lower()
                self._profiles[key] = profile
                loaded.append(profile)
            except yaml.YAMLError as exc:
                log.warning("Invalid YAML in %s: %s", path, exc)
            except OSError as exc:
                log.warning("Could not read %s: %s", path, exc)

        return loaded

    def get(self, key: str) -> Optional[DeviceProfile]:
        if not key:
            return None
        return self._profiles.get(key.lower())

    def all(self) -> list[DeviceProfile]:
        return list(self._profiles.values())

    def __len__(self) -> int:
        return len(self._profiles)

    def __iter__(self) -> Iterator[DeviceProfile]:
        return iter(self._profiles.values())

    def find_by_codename(self, codename: str) -> Optional[DeviceProfile]:
        return self.get(codename)

    def find_by_product(self, product: str) -> Optional[DeviceProfile]:
        target = (product or "").lower()
        for profile in self._profiles.values():
            if profile.product.lower() == target or profile.codename.lower() == target:
                return profile
        return None
