"""Tests for factory package analysis (Phase 2)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from android_flasher.firmware.factory_package import FactoryPackageAnalyzer
from android_flasher.firmware.metadata import FirmwareMetadata


def _make_factory_zip(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("flash-all.sh", "#!/bin/sh\n")
        zf.writestr("bootloader-panther-1.0.img", b"BL")
        zf.writestr("radio-panther-g5300-0000.img", b"R")
        zf.writestr("image-panther-tq1a.230205.001.zip", b"PK")
    return path


def test_factory_package_codename(tmp_path: Path) -> None:
    path = _make_factory_zip(tmp_path / "factory.zip")
    metadata = FirmwareMetadata(source_path=str(path))
    analyzer = FactoryPackageAnalyzer()
    info = analyzer.analyze(path, metadata)
    assert info.codename == "panther"
    assert info.bootloader_version == "1.0"
    assert info.radio_version is not None
    assert info.inner_image_zip is not None
    assert metadata.codename == "panther"


def test_factory_package_warns_without_script(tmp_path: Path) -> None:
    path = tmp_path / "factory.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("boot.img", b"ANDROID!")
    metadata = FirmwareMetadata(source_path=str(path))
    FactoryPackageAnalyzer().analyze(path, metadata)
    assert any("flash-all" in w for w in metadata.warnings)
