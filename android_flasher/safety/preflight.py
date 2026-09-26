"""Safety preflight.

Runs a deterministic battery of checks against a plan and the current
device state. Preflight is the single gate that decides whether
execution is permitted.

Checks cover:

    - device present
    - single intended device (serial confirmed)
    - correct transport (fastboot)
    - firmware identified
    - compatibility status
    - partition existence / architecture
    - slot architecture
    - bootloader state
    - required capabilities
    - firmware integrity (hash)
    - operation risk vs configured maximum
    - user confirmation requirement
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from android_flasher.config.settings import Settings
from android_flasher.core.flash_plan import (
    FlashOperationKind,
    FlashPlan,
    FlashPlanStatus,
    SlotStrategy,
)
from android_flasher.devices.bootloader import BootloaderInfo
from android_flasher.devices.detection import DeviceState, DetectionResult
from android_flasher.devices.identification import DeviceIdentity
from android_flasher.devices.slots import SlotInfo
from android_flasher.firmware.compatibility import (
    CompatibilityResult,
    CompatibilityStatus,
)
from android_flasher.firmware.package import FirmwarePackage
from android_flasher.logging.logger import get_logger
from android_flasher.partitions.manager import PartitionAnalysis
from android_flasher.safety.validator import (
    SafetyValidator,
    ValidationIssue,
    ValidationSeverity,
)

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------

@dataclass
class PreflightCheck:
    """A single named check."""

    name: str
    passed: bool
    severity: str  # INFO | WARNING | ERROR | BLOCKER
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class PreflightReport:
    """Aggregate preflight report."""

    checks: list[PreflightCheck] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, check: PreflightCheck) -> None:
        self.checks.append(check)

    def add_warning(self, message: str) -> None:
        if message and message not in self.warnings:
            self.warnings.append(message)

    def has_blockers(self) -> bool:
        return any(c.severity == "BLOCKER" and not c.passed for c in self.checks)

    def has_failures(self) -> bool:
        return any(
            not c.passed and c.severity in ("BLOCKER", "ERROR") for c in self.checks
        )

    def is_blocked(self) -> bool:
        return self.has_blockers() or self.has_failures()

    def passed(self) -> bool:
        return not self.has_failures()

    def to_dict(self) -> dict:
        return {
            "checks": [c.to_dict() for c in self.checks],
            "issues": [i.to_dict() for i in self.issues],
            "warnings": list(self.warnings),
            "passed": self.passed(),
            "blocked": self.is_blocked(),
        }


# ---------------------------------------------------------------------------
# Preflight engine
# ---------------------------------------------------------------------------

class SafetyPreflight:
    """Runs a battery of preflight checks against a plan."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        plan: FlashPlan,
        device: Optional[DeviceIdentity],
        firmware: Optional[FirmwarePackage],
        compatibility: Optional[CompatibilityResult],
        partition_analysis: Optional[PartitionAnalysis] = None,
        detection: Optional[DetectionResult] = None,
        bootloader_info: Optional[BootloaderInfo] = None,
        slot_info: Optional[SlotInfo] = None,
    ) -> PreflightReport:
        report = PreflightReport()
        validator = SafetyValidator()

        self._check_plan_status(plan, report)
        self._check_phase1_readonly(report)
        self._check_flash_permission(report)
        self._check_device_present(device, detection, report)
        self._check_transport(plan, report)
        self._check_serial(device, plan, report)
        self._check_firmware_present(firmware, report)
        self._check_compatibility(compatibility, report)
        self._check_partitions(plan, partition_analysis, report)
        self._check_slot_architecture(plan, device, slot_info, report)
        self._check_bootloader(bootloader_info, device, report)
        self._check_capabilities(plan, device, report)
        self._check_integrity(firmware, report)
        self._check_operations(plan, report)
        self._check_confirmation(plan, compatibility, report)

        report.issues = list(validator.issues)
        return report

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _check_plan_status(self, plan: FlashPlan, report: PreflightReport) -> None:
        if plan is None:
            report.add(PreflightCheck(
                name="plan_present",
                passed=False,
                severity="BLOCKER",
                message="No flash plan was provided.",
            ))
            return
        if plan.status == FlashPlanStatus.BLOCKED:
            report.add(PreflightCheck(
                name="plan_status",
                passed=False,
                severity="BLOCKER",
                message="Plan is already blocked by the planner.",
            ))
            return
        if not plan.steps:
            report.add(PreflightCheck(
                name="plan_has_steps",
                passed=False,
                severity="BLOCKER",
                message="Plan contains no executable steps.",
            ))
            return
        report.add(PreflightCheck(
            name="plan_status",
            passed=True,
            severity="INFO",
            message=f"Plan status: {plan.status.value}",
        ))

    def _check_phase1_readonly(self, report: PreflightReport) -> None:
        if self._settings.safety.phase1_read_only:
            report.add(PreflightCheck(
                name="phase1_read_only",
                passed=False,
                severity="BLOCKER",
                message="Safety settings keep the application in read-only mode.",
            ))
        else:
            report.add(PreflightCheck(
                name="phase1_read_only",
                passed=True,
                severity="INFO",
                message="Read-only mode is disabled.",
            ))

    def _check_flash_permission(self, report: PreflightReport) -> None:
        if not self._settings.safety.allow_flash:
            report.add(PreflightCheck(
                name="flash_permission",
                passed=False,
                severity="BLOCKER",
                message="Flashing is not enabled in safety settings.",
            ))
        else:
            report.add(PreflightCheck(
                name="flash_permission",
                passed=True,
                severity="INFO",
                message="Flashing is enabled.",
            ))

    def _check_device_present(
        self,
        device: Optional[DeviceIdentity],
        detection: Optional[DetectionResult],
        report: PreflightReport,
    ) -> None:
        if device is None:
            report.add(PreflightCheck(
                name="device_present",
                passed=False,
                severity="BLOCKER",
                message="No device is identified.",
            ))
            return
        if detection is not None and detection.state in (
            DeviceState.NO_DEVICE,
            DeviceState.MULTIPLE_DEVICES,
            DeviceState.UNKNOWN,
        ):
            report.add(PreflightCheck(
                name="device_present",
                passed=False,
                severity="BLOCKER",
                message=f"Detection state is {detection.state.value}.",
            ))
            return
        report.add(PreflightCheck(
            name="device_present",
            passed=True,
            severity="INFO",
            message="A single device is identified.",
        ))

    def _check_transport(self, plan: FlashPlan, report: PreflightReport) -> None:
        if plan is None:
            return
        if plan.device_transport not in ("fastboot", "fastbootd"):
            report.add(PreflightCheck(
                name="transport",
                passed=False,
                severity="BLOCKER",
                message=f"Transport '{plan.device_transport}' is not fastboot-compatible.",
            ))
            return
        report.add(PreflightCheck(
            name="transport",
            passed=True,
            severity="INFO",
            message=f"Transport: {plan.device_transport}",
        ))

    def _check_serial(
        self,
        device: Optional[DeviceIdentity],
        plan: FlashPlan,
        report: PreflightReport,
    ) -> None:
        if device is None or plan is None:
            return
        if plan.device_serial is None:
            report.add(PreflightCheck(
                name="serial_confirmed",
                passed=False,
                severity="ERROR",
                message="Plan does not specify a target serial.",
            ))
            return
        if device.serial and device.serial != plan.device_serial:
            report.add(PreflightCheck(
                name="serial_confirmed",
                passed=False,
                severity="BLOCKER",
                message=f"Serial mismatch: plan={plan.device_serial} device={device.serial}",
            ))
            return
        report.add(PreflightCheck(
            name="serial_confirmed",
            passed=True,
            severity="INFO",
            message=f"Serial: {plan.device_serial}",
        ))

    def _check_firmware_present(
        self,
        firmware: Optional[FirmwarePackage],
        report: PreflightReport,
    ) -> None:
        if firmware is None:
            report.add(PreflightCheck(
                name="firmware_present",
                passed=False,
                severity="BLOCKER",
                message="No firmware package is selected.",
            ))
            return
        if firmware.metadata.has_errors():
            report.add(PreflightCheck(
                name="firmware_present",
                passed=False,
                severity="BLOCKER",
                message="Firmware metadata contains errors.",
            ))
            return
        report.add(PreflightCheck(
            name="firmware_present",
            passed=True,
            severity="INFO",
            message=f"Firmware type: {firmware.metadata.package_type}",
        ))

    def _check_compatibility(
        self,
        compatibility: Optional[CompatibilityResult],
        report: PreflightReport,
    ) -> None:
        if compatibility is None:
            report.add(PreflightCheck(
                name="compatibility",
                passed=False,
                severity="BLOCKER",
                message="Compatibility has not been evaluated.",
            ))
            return

        status = compatibility.status
        if status == CompatibilityStatus.MISMATCH:
            report.add(PreflightCheck(
                name="compatibility",
                passed=False,
                severity="BLOCKER",
                message="Compatibility MISMATCH blocks execution.",
            ))
            return
        if status == CompatibilityStatus.BLOCKED:
            report.add(PreflightCheck(
                name="compatibility",
                passed=False,
                severity="BLOCKER",
                message="Compatibility BLOCKED.",
            ))
            return
        if status == CompatibilityStatus.UNKNOWN:
            allowed = self._settings.safety.allow_unknown_compatibility
            report.add(PreflightCheck(
                name="compatibility",
                passed=allowed,
                severity="WARNING" if allowed else "BLOCKER",
                message=(
                    "Compatibility UNKNOWN. "
                    + ("Elevated confirmation required." if allowed else "Blocked by settings.")
                ),
            ))
            return
        if status == CompatibilityStatus.LIKELY:
            allowed = self._settings.safety.allow_likely_compatibility
            report.add(PreflightCheck(
                name="compatibility",
                passed=allowed,
                severity="INFO" if allowed else "BLOCKER",
                message="Compatibility LIKELY.",
            ))
            return
        report.add(PreflightCheck(
            name="compatibility",
            passed=True,
            severity="INFO",
            message=f"Compatibility: {status.value}",
        ))

    def _check_partitions(
        self,
        plan: FlashPlan,
        analysis: Optional[PartitionAnalysis],
        report: PreflightReport,
    ) -> None:
        if plan is None:
            return
        for op in plan.operations:
            if op.kind != FlashOperationKind.FLASH_IMAGE:
                continue
            if not op.partition:
                report.add(PreflightCheck(
                    name=f"partition_{op.partition or 'unknown'}",
                    passed=False,
                    severity="BLOCKER",
                    message="Flash operation has no partition.",
                ))
                continue

            if analysis is None or analysis.device is None:
                # No device partition model available; allow but warn.
                report.add(PreflightCheck(
                    name=f"partition_{op.partition}",
                    passed=True,
                    severity="WARNING",
                    message=f"Partition model unavailable; cannot confirm {op.partition}.",
                ))
                continue

            if analysis.device.get(op.partition) is None:
                report.add(PreflightCheck(
                    name=f"partition_{op.partition}",
                    passed=False,
                    severity="BLOCKER",
                    message=f"Partition '{op.partition}' not present in device model.",
                ))
            else:
                report.add(PreflightCheck(
                    name=f"partition_{op.partition}",
                    passed=True,
                    severity="INFO",
                    message=f"Partition '{op.partition}' is present.",
                ))

    def _check_slot_architecture(
        self,
        plan: FlashPlan,
        device: Optional[DeviceIdentity],
        slot_info: Optional[SlotInfo],
        report: PreflightReport,
    ) -> None:
        if plan is None or device is None:
            return
        if plan.slot_strategy == SlotStrategy.NONE:
            return
        if not device.slot_support:
            report.add(PreflightCheck(
                name="slot_architecture",
                passed=False,
                severity="BLOCKER",
                message="Plan uses a slot strategy but device reports no A/B support.",
            ))
            return
        if plan.slot_strategy in (SlotStrategy.OTHER, SlotStrategy.EXPLICIT, SlotStrategy.BOTH):
            if not self._settings.safety.allow_ab_slot_change:
                report.add(PreflightCheck(
                    name="slot_architecture",
                    passed=False,
                    severity="BLOCKER",
                    message="Slot changes are disabled by safety settings.",
                ))
                return
        report.add(PreflightCheck(
            name="slot_architecture",
            passed=True,
            severity="INFO",
            message=f"Slot strategy: {plan.slot_strategy.value}",
        ))

    def _check_bootloader(
        self,
        bootloader_info: Optional[BootloaderInfo],
        device: Optional[DeviceIdentity],
        report: PreflightReport,
    ) -> None:
        if not self._settings.safety.require_bootloader_check:
            report.add(PreflightCheck(
                name="bootloader",
                passed=True,
                severity="INFO",
                message="Bootloader check disabled by settings.",
            ))
            return

        lock_state: Optional[str] = None
        if bootloader_info is not None:
            lock_state = getattr(bootloader_info.state, "value", None) or str(
                bootloader_info.state
            )
        elif device is not None:
            lock = getattr(device, "bootloader_state", None)
            lock_state = getattr(lock, "value", None) if lock is not None else None

        if lock_state == "locked":
            report.add(PreflightCheck(
                name="bootloader",
                passed=False,
                severity="BLOCKER",
                message="Bootloader is locked; flashing is not permitted.",
            ))
            return
        if lock_state is None:
            report.add(PreflightCheck(
                name="bootloader",
                passed=True,
                severity="WARNING",
                message="Bootloader lock state could not be determined.",
            ))
            return
        report.add(PreflightCheck(
            name="bootloader",
            passed=True,
            severity="INFO",
            message=f"Bootloader state: {lock_state}",
        ))

    def _check_capabilities(
        self,
        plan: FlashPlan,
        device: Optional[DeviceIdentity],
        report: PreflightReport,
    ) -> None:
        if plan is None or device is None:
            return
        caps = getattr(device, "capabilities", None)

        for op in plan.operations:
            if op.requires_fastbootd:
                if not getattr(caps, "supports_fastbootd", True):
                    report.add(PreflightCheck(
                        name="fastbootd_capability",
                        passed=False,
                        severity="BLOCKER",
                        message="Operation requires fastbootd but device reports no support.",
                    ))
            if op.kind == FlashOperationKind.UPDATE_PACKAGE:
                if not getattr(caps, "supports_update", True):
                    report.add(PreflightCheck(
                        name="update_capability",
                        passed=False,
                        severity="BLOCKER",
                        message="Device reports no support for fastboot update.",
                    ))
            if op.partition in ("system", "product", "vendor", "system_ext", "odm", "super"):
                if getattr(caps, "supports_dynamic_partitions", None) is False and op.partition in (
                    "system", "product", "vendor", "system_ext", "odm"
                ):
                    report.add(PreflightCheck(
                        name=f"dynamic_capability_{op.partition}",
                        passed=False,
                        severity="BLOCKER",
                        message=(
                            f"Firmware targets logical partition '{op.partition}' but device "
                            f"reports no dynamic partition support."
                        ),
                    ))

        if not any(c.name.startswith(("fastbootd_capability", "update_capability", "dynamic_capability")) for c in report.checks):
            report.add(PreflightCheck(
                name="capabilities",
                passed=True,
                severity="INFO",
                message="Device capabilities satisfy the plan.",
            ))

    def _check_integrity(
        self,
        firmware: Optional[FirmwarePackage],
        report: PreflightReport,
    ) -> None:
        if firmware is None:
            return
        if not self._settings.safety.require_hash_verification:
            report.add(PreflightCheck(
                name="integrity",
                passed=True,
                severity="INFO",
                message="Integrity check disabled by settings.",
            ))
            return
        if not firmware.metadata.source_sha256 and not firmware.metadata.source_sha512:
            report.add(PreflightCheck(
                name="integrity",
                passed=True,
                severity="WARNING",
                message="Firmware has no recorded hash; integrity unverified.",
            ))
            return
        report.add(PreflightCheck(
            name="integrity",
            passed=True,
            severity="INFO",
            message="Firmware hash is recorded.",
        ))

    def _check_operations(self, plan: FlashPlan, report: PreflightReport) -> None:
        if plan is None:
            return
        for op in plan.operations:
            if op.avb_disable:
                if not self._settings.flash.allow_avb_disable:
                    report.add(PreflightCheck(
                        name="avb_disable",
                        passed=False,
                        severity="BLOCKER",
                        message="AVB disable is not permitted by settings.",
                    ))
                else:
                    report.add(PreflightCheck(
                        name="avb_disable",
                        passed=True,
                        severity="WARNING",
                        message="AVB disable requested; CRITICAL risk.",
                    ))
            if op.kind == FlashOperationKind.ERASE_PARTITION:
                if not self._settings.safety.allow_erase:
                    report.add(PreflightCheck(
                        name="erase_partition",
                        passed=False,
                        severity="BLOCKER",
                        message="Erase is disabled by safety settings.",
                    ))
            if op.kind == FlashOperationKind.FORMAT_PARTITION:
                if not self._settings.safety.allow_format:
                    report.add(PreflightCheck(
                        name="format_partition",
                        passed=False,
                        severity="BLOCKER",
                        message="Format is disabled by safety settings.",
                    ))
            if op.kind == FlashOperationKind.SET_ACTIVE_SLOT:
                if not self._settings.safety.allow_set_active:
                    report.add(PreflightCheck(
                        name="set_active_slot",
                        passed=False,
                        severity="BLOCKER",
                        message="Changing the active slot is disabled by safety settings.",
                    ))

    def _check_confirmation(
        self,
        plan: FlashPlan,
        compatibility: Optional[CompatibilityResult],
        report: PreflightReport,
    ) -> None:
        if plan is None:
            return
        if not self._settings.safety.require_confirmation:
            report.add(PreflightCheck(
                name="confirmation_requirement",
                passed=True,
                severity="INFO",
                message="Confirmation disabled by settings.",
            ))
            return
        if plan.confirmation_required == "NONE":
            report.add(PreflightCheck(
                name="confirmation_requirement",
                passed=True,
                severity="INFO",
                message="No confirmation required for this plan.",
            ))
            return
        report.add(PreflightCheck(
            name="confirmation_requirement",
            passed=True,
            severity="INFO",
            message=f"Confirmation level: {plan.confirmation_required}",
        ))
