"""Post-operation verification.

Verification records:

    - per-step command result
    - per-step expected markers (where meaningful)
    - a final re-detection of the device
    - a final read of slot state
    - a final read of bootloader state

Verification never claims the device *will* boot. It reports observed
state and flags divergence from expectations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from android_flasher.core.command_executor import ExecutionResult, ExecutionStatus
from android_flasher.core.flash_plan import FlashPlan, FlashStepKind
from android_flasher.devices.bootloader import BootloaderInfo
from android_flasher.devices.detection import DetectionResult
from android_flasher.devices.identification import DeviceIdentity
from android_flasher.devices.slots import SlotInfo
from android_flasher.logging.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums and models
# ---------------------------------------------------------------------------

class VerificationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class StepVerification:
    """Verification of a single executed step."""

    index: int
    description: str
    command: list[str]
    result_status: str
    returncode: Optional[int]
    markers_matched: list[str] = field(default_factory=list)
    markers_missing: list[str] = field(default_factory=list)
    note: str = ""

    def ok(self) -> bool:
        return self.result_status == ExecutionStatus.SUCCESS.value

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "description": self.description,
            "command": list(self.command),
            "result_status": self.result_status,
            "returncode": self.returncode,
            "markers_matched": list(self.markers_matched),
            "markers_missing": list(self.markers_missing),
            "note": self.note,
        }


@dataclass
class VerificationReport:
    """Aggregate verification report."""

    status: VerificationStatus = VerificationStatus.UNKNOWN
    steps: list[StepVerification] = field(default_factory=list)
    device_detection: Optional[dict] = None
    active_slot: Optional[str] = None
    bootloader_state: Optional[str] = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_step(self, step: StepVerification) -> None:
        self.steps.append(step)

    def add_note(self, message: str) -> None:
        if message and message not in self.notes:
            self.notes.append(message)

    def add_warning(self, message: str) -> None:
        if message and message not in self.warnings:
            self.warnings.append(message)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "device_detection": self.device_detection,
            "active_slot": self.active_slot,
            "bootloader_state": self.bootloader_state,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class VerificationEngine:
    """Verifies execution results against a plan."""

    def verify_steps(
        self,
        plan: FlashPlan,
        results: list[ExecutionResult],
    ) -> VerificationReport:
        report = VerificationReport()

        if len(results) != len(plan.steps):
            report.add_warning(
                "Step results count does not match plan steps count; "
                "verification may be incomplete."
            )

        for step, result in zip(plan.steps, results):
            verification = StepVerification(
                index=step.index,
                description=step.description,
                command=list(step.command) if step.command else [],
                result_status=result.status.value,
                returncode=result.returncode,
            )

            if step.expected_stdout_markers:
                combined = (result.stdout or "") + "\n" + (result.stderr or "")
                for marker in step.expected_stdout_markers:
                    if marker and marker in combined:
                        verification.markers_matched.append(marker)
                    else:
                        verification.markers_missing.append(marker)
                if verification.markers_missing:
                    verification.note = "expected markers not found"

            if step.optional and not result.ok():
                verification.note = (verification.note + "; optional step failed").strip("; ")

            report.add_step(verification)

        # Aggregate.
        if not report.steps:
            report.status = VerificationStatus.UNKNOWN
            return report

        failed = [
            s for s in report.steps
            if not s.ok() and not self._step_optional(plan, s.index)
        ]
        cancelled = [
            s for s in report.steps
            if s.result_status == ExecutionStatus.CANCELLED.value
        ]
        timed_out = [
            s for s in report.steps
            if s.result_status == ExecutionStatus.TIMEOUT.value
        ]

        if cancelled or timed_out or failed:
            report.status = VerificationStatus.FAILED
            if cancelled:
                report.add_warning("At least one step was cancelled.")
            if timed_out:
                report.add_warning("At least one step timed out.")
            if failed:
                report.add_warning(
                    f"{len(failed)} step(s) failed with nonzero exit."
                )
        else:
            report.status = VerificationStatus.SUCCESS

        return report

    def add_final_device_state(
        self,
        report: VerificationReport,
        detection: Optional[DetectionResult] = None,
        identity: Optional[DeviceIdentity] = None,
        slot_info: Optional[SlotInfo] = None,
        bootloader_info: Optional[BootloaderInfo] = None,
    ) -> VerificationReport:
        if detection is not None:
            report.device_detection = {
                "state": detection.state.value,
                "message": detection.message,
            }
        if identity is not None:
            report.device_detection = report.device_detection or {}
            report.device_detection["serial"] = identity.serial
            report.device_detection["codename"] = identity.device_codename
        if slot_info is not None:
            report.active_slot = slot_info.current_slot or slot_info.slot_suffix
        if bootloader_info is not None:
            state = bootloader_info.state
            report.bootloader_state = state.value if hasattr(state, "value") else str(state)

        # Downgrade to PARTIAL if we could not observe final state.
        if report.status == VerificationStatus.SUCCESS:
            if report.device_detection is None:
                report.status = VerificationStatus.PARTIAL
                report.add_note("Device was not re-detected after execution.")
        return report

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _step_optional(plan: FlashPlan, index: int) -> bool:
        for step in plan.steps:
            if step.index == index:
                return step.optional
        return False
