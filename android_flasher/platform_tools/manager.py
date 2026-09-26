"""High-level Platform Tools manager.

Discovers adb/fastboot, queries their versions, and exposes a stable
interface for the rest of the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from android_flasher.config.settings import Settings
from android_flasher.logging.logger import get_logger
from android_flasher.platform_tools.locator import LocatedTool, PlatformToolLocator
from android_flasher.platform_tools.version import parse_revision, parse_version
from android_flasher.utils.subprocess import CommandResult, run_command

log = get_logger(__name__)


@dataclass
class ToolInfo:
    """Information about a discovered platform tool."""

    name: str
    path: Optional[Path]
    source: str
    available: bool
    version: Optional[str] = None
    revision: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": str(self.path) if self.path else None,
            "source": self.source,
            "available": self.available,
            "version": self.version,
            "revision": self.revision,
            "error": self.error,
        }


@dataclass
class PlatformToolReport:
    """Aggregate report of all platform tools."""

    tools: dict[str, ToolInfo] = field(default_factory=dict)

    @property
    def all_available(self) -> bool:
        return all(tool.available for tool in self.tools.values()) if self.tools else False

    @property
    def any_available(self) -> bool:
        return any(tool.available for tool in self.tools.values())

    def get(self, name: str) -> Optional[ToolInfo]:
        return self.tools.get(name)

    def to_dict(self) -> dict:
        return {name: tool.to_dict() for name, tool in self.tools.items()}


class PlatformToolManager:
    """Discovers and manages adb/fastboot."""

    def __init__(self, settings: Settings, project_root: Path) -> None:
        self._settings = settings
        self._project_root = Path(project_root)
        self._locator = PlatformToolLocator(
            project_root=self._project_root,
            search_paths=settings.platform_tools.search_paths,
            executable_map=settings.platform_tools.executable_names,
            allow_system_path=settings.platform_tools.allow_system_path,
            allow_bundled=settings.platform_tools.allow_bundled,
        )
        self._report: Optional[PlatformToolReport] = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self, query_versions: bool = True) -> PlatformToolReport:
        """Locate tools and optionally query their versions."""
        located = self._locator.locate_all()
        report = PlatformToolReport()

        for name, tool in located.items():
            info = ToolInfo(
                name=name,
                path=tool.path,
                source=tool.source,
                available=tool.available,
            )
            if tool.available and query_versions:
                self._populate_version(info)
            elif not tool.available:
                info.error = "Executable not found"
            report.tools[name] = info

        self._report = report
        return report

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def report(self) -> Optional[PlatformToolReport]:
        return self._report

    def adb_path(self) -> Optional[Path]:
        if self._report is None:
            self.discover()
        tool = self._report.tools.get("adb") if self._report else None
        return tool.path if tool and tool.available else None

    def fastboot_path(self) -> Optional[Path]:
        if self._report is None:
            self.discover()
        tool = self._report.tools.get("fastboot") if self._report else None
        return tool.path if tool and tool.available else None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _populate_version(self, info: ToolInfo) -> None:
        if info.path is None:
            return
        timeout = float(self._settings.timeouts.version_check)
        # Both adb and fastboot accept ``--version``.
        result: CommandResult = run_command(
            [str(info.path), "--version"],
            timeout=timeout,
        )
        if result.ok:
            combined = f"{result.stdout}\n{result.stderr}"
            info.version = parse_version(combined)
            info.revision = parse_revision(combined)
        else:
            info.error = result.error or f"Exit code {result.returncode}"
