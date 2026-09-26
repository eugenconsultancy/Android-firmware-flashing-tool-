"""Tests for device profile loading (Phase 2)."""

from __future__ import annotations

from pathlib import Path

import yaml

from android_flasher.config.device_profiles import (
    DeviceProfile,
    DeviceProfileRegistry,
)


def _write_profile(root: Path, subdir: str, name: str, payload: dict) -> Path:
    folder = root / subdir
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_empty_registry(tmp_path: Path) -> None:
    registry = DeviceProfileRegistry(tmp_path / "profiles")
    assert registry.load() == []


def test_load_single_profile(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    _write_profile(root, "google", "panther.yaml", {
        "manufacturer": "Google",
        "codename": "panther",
        "architecture": {"slots": "ab", "dynamic_partitions": True},
        "firmware": {"formats": ["factory_zip", "ota_zip"]},
    })
    registry = DeviceProfileRegistry(root)
    profiles = registry.load()
    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.codename == "panther"
    assert profile.slots == "ab"
    assert profile.dynamic_partitions is True
    assert "factory_zip" in profile.firmware_formats


def test_find_by_codename(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    _write_profile(root, "google", "panther.yaml", {"manufacturer": "Google", "codename": "panther"})
    _write_profile(root, "google", "cheetah.yaml", {"manufacturer": "Google", "codename": "cheetah"})
    registry = DeviceProfileRegistry(root)
    registry.load()
    assert registry.find_by_codename("panther") is not None
    assert registry.find_by_codename("missing") is None


def test_malformed_profile_is_ignored(tmp_path: Path) -> None:
    root = tmp_path / "profiles"
    folder = root / "broken"
    folder.mkdir(parents=True)
    (folder / "bad.yaml").write_text(":: invalid ::: yaml", encoding="utf-8")
    registry = DeviceProfileRegistry(root)
    profiles = registry.load()
    assert profiles == []
