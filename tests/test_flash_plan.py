"""Tests for the flash planner (Phase 3)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from android_flasher.config.settings import Settings
from android_flasher.core.flash_plan import (
    FlashOperationKind,
    FlashPlan,
    FlashPlanStatus,
    SlotStrategy,
)
from android_flasher.devices.detection import DeviceState
from android_flasher.devices.identification import (
    DeviceCapabilities,
    DeviceIdentity,
)
from android_flasher.firmware.compatibility import (
    CompatibilityEngine,
    CompatibilityStatus,
)
from android_flasher.firmware.detector import (
    FirmwareDetectionResult,
    FirmwareKind,
    FirmwareType,
)
from android_flasher.firmware.metadata import (
    FirmwareImageEntry,
    FirmwareMetadata,
    ImageType,
)
from android_flasher.firmware.package import FirmwarePackage
from android_flasher.safety.planner import FlashPlanner


def _device(**overrides) -> DeviceIdentity:
    identity = DeviceIdentity(
        state=DeviceState.FASTBOOT_DEVICE,
        transport="fastboot",
        serial="SER1",
    )
    identity.capabilities = DeviceCapabilities()
    for k, v in overrides.items():
        setattr(identity, k, v)
    return identity


def _make_raw_boot_package(tmp_path: Path) -> FirmwarePackage:
    """Build a synthetic raw boot.img package.

    The metadata declares codename and product so that the compatibility
    engine can perform a real identity comparison against a detected
    device. A raw image with no declared target cannot be verified as
    compatible with a specific device.
    """
    path = tmp_path / "boot.img"
    path.write_bytes(b"ANDROID!" + b"\x00" * 4096)
    detection = FirmwareDetectionResult(
        kind=FirmwareKind.RAW_IMAGE,
        firmware_type=FirmwareType.RAW_IMAGE,
        path=path,
        size_bytes=path.stat().st_size,
    )
    metadata = FirmwareMetadata(
        source_path=str(path),
        source_name="boot.img",
        source_size_bytes=path.stat().st_size,
        package_type=FirmwareType.RAW_IMAGE.value,
        format="raw_image",
        codename="panther",
        product="panther",
    )
    metadata.images.append(
        FirmwareImageEntry(
            name="boot.img",
            image_type=ImageType.BOOT,
            partition="boot",
        )
    )
    return FirmwarePackage(path=path, detection=detection, metadata=metadata)


def _make_factory_zip(tmp_path: Path) -> FirmwarePackage:
    path = tmp_path / "factory.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("flash-all.sh", "#!/bin/sh\n")
        zf.writestr("bootloader-panther-1.0.img", b"BL")
    detection = FirmwareDetectionResult(
        kind=FirmwareKind.ZIP_ARCHIVE,
        firmware_type=FirmwareType.FACTORY_ZIP,
        path=path,
        size_bytes=path.stat().st_size,
        is_zip=True,
        has_factory_script=True,
    )
    metadata = FirmwareMetadata(
        source_path=str(path),
        source_name="factory.zip",
        package_type=FirmwareType.FACTORY_ZIP.value,
        format="zip",
        codename="panther",
    )
    return FirmwarePackage(path=path, detection=detection, metadata=metadata)


def test_planner_blocks_without_device(tmp_path: Path) -> None:
    settings = Settings()
    planner = FlashPlanner(settings)
    plan = planner.plan(
        device=None,
        firmware=_make_raw_boot_package(tmp_path),
        compatibility=None,
        partition_analysis=None,
    )
    assert plan.status == FlashPlanStatus.BLOCKED
    assert any("device" in b.lower() for b in plan.blockers)


def test_planner_blocks_without_firmware() -> None:
    settings = Settings()
    planner = FlashPlanner(settings)
    plan = planner.plan(
        device=_device(),
        firmware=None,
        compatibility=None,
        partition_analysis=None,
    )
    assert plan.status == FlashPlanStatus.BLOCKED


def test_planner_blocks_without_compatibility(tmp_path: Path) -> None:
    settings = Settings()
    planner = FlashPlanner(settings)
    plan = planner.plan(
        device=_device(),
        firmware=_make_raw_boot_package(tmp_path),
        compatibility=None,
        partition_analysis=None,
    )
    assert plan.status == FlashPlanStatus.BLOCKED
    assert any("compatibility" in b.lower() for b in plan.blockers)


def test_planner_blocks_in_readonly_mode(tmp_path: Path) -> None:
    settings = Settings()
    planner = FlashPlanner(settings)
    device = _device(device_codename="panther", product="panther")
    package = _make_raw_boot_package(tmp_path)
    engine = CompatibilityEngine()
    compatibility = engine.compare(device, package.metadata)
    plan = planner.plan(
        device=device,
        firmware=package,
        compatibility=compatibility,
        partition_analysis=None,
    )
    assert plan.status == FlashPlanStatus.BLOCKED
    assert any("read-only" in b.lower() for b in plan.blockers)


def test_planner_raw_image_with_flash_enabled(tmp_path: Path) -> None:
    settings = Settings()
    settings.safety.phase1_read_only = False
    settings.safety.allow_flash = True
    planner = FlashPlanner(settings)
    device = _device(device_codename="panther", product="panther")
    package = _make_raw_boot_package(tmp_path)
    engine = CompatibilityEngine()
    compatibility = engine.compare(device, package.metadata)

    plan = planner.plan(
        device=device,
        firmware=package,
        compatibility=compatibility,
        partition_analysis=None,
    )
    assert plan.status in (FlashPlanStatus.READY, FlashPlanStatus.REQUIRES_CONFIRMATION)
    assert any(
        op.kind == FlashOperationKind.FLASH_IMAGE for op in plan.operations
    )


def test_planner_factory_zip_uses_update_when_extraction_disabled(tmp_path: Path) -> None:
    settings = Settings()
    settings.safety.phase1_read_only = False
    settings.safety.allow_flash = True
    settings.flash.allow_extraction_for_factory_zip = False
    settings.flash.allow_fastboot_update = True

    planner = FlashPlanner(settings)
    device = _device(device_codename="panther", product="panther")
    package = _make_factory_zip(tmp_path)
    engine = CompatibilityEngine()
    compatibility = engine.compare(device, package.metadata)

    plan = planner.plan(
        device=device,
        firmware=package,
        compatibility=compatibility,
        partition_analysis=None,
    )
    assert any(
        op.kind == FlashOperationKind.UPDATE_PACKAGE for op in plan.operations
    )


def test_planner_avb_disable_blocked_by_default(tmp_path: Path) -> None:
    settings = Settings()
    settings.safety.phase1_read_only = False
    settings.safety.allow_flash = True

    planner = FlashPlanner(settings)
    device = _device(device_codename="panther", product="panther")
    package = _make_raw_boot_package(tmp_path)
    package.metadata.images[0].image_type = ImageType.VBMETA
    package.metadata.images[0].partition = "vbmeta"
    engine = CompatibilityEngine()
    compatibility = engine.compare(device, package.metadata)
    plan = planner.plan(
        device=device,
        firmware=package,
        compatibility=compatibility,
        partition_analysis=None,
    )
    assert plan.status in (FlashPlanStatus.READY, FlashPlanStatus.REQUIRES_CONFIRMATION)


def test_planner_confirmation_standard_for_simple_flash(tmp_path: Path) -> None:
    settings = Settings()
    settings.safety.phase1_read_only = False
    settings.safety.allow_flash = True

    planner = FlashPlanner(settings)
    device = _device(device_codename="panther", product="panther")
    package = _make_raw_boot_package(tmp_path)
    engine = CompatibilityEngine()
    compatibility = engine.compare(device, package.metadata)
    plan = planner.plan(
        device=device,
        firmware=package,
        compatibility=compatibility,
        partition_analysis=None,
    )
    assert plan.confirmation_required in ("STANDARD", "ELEVATED")


def test_planner_blocked_on_compatibility_mismatch(tmp_path: Path) -> None:
    settings = Settings()
    settings.safety.phase1_read_only = False
    settings.safety.allow_flash = True

    planner = FlashPlanner(settings)
    device = _device(device_codename="cheetah", product="cheetah")
    package = _make_raw_boot_package(tmp_path)
    engine = CompatibilityEngine()
    compatibility = engine.compare(device, package.metadata)
    plan = planner.plan(
        device=device,
        firmware=package,
        compatibility=compatibility,
        partition_analysis=None,
    )
    assert plan.status == FlashPlanStatus.BLOCKED
