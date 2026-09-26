"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from android_flasher.config.settings import Settings


def test_defaults_when_file_missing(tmp_path: Path) -> None:
    settings = Settings.load(tmp_path / "does_not_exist.yaml")
    assert settings.application.name == "Android Flasher"
    assert settings.safety.phase1_read_only is True
    assert settings.timeouts.adb > 0


def test_load_from_yaml(tmp_path: Path) -> None:
    config = {
        "application": {"name": "Test Flasher", "version": "1.2.3"},
        "timeouts": {"adb": 11, "fastboot": 22},
        "safety": {"allow_flash": False, "phase1_read_only": True},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    settings = Settings.load(path)
    assert settings.application.name == "Test Flasher"
    assert settings.timeouts.adb == 11
    assert settings.timeouts.fastboot == 22
    assert settings.safety.allow_flash is False


def test_unknown_keys_are_ignored(tmp_path: Path) -> None:
    config = {"application": {"name": "X", "unknown_key": "ignored"}}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")

    settings = Settings.load(path)
    assert settings.application.name == "X"


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(":: invalid ::: yaml :::", encoding="utf-8")
    with pytest.raises(ValueError):
        Settings.load(path)


def test_to_dict_is_serializable() -> None:
    settings = Settings()
    payload = settings.to_dict()
    assert isinstance(payload, dict)
    assert "application" in payload
    assert "safety" in payload
