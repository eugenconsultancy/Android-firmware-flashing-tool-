"""Firmware detection and analysis tests."""

from __future__ import annotations

import zipfile
from pathlib import Path

from android_flasher.firmware.detector import (
    FirmwareDetector,
    FirmwareKind,
    FirmwareType,
)


def test_detect_missing_file(tmp_path: Path) -> None:
    detector = FirmwareDetector()
    result = detector.detect(tmp_path / "missing.img")
    assert result.kind == FirmwareKind.MISSING


def test_detect_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.img"
    path.write_bytes(b"")
    detector = FirmwareDetector()
    result = detector.detect(path)
    assert result.kind == FirmwareKind.UNREADABLE


def test_detect_sparse_image(tmp_path: Path) -> None:
    path = tmp_path / "sparse.img"
    path.write_bytes(b"\x3a\xff\x26\xed" + b"\x00" * 64)
    detector = FirmwareDetector()
    result = detector.detect(path)
    assert result.kind == FirmwareKind.RAW_IMAGE
    assert result.is_sparse is True


def test_detect_zip_factory(tmp_path: Path) -> None:
    path = tmp_path / "factory.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("flash-all.sh", "#!/bin/sh\n")
    detector = FirmwareDetector()
    result = detector.detect(path)
    assert result.kind == FirmwareKind.ZIP_ARCHIVE
    assert result.firmware_type in (
        FirmwareType.FACTORY_ZIP,
        FirmwareType.OTA_ZIP,
    )


def test_detect_zip_ota(tmp_path: Path) -> None:
    path = tmp_path / "ota.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("payload.bin", b"payload")
    detector = FirmwareDetector()
    result = detector.detect(path)
    assert result.has_payload_bin is True


def test_detect_corrupt_zip(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.zip"
    path.write_bytes(b"PK\x03\x04" + b"garbage")
    detector = FirmwareDetector()
    result = detector.detect(path)
    assert result.kind == FirmwareKind.UNREADABLE


def test_detect_raw_image(tmp_path: Path) -> None:
    path = tmp_path / "boot.img"
    path.write_bytes(b"ANDROID!" + b"\x00" * 128)
    detector = FirmwareDetector()
    result = detector.detect(path)
    assert result.kind == FirmwareKind.RAW_IMAGE
    assert result.is_sparse is False
