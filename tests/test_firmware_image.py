"""Tests for raw image inspection (Phase 2)."""

from __future__ import annotations

from pathlib import Path

from android_flasher.firmware.image import (
    classify_image_name,
    inspect_image_bytes,
    inspect_raw_image,
)
from android_flasher.firmware.metadata import ImageType


def test_classify_image_name_basic() -> None:
    image_type, partition, slot = classify_image_name("boot.img")
    assert image_type == ImageType.BOOT
    assert partition == "boot"
    assert slot is None


def test_classify_image_name_slot() -> None:
    image_type, partition, slot = classify_image_name("boot_a.img")
    assert image_type == ImageType.BOOT
    assert slot == "_a"


def test_classify_image_name_unknown() -> None:
    image_type, _, _ = classify_image_name("mystery.img")
    assert image_type == ImageType.OTHER


def test_classify_super() -> None:
    image_type, partition, _ = classify_image_name("super.img")
    assert image_type == ImageType.SUPER
    assert partition == "super"


def test_inspect_raw_image(tmp_path: Path) -> None:
    path = tmp_path / "boot.img"
    path.write_bytes(b"ANDROID!" + b"\x00" * 512)
    info = inspect_raw_image(path)
    assert info.image_type == ImageType.BOOT
    assert info.detected_format == "android_boot"
    assert info.sparse is False


def test_inspect_sparse_image(tmp_path: Path) -> None:
    path = tmp_path / "system.img"
    path.write_bytes(b"\x3a\xff\x26\xed" + b"\x00" * 128)
    info = inspect_raw_image(path)
    assert info.detected_format == "sparse"
    assert info.sparse is True


def test_inspect_vbmeta() -> None:
    info = inspect_image_bytes("vbmeta.img", b"AVB0" + b"\x00" * 128)
    assert info.image_type == ImageType.VBMETA
    assert info.detected_format == "vbmeta"


def test_inspect_dtbo() -> None:
    info = inspect_image_bytes("dtbo.img", b"\xd7\xb7\xab\x1e" + b"\x00" * 128)
    assert info.image_type == ImageType.DTBO
    assert info.detected_format == "dtbo"
