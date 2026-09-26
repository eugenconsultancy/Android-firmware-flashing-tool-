"""Tests for payload analysis (Phase 2)."""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path

from android_flasher.firmware.metadata import FirmwareMetadata
from android_flasher.firmware.payload import PAYLOAD_MAGIC, PayloadAnalyzer


def _make_payload_zip(path: Path, payload: bytes) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("payload.bin", payload)
        zf.writestr("metadata", "ota-type=AB\n")
    return path


def test_payload_present(tmp_path: Path) -> None:
    # ChromeOS payload header: "CrAU" + version u64 + manifest_size u64 + sig_size u32
    header = PAYLOAD_MAGIC + struct.pack(">QQ", 2, 1024) + struct.pack(">I", 0)
    payload = header + b"\x00" * 100
    path = _make_payload_zip(tmp_path / "ota.zip", payload)
    metadata = FirmwareMetadata(source_path=str(path))
    info = PayloadAnalyzer().analyze_zip(path, metadata)
    assert info.present is True
    assert info.version == 2
    assert info.manifest_size == 1024


def test_payload_missing(tmp_path: Path) -> None:
    path = tmp_path / "no_payload.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("metadata", "ota-type=AB\n")
    metadata = FirmwareMetadata(source_path=str(path))
    info = PayloadAnalyzer().analyze_zip(path, metadata)
    assert info.present is False
    assert any("payload.bin" in w for w in metadata.warnings)


def test_payload_bad_magic(tmp_path: Path) -> None:
    path = _make_payload_zip(tmp_path / "ota.zip", b"XXXX" + b"\x00" * 100)
    metadata = FirmwareMetadata(source_path=str(path))
    info = PayloadAnalyzer().analyze_zip(path, metadata)
    assert info.present is True
    assert any("magic" in note for note in info.notes)
