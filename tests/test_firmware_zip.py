"""Tests for ZIP inspection (Phase 2)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from android_flasher.firmware.zip_package import ZipPackageInspector


def _make_zip(path: Path, entries: dict) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return path


def test_inspect_factory_zip(tmp_path: Path) -> None:
    path = _make_zip(tmp_path / "factory.zip", {
        "flash-all.sh": "#!/bin/sh\n",
        "bootloader-panther-1.0.img": b"BL",
        "radio-panther-0000.img": b"R",
        "image-panther-build.zip": b"PK",
    })
    inspection = ZipPackageInspector().inspect(path)
    assert inspection.opened_ok is True
    assert inspection.has_flash_script is True
    assert inspection.has_bootloader is True
    assert inspection.has_radio is True
    assert any("bootloader-panther" in e for e in inspection.image_entries)


def test_inspect_ota_zip(tmp_path: Path) -> None:
    path = _make_zip(tmp_path / "ota.zip", {
        "payload.bin": b"CrAU" + b"\x00" * 100,
        "metadata": "ota-type=AB\n",
        "care_map.pb": b"",
    })
    inspection = ZipPackageInspector().inspect(path)
    assert inspection.opened_ok is True
    assert inspection.has_payload_bin is True
    assert inspection.has_metadata is True
    assert inspection.has_care_map is True


def test_inspect_missing_zip(tmp_path: Path) -> None:
    inspection = ZipPackageInspector().inspect(tmp_path / "missing.zip")
    assert inspection.opened_ok is False
    assert inspection.error is not None


def test_read_member(tmp_path: Path) -> None:
    path = _make_zip(tmp_path / "x.zip", {"metadata": "hello=world\n"})
    inspector = ZipPackageInspector()
    content = inspector.read_member(path, "metadata")
    assert content == b"hello=world\n"
    text = inspector.read_text_member(path, "metadata")
    assert text is not None and "hello=world" in text


def test_read_missing_member(tmp_path: Path) -> None:
    path = _make_zip(tmp_path / "x.zip", {"a": b"a"})
    inspector = ZipPackageInspector()
    assert inspector.read_member(path, "missing") is None
