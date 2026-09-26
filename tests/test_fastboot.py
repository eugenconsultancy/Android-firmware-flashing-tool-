"""Fastboot client tests."""

from __future__ import annotations

from pathlib import Path

from android_flasher.devices.fastboot import FastbootClient


def test_fastboot_client_constructs() -> None:
    client = FastbootClient(Path("/tmp/fastboot"))
    assert client is not None


def test_fastboot_parse_devices_empty() -> None:
    client = FastbootClient(Path("/tmp/fastboot"))
    parsed = client._parse_devices("")  # type: ignore[attr-defined]
    assert parsed == []


def test_fastboot_parse_devices_single() -> None:
    client = FastbootClient(Path("/tmp/fastboot"))
    parsed = client._parse_devices("SER1\tfastboot\n")  # type: ignore[attr-defined]
    assert len(parsed) == 1
    assert parsed[0][0] == "SER1"
