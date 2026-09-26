"""Tests for Platform Tools discovery."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from android_flasher.config.settings import Settings
from android_flasher.platform_tools.locator import PlatformToolLocator
from android_flasher.platform_tools.manager import PlatformToolManager
from android_flasher.platform_tools.version import parse_revision, parse_version


def _touch_executable(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\necho stub\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o755)


def test_locator_finds_bundled_tool(tmp_path: Path) -> None:
    bundled = tmp_path / "platform-tools"
    adb_name = "adb.exe" if os.name == "nt" else "adb"
    _touch_executable(bundled / adb_name)

    locator = PlatformToolLocator(
        project_root=tmp_path,
        search_paths=["platform-tools"],
        executable_map={"adb": "adb"},
        allow_system_path=False,
        allow_bundled=True,
    )
    result = locator.locate("adb")
    assert result.available
    assert result.source == "bundled"
    assert result.path is not None


def test_locator_returns_not_found(tmp_path: Path) -> None:
    locator = PlatformToolLocator(
        project_root=tmp_path,
        search_paths=[],
        executable_map={"adb": "definitely_missing_tool_xyz"},
        allow_system_path=False,
        allow_bundled=False,
    )
    result = locator.locate("adb")
    assert not result.available
    assert result.source == "not_found"


def test_parse_version() -> None:
    assert parse_version("Android Debug Bridge version 1.0.41") == "1.0.41"
    assert parse_version("fastboot version 35.0.1-11528375") == "35.0.1"
    assert parse_version("no version here") is None


def test_parse_revision() -> None:
    assert parse_revision("Revision 8c1f2a3b") == "8c1f2a3b"
    assert parse_revision("no revision") is None


def test_manager_discovers_without_version_query(tmp_path: Path) -> None:
    settings = Settings()
    settings.platform_tools.allow_system_path = False
    settings.platform_tools.allow_bundled = True
    settings.platform_tools.search_paths = []

    manager = PlatformToolManager(settings=settings, project_root=tmp_path)
    report = manager.discover(query_versions=False)
    assert "adb" in report.tools
    assert "fastboot" in report.tools
    assert report.tools["adb"].available is False
