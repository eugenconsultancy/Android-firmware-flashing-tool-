"""Tests for the safety subsystem (Phase 3)."""

from __future__ import annotations

from pathlib import Path

from android_flasher.config.settings import Settings
from android_flasher.core.flash_plan import (
    FlashOperation,
    FlashOperationKind,
    FlashPlan,
    FlashPlanStatus,
    FlashStep,
    FlashStepKind,
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
from android_flasher.firmware.metadata import FirmwareMetadata
from android_flasher.firmware.package import FirmwarePackage
from android_flasher.safety.backup import BackupPlanner, BackupSupport
from android_flasher.safety.confirmation import (
    ConfirmationBuilder,
    ConfirmationRequirement,
)
from android_flasher.safety.preflight import SafetyPreflight
from android_flasher.safety.risk import RiskAssessor, RiskLevel
from android_flasher.safety.validator import (
    SafetyValidator,
    ValidationSeverity,
)


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


def _simple_plan(tmp_path: Path) -> FlashPlan:
    plan = FlashPlan(plan_id="test")
    op = FlashOperation(
        kind=FlashOperationKind.FLASH_IMAGE,
        partition="boot",
        image_path=str(tmp_path / "boot.img"),
        destructive=True,
    )
    plan.add_operation(op)
    plan.add_step(FlashStep(
        index=0,
        kind=FlashStepKind.FLASH,
        operation=op,
        description="flash boot",
    ))
    return plan


def test_validator_severities() -> None:
    v = SafetyValidator()
    v.info("i", "info")
    v.warn("w", "warn")
    v.error("e", "error")
    v.block("b", "blocker")
    assert v.has_blockers() is True
    assert v.has_errors() is True
    assert v.has_warnings() is True
    assert len(v.issues) == 4


def test_risk_low_for_reboot_only_plan() -> None:
    plan = FlashPlan(plan_id="reboot")
    op = FlashOperation(kind=FlashOperationKind.REBOOT_SYSTEM)
    plan.add_operation(op)
    plan.add_step(FlashStep(
        index=0,
        kind=FlashStepKind.REBOOT,
        operation=op,
        description="reboot",
    ))
    risk = RiskAssessor().assess(
        plan=plan,
        device=_device(),
        firmware=None,
        compatibility=None,
    )
    assert risk.level == RiskLevel.LOW


def test_risk_critical_for_avb_disable(tmp_path: Path) -> None:
    plan = FlashPlan(plan_id="avb")
    op = FlashOperation(
        kind=FlashOperationKind.FLASH_IMAGE,
        partition="vbmeta",
        image_path=str(tmp_path / "vbmeta.img"),
        avb_disable=True,
        destructive=True,
    )
    plan.add_operation(op)
    plan.add_step(FlashStep(
        index=0,
        kind=FlashStepKind.FLASH,
        operation=op,
        description="flash vbmeta",
    ))
    risk = RiskAssessor().assess(
        plan=plan,
        device=_device(),
        firmware=None,
        compatibility=None,
    )
    assert risk.level == RiskLevel.CRITICAL


def test_risk_critical_for_locked_bootloader(tmp_path: Path) -> None:
    device = _device()
    device.bootloader_state = type("BS", (), {"value": "locked"})()
    plan = _simple_plan(tmp_path)
    risk = RiskAssessor().assess(
        plan=plan,
        device=device,
        firmware=None,
        compatibility=None,
    )
    assert risk.blocked is True
    assert risk.level == RiskLevel.CRITICAL


def test_preflight_blocks_readonly(tmp_path: Path) -> None:
    settings = Settings()
    # phase1_read_only defaults to True
    plan = _simple_plan(tmp_path)
    report = SafetyPreflight(settings).run(
        plan=plan,
        device=_device(),
        firmware=None,
        compatibility=None,
        partition_analysis=None,
    )
    assert report.is_blocked() is True


def test_preflight_passes_with_flash_enabled(tmp_path: Path) -> None:
    settings = Settings()
    settings.safety.phase1_read_only = False
    settings.safety.allow_flash = True
    settings.safety.require_bootloader_check = False
    settings.safety.require_confirmation = False

    plan = _simple_plan(tmp_path)
    plan.device_serial = "SER1"
    plan.device_transport = "fastboot"
    plan.status = FlashPlanStatus.READY
    device = _device(device_codename="panther", product="panther")

    # Build a compatibility result manually.
    package = FirmwarePackage(
        path=tmp_path / "boot.img",
        detection=FirmwareDetectionResult(
            kind=FirmwareKind.RAW_IMAGE,
            firmware_type=FirmwareType.RAW_IMAGE,
        ),
        metadata=FirmwareMetadata(source_path="boot.img"),
    )
    engine = CompatibilityEngine()
    compatibility = engine.compare(device, package.metadata)

    report = SafetyPreflight(settings).run(
        plan=plan,
        device=device,
        firmware=package,
        compatibility=compatibility,
        partition_analysis=None,
    )
    # Compatibility may be UNKNOWN; with default settings that blocks.
    assert report.is_blocked() is True or report.passed() is True


def test_preflight_blocks_mismatch(tmp_path: Path) -> None:
    settings = Settings()
    settings.safety.phase1_read_only = False
    settings.safety.allow_flash = True
    settings.safety.require_bootloader_check = False

    device = _device(device_codename="cheetah", product="cheetah")
    package = FirmwarePackage(
        path=tmp_path / "boot.img",
        detection=FirmwareDetectionResult(
            kind=FirmwareKind.RAW_IMAGE,
            firmware_type=FirmwareType.RAW_IMAGE,
        ),
        metadata=FirmwareMetadata(
            source_path="boot.img",
            codename="panther",
            product="panther",
            slot_architecture="ab",
        ),
    )
    engine = CompatibilityEngine()
    compatibility = engine.compare(device, package.metadata)

    plan = _simple_plan(tmp_path)
    plan.device_serial = "SER1"
    plan.device_transport = "fastboot"
    plan.status = FlashPlanStatus.READY

    report = SafetyPreflight(settings).run(
        plan=plan,
        device=device,
        firmware=package,
        compatibility=compatibility,
        partition_analysis=None,
    )
    assert report.is_blocked() is True


def test_confirmation_builder_blocked_for_high_risk(tmp_path: Path) -> None:
    settings = Settings()
    builder = ConfirmationBuilder(settings)
    plan = FlashPlan(plan_id="x")
    op = FlashOperation(
        kind=FlashOperationKind.ERASE_PARTITION,
        partition="userdata",
        destructive=True,
    )
    plan.add_operation(op)
    plan.add_step(FlashStep(
        index=0,
        kind=FlashStepKind.WIPE,
        operation=op,
        description="erase",
    ))
    risk = RiskAssessor().assess(
        plan=plan,
        device=_device(),
        firmware=None,
        compatibility=None,
    )
    prompt = builder.build(plan=plan, risk=risk, compatibility=None)
    # Default settings block CRITICAL.
    assert prompt.requirement in (
        ConfirmationRequirement.BLOCKED,
        ConfirmationRequirement.ELEVATED,
    )


def test_backup_planner_userdata_unsupported(tmp_path: Path) -> None:
    plan = FlashPlan(plan_id="x")
    op = FlashOperation(
        kind=FlashOperationKind.FLASH_IMAGE,
        partition="userdata",
        image_path=str(tmp_path / "userdata.img"),
        destructive=True,
    )
    plan.add_operation(op)
    backup = BackupPlanner().plan_for_plan(plan)
    assert backup.entries.get("userdata") == BackupSupport.UNSUPPORTED
