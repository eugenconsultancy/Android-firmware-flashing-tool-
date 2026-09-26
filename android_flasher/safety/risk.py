"""Risk classification.

Risk is computed from the *characteristics* of an operation and the
state of the device. It is never a fixed label.

Risk levels (ascending):

    LOW       - read-only or fully reversible, no destructive effect.
    MEDIUM    - writes to a partition but preserves device usability
                when executed on a compatible target with an unlocked
                bootloader.
    HIGH      - writes to bootloader / radio / vbmeta, changes the
                active slot, or operates on dynamic partitions.
    CRITICAL  - disables AVB, wipes data, or unlocks the bootloader.

Higher risk requires higher confirmation. ``SafetySettings`` decides
whether CRITICAL is blocked outright.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from android_flasher.core.flash_plan import (
    FlashOperationKind,
    FlashPlan,
    SlotStrategy,
)
from android_flasher.devices.identification import DeviceIdentity
from android_flasher.firmware.compatibility import (
    CompatibilityResult,
    CompatibilityStatus,
)
from android_flasher.firmware.package import FirmwarePackage
from android_flasher.logging.logger import get_logger
from android_flasher.safety.preflight import PreflightReport


log = get_logger(__name__)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    @property
    def order(self) -> int:
        # UNKNOWN is intentionally the *lowest* rank so that
        # ``_raise_to`` can promote it. UNKNOWN is only used as the
        # initial sentinel; a real assessment never remains UNKNOWN.
        return {
            RiskLevel.UNKNOWN: -1,
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }[self]


@dataclass
class RiskAssessment:
    """Aggregate risk classification for a plan."""

    level: RiskLevel = RiskLevel.UNKNOWN
    reasons: list[str] = field(default_factory=list)
    blocked: bool = False
    blocking_reason: str = ""

    def add_reason(self, message: str) -> None:
        if message and message not in self.reasons:
            self.reasons.append(message)

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "reasons": list(self.reasons),
            "blocked": self.blocked,
            "blocking_reason": self.blocking_reason,
        }


class RiskAssessor:
    """Computes a risk level for a plan."""

    def assess(
        self,
        *,
        plan: FlashPlan,
        device: Optional[DeviceIdentity],
        firmware: Optional[FirmwarePackage],
        compatibility: Optional[CompatibilityResult],
        preflight: Optional[PreflightReport] = None,
    ) -> RiskAssessment:
        assessment = RiskAssessment()
        assessment.level = RiskLevel.UNKNOWN

        if plan is None:
            assessment.level = RiskLevel.UNKNOWN
            assessment.add_reason("No plan provided.")
            return assessment

        if plan.is_blocked():
            assessment.level = RiskLevel.CRITICAL
            assessment.blocked = True
            assessment.blocking_reason = "Plan is already blocked."
            assessment.add_reason("Plan is blocked by the planner.")
            return assessment

        # Compatibility influence.
        if compatibility is not None:
            if compatibility.status == CompatibilityStatus.MISMATCH:
                assessment.blocked = True
                assessment.blocking_reason = "Compatibility mismatch."
                assessment.level = RiskLevel.CRITICAL
                assessment.add_reason("Firmware/device compatibility mismatch.")
            elif compatibility.status == CompatibilityStatus.BLOCKED:
                assessment.blocked = True
                assessment.blocking_reason = "Compatibility blocked."
                assessment.level = RiskLevel.CRITICAL
                assessment.add_reason("Compatibility engine blocked the plan.")
            elif compatibility.status == CompatibilityStatus.UNKNOWN:
                assessment.add_reason(
                    "Compatibility unknown; elevated confirmation required."
                )
                assessment.level = RiskLevel.HIGH
            elif compatibility.status == CompatibilityStatus.LIKELY:
                assessment.add_reason("Compatibility likely but not confirmed.")
                if assessment.level.order < RiskLevel.MEDIUM.order:
                    assessment.level = RiskLevel.MEDIUM

        # Bootloader state.
        if device is not None:
            lock = getattr(device, "bootloader_state", None)
            lock_value = getattr(lock, "value", None) if lock else None
            if lock_value == "locked":
                assessment.blocked = True
                assessment.blocking_reason = "Bootloader is locked."
                assessment.level = RiskLevel.CRITICAL
                assessment.add_reason("Bootloader is locked.")

        # Per-operation contribution. Run this BEFORE the fallback so
        # that operations can raise the level.
        for op in plan.operations:
            self._contribute_operation(op, plan, assessment)

        # Preflight failures escalate risk.
        if preflight is not None and preflight.has_failures():
            assessment.blocked = True
            assessment.blocking_reason = "Preflight failed."
            assessment.level = RiskLevel.CRITICAL
            assessment.add_reason("Preflight checks failed.")

        if assessment.level == RiskLevel.UNKNOWN:
            assessment.level = RiskLevel.LOW
            assessment.add_reason("No destructive operations were identified.")

        return assessment

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _contribute_operation(
        self,
        op,
        plan: FlashPlan,
        assessment: RiskAssessment,
    ) -> None:
        kind = op.kind

        if kind == FlashOperationKind.NO_OP:
            return

        if kind == FlashOperationKind.REBOOT_SYSTEM:
            self._raise_to(assessment, RiskLevel.LOW, "reboot system")
            return

        if kind == FlashOperationKind.REBOOT_BOOTLOADER:
            self._raise_to(assessment, RiskLevel.LOW, "reboot to bootloader")
            return

        if kind == FlashOperationKind.REBOOT_FASTBOOTD:
            self._raise_to(assessment, RiskLevel.LOW, "reboot to fastbootd")
            return

        if kind == FlashOperationKind.SET_ACTIVE_SLOT:
            self._raise_to(assessment, RiskLevel.HIGH, "set active slot")
            return

        if kind == FlashOperationKind.ERASE_PARTITION:
            self._raise_to(assessment, RiskLevel.CRITICAL, "erase partition")
            return

        if kind == FlashOperationKind.FORMAT_PARTITION:
            self._raise_to(assessment, RiskLevel.CRITICAL, "format partition")
            return

        if kind == FlashOperationKind.UPDATE_PACKAGE:
            self._raise_to(assessment, RiskLevel.HIGH, "update package")
            return

        if kind == FlashOperationKind.FLASH_IMAGE:
            # AVB disable is always CRITICAL regardless of partition.
            if op.avb_disable:
                self._raise_to(assessment, RiskLevel.CRITICAL, "AVB disable")

            partition = (op.partition or "").lower()
            if partition in ("bootloader", "radio", "modem"):
                self._raise_to(assessment, RiskLevel.HIGH, f"flash {partition}")
            elif partition in ("vbmeta", "vbmeta_system", "vbmeta_vendor"):
                self._raise_to(assessment, RiskLevel.HIGH, f"flash {partition}")
            elif partition in ("boot", "init_boot", "vendor_boot", "dtbo", "recovery"):
                self._raise_to(assessment, RiskLevel.MEDIUM, f"flash {partition}")
            elif partition in (
                "super",
                "system",
                "system_ext",
                "product",
                "vendor",
                "odm",
            ):
                self._raise_to(assessment, RiskLevel.HIGH, f"flash {partition}")
            elif partition == "userdata":
                self._raise_to(assessment, RiskLevel.CRITICAL, "flash userdata")
            else:
                self._raise_to(
                    assessment,
                    RiskLevel.MEDIUM,
                    f"flash {partition or 'partition'}",
                )

            if op.requires_fastbootd:
                assessment.add_reason("Operation requires fastbootd mode.")
            if op.slot_strategy == SlotStrategy.BOTH:
                self._raise_to(assessment, RiskLevel.HIGH, "flash both slots")

        if plan.reboot_after_flash:
            self._raise_to(assessment, RiskLevel.LOW, "reboot after flash")

    @staticmethod
    def _raise_to(
        assessment: RiskAssessment,
        level: RiskLevel,
        reason: str,
    ) -> None:
        if level.order > assessment.level.order:
            assessment.level = level
        assessment.add_reason(reason)
