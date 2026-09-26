"""Tests for FirmwareMetadata (Phase 2)."""

from __future__ import annotations

from android_flasher.firmware.metadata import (
    FirmwareImageEntry,
    FirmwareMetadata,
    FirmwarePartitionEntry,
    ImageType,
)


def test_metadata_defaults() -> None:
    metadata = FirmwareMetadata()
    assert metadata.images == []
    assert metadata.partitions == []
    assert metadata.warnings == []
    assert metadata.errors == []
    assert metadata.has_errors() is False


def test_metadata_add_warning_deduplicates() -> None:
    metadata = FirmwareMetadata()
    metadata.add_warning("same")
    metadata.add_warning("same")
    assert metadata.warnings == ["same"]


def test_metadata_add_error() -> None:
    metadata = FirmwareMetadata()
    metadata.add_error("boom")
    assert metadata.has_errors() is True
    assert "boom" in metadata.errors


def test_metadata_to_dict_serializable() -> None:
    import json
    metadata = FirmwareMetadata(source_name="x.zip")
    metadata.images.append(FirmwareImageEntry(name="boot.img", image_type=ImageType.BOOT))
    metadata.partitions.append(FirmwarePartitionEntry(name="boot"))
    payload = metadata.to_dict()
    json.dumps(payload)  # must not raise


def test_image_types_list_includes_expected() -> None:
    assert ImageType.BOOT in ImageType.ALL
    assert ImageType.SUPER in ImageType.ALL
    assert ImageType.VBMETA in ImageType.ALL
