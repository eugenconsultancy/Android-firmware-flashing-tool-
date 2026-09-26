"""Tests for firmware detection (Phase 2)."""

from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

from android_flasher.firmware.detector import (
    FirmwareDetector,
    FirmwareKind,
    FirmwareType,
)


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_detect_missing_file(tmp_path: Path) -> None:
    result = FirmwareDetector().detect(tmp_path / "missing.img")
    assert result.kind == FirmwareKind.MISSING
    assert result.firmware_type == FirmwareType.UNKNOWN


def test_detect_empty_file(tmp_path: Path) -> None:
    path = _write(tmp_path / "empty.img", b"")
    result = FirmwareDetector().detect(path)
    assert result.kind == FirmwareKind.UNREADABLE


def test_detect_raw_image(tmp_path: Path) -> None:
    # Non-sparse, non-zip bytes.
    path = _write(tmp_path / "boot.img", b"ANDROID!" + b"\x00" * 2000)
    result = FirmwareDetector().detect(path)
    assert result.kind == FirmwareKind.RAW_IMAGE
    assert result.firmware_type == FirmwareType.RAW_IMAGE
    assert result.is_sparse is False


def test_detect_sparse_image(tmp_path: Path) -> None:
    header = b"\x3a\xff\x26\xed" + b"\x00" * 100
    path = _write(tmp_path / "system.img", header)
    result = FirmwareDetector().detect(path)
    assert result.kind == FirmwareKind.RAW_IMAGE
    assert result.firmware_type == FirmwareType.SPARSE_IMAGE
    assert result.is_sparse is True


def test_detect_zip_factory(tmp_path: Path) -> None:
    path = tmp_path / "factory.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("flash-all.sh", "#!/bin/sh\necho hi")
        zf.writestr("bootloader-panther-1.0.img", b"BL")
        zf.writestr("image-panther-build.zip", b"PK")
    result = FirmwareDetector().detect(path)
    assert result.kind == FirmwareKind.ZIP_ARCHIVE
    assert result.firmware_type == FirmwareType.FACTORY_ZIP
    assert result.is_zip is True
    assert result.has_factory_script is True


def test_detect_zip_ota(tmp_path: Path) -> None:
    path = tmp_path / "ota.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("payload.bin", b"CrAU" + b"\x00" * 100)
        zf.writestr("metadata", "ota-type=AB\n")
    result = FirmwareDetector().detect(path)
    assert result.kind == FirmwareKind.ZIP_ARCHIVE
    assert result.firmware_type == FirmwareType.OTA_ZIP
    assert result.has_payload_bin is True


def test_detect_corrupt_zip(tmp_path: Path) -> None:
    # Looks like a zip by magic but the central directory is invalid.
    path = _write(tmp_path / "bad.zip", b"PK\x03\x04" + b"\x00" * 10)
    result = FirmwareDetector().detect(path)
    assert result.kind == FirmwareKind.UNREADABLE
    assert "Corrupt ZIP" in result.message
