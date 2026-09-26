"""Tests for FirmwareAnalyzer end-to-end (Phase 2)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from android_flasher.firmware.analyzer import AnalysisOptions, FirmwareAnalyzer
from android_flasher.firmware.detector import FirmwareType
from android_flasher.firmware.metadata import ImageType


def test_analyze_raw_boot_image(tmp_path: Path) -> None:
    path = tmp_path / "boot.img"
    path.write_bytes(b"ANDROID!" + b"\x00" * 4096)

    analyzer = FirmwareAnalyzer(options=AnalysisOptions(compute_hashes=True))
    package = analyzer.analyze(path)

    assert package.metadata.package_type == FirmwareType.RAW_IMAGE.value
    assert package.metadata.source_sha256 is not None
    assert any(img.image_type == ImageType.BOOT for img in package.metadata.images)


def test_analyze_sparse_image(tmp_path: Path) -> None:
    path = tmp_path / "system.img"
    path.write_bytes(b"\x3a\xff\x26\xed" + b"\x00" * 128)
    analyzer = FirmwareAnalyzer(options=AnalysisOptions(compute_hashes=False))
    package = analyzer.analyze(path)
    assert package.metadata.package_type == FirmwareType.SPARSE_IMAGE.value
    assert package.metadata.sparse_image_present is True


def test_analyze_factory_zip(tmp_path: Path) -> None:
    path = tmp_path / "factory.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("flash-all.sh", "#!/bin/sh\n")
        zf.writestr("bootloader-panther-1.0.img", b"BL")
        zf.writestr("image-panther-tq1a.zip", b"PK")

    analyzer = FirmwareAnalyzer(options=AnalysisOptions(compute_hashes=False))
    package = analyzer.analyze(path)
    assert package.metadata.package_type == FirmwareType.FACTORY_ZIP.value
    assert package.metadata.codename == "panther"


def test_analyze_ota_zip(tmp_path: Path) -> None:
    path = tmp_path / "ota.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("payload.bin", b"CrAU" + b"\x00" * 100)
        zf.writestr(
            "metadata",
            "ota-type=AB\n"
            "post-build=google/panther/panther:14/UQ1A/1234567:user/release-keys\n",
        )

    analyzer = FirmwareAnalyzer(options=AnalysisOptions(compute_hashes=False))
    package = analyzer.analyze(path)
    assert package.metadata.package_type == FirmwareType.OTA_ZIP.value
    assert package.metadata.codename == "panther"


def test_analyze_missing_file(tmp_path: Path) -> None:
    analyzer = FirmwareAnalyzer()
    package = analyzer.analyze(tmp_path / "missing.zip")
    assert package.metadata.has_errors() is True


def test_analyze_corrupt_zip(tmp_path: Path) -> None:
    path = tmp_path / "bad.zip"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 10)
    analyzer = FirmwareAnalyzer(options=AnalysisOptions(compute_hashes=False))
    package = analyzer.analyze(path)
    assert package.metadata.has_errors() is True
