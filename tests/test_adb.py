"""ADB client tests.

These tests avoid a physical device by only exercising argument
construction and parsing where possible.
"""

from __future__ import annotations

from pathlib import Path

from android_flasher.devices.adb import AdbClient


def test_adb_client_constructs() -> None:
    client = AdbClient(Path("/tmp/adb"))
    assert client is not None


def test_adb_parse_devices_empty() -> None:
    client = AdbClient(Path("/tmp/adb"))
    parsed = client._parse_devices("")  # type: ignore[attr-defined]
    assert parsed == []


def test_adb_parse_devices_single() -> None:
    client = AdbClient(Path("/tmp/adb"))
    parsed = client._parse_devices("SER1\tdevice\n")  # type: ignore[attr-defined]
    assert len(parsed) == 1
    assert parsed[0][0] == "SER1"
