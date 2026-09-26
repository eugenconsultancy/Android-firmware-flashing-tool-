"""Locate adb and fastboot executables across platforms."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from android_flasher.utils.filesystem import executable_names, is_executable, which


@dataclass
class LocatedTool:
    """A discovered executable."""

    name: str
    path: Optional[Path]
    source: str  # "system_path" | "configured" | "bundled" | "not_found"

    @property
    def available(self) -> bool:
        return self.path is not None and is_executable(self.path)


class PlatformToolLocator:
    """Searches system PATH, configured directories, and bundled directories."""

    def __init__(
        self,
        project_root: Path,
        search_paths: Iterable[str],
        executable_map: dict[str, str],
        allow_system_path: bool = True,
        allow_bundled: bool = True,
    ) -> None:
        self._project_root = Path(project_root)
        self._search_paths = [Path(p) for p in search_paths]
        self._executable_map = dict(executable_map)
        self._allow_system_path = allow_system_path
        self._allow_bundled = allow_bundled

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def locate(self, name: str) -> LocatedTool:
        """Locate a single tool by logical name (``adb`` or ``fastboot``)."""
        base = self._executable_map.get(name, name)

        # 1. Bundled within the project.
        if self._allow_bundled:
            found = self._search_directories(
                base,
                self._bundled_directories(),
            )
            if found is not None:
                return LocatedTool(name=name, path=found, source="bundled")

        # 2. Configured search paths.
        found = self._search_directories(base, self._configured_directories())
        if found is not None:
            return LocatedTool(name=name, path=found, source="configured")

        # 3. System PATH.
        if self._allow_system_path:
            for candidate in executable_names(base):
                located = which(candidate)
                if located is not None and is_executable(located):
                    return LocatedTool(name=name, path=located, source="system_path")

        return LocatedTool(name=name, path=None, source="not_found")

    def locate_all(self) -> dict[str, LocatedTool]:
        """Locate every configured tool."""
        return {name: self.locate(name) for name in self._executable_map}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _bundled_directories(self) -> list[Path]:
        return [
            self._project_root / "platform-tools",
            self._project_root / "platform-tools" / "bin",
            self._project_root / "platform_tools",
        ]

    def _configured_directories(self) -> list[Path]:
        directories: list[Path] = []
        for raw in self._search_paths:
            if raw.is_absolute():
                directories.append(raw)
            else:
                directories.append(self._project_root / raw)
        return directories

    def _search_directories(
        self,
        base: str,
        directories: Iterable[Path],
    ) -> Optional[Path]:
        for directory in directories:
            if not directory.is_dir():
                continue
            for filename in executable_names(base):
                candidate = directory / filename
                if is_executable(candidate):
                    return candidate
        return None


def is_windows() -> bool:
    """Return True on Windows."""
    return os.name == "nt"
