"""High-level flasher facade.

Combines the planner, safety preflight, command builder, executor and
verification into a single object that the UI can drive. The GUI never
sees subprocess primitives or raw fastboot commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from android_flasher.config.settings import Settings
from android_flasher.core.command_executor import ExecutionResult
from android_flasher.core.flash_engine import ExecutionTrace, FlashEngine
from android_flasher.core.flash_plan import FlashPlan, FlashPlanStatus
from android_flasher.devices.bootloader import BootloaderInfo
from android_flasher.devices.detection import DetectionResult
from android_flasher.devices.identification import DeviceIdentity
from android_flasher.devices.slots import SlotInfo
from android_flasher.firmware.compatibility import CompatibilityResult
from android_flasher.firmware.package import FirmwarePackage
from android_flasher.logging.logger import get_logger
from android_flasher.partitions.manager import PartitionAnalysis
from android_flasher.safety.preflight import PreflightReport, SafetyPreflight
from android_flasher.safety.risk import RiskAssessment, RiskAssessor

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Request / response
# ---------------------------------------------------------------------------

@dataclass
class FlasherRequest:
    """Everything the flasher needs to run a single operation."""

    settings: Settings
    fastboot_path: Path
    adb_path: Optional[Path] = None
    device: Optional[DeviceIdentity] = None
    firmware: Optional[FirmwarePackage] = None
    compatibility: Optional[CompatibilityResult] = None
    partition_analysis: Optional[PartitionAnalysis] = None
    detection: Optional[DetectionResult] = None
    slot_info: Optional[SlotInfo] = None
    bootloader_info: Optional[BootloaderInfo] = None
    confirmed: bool = False


@dataclass
class FlasherOutcome:
    """Result of a full flasher run."""

    plan: Optional[FlashPlan] = None
    preflight: Optional[PreflightReport] = None
    risk: Optional[RiskAssessment] = None
    trace: Optional[ExecutionTrace] = None
    error: str = ""
    refused: bool = False

    def to_dict(self) -> dict:
        return {
            "plan": self.plan.to_dict() if self.plan else None,
            "preflight": self.preflight.to_dict() if self.preflight else None,
            "risk": self.risk.to_dict() if self.risk else None,
            "trace": self.trace.to_dict() if self.trace else None,
            "error": self.error,
            "refused": self.refused,
        }


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------

class Flasher:
    """Facade that runs the full planning → preflight → execution chain."""

    def __init__(self, request: FlasherRequest) -> None:
        self._request = request

    # ------------------------------------------------------------------
    # Plan only
    # ------------------------------------------------------------------

    def build_plan(self) -> FlashPlan:
        """Generate a flash plan from the request.

        Delegates to the planner factory in this module.
        """
        return build_flash_plan(
            settings=self._request.settings,
            device=self._request.device,
            firmware=self._request.firmware,
            compatibility=self._request.compatibility,
            partition_analysis=self._request.partition_analysis,
            detection=self._request.detection,
            bootloader_info=self._request.bootloader_info,
            slot_info=self._request.slot_info,
        )

    # ------------------------------------------------------------------
    # Preflight
    # ------------------------------------------------------------------

    def preflight(self, plan: FlashPlan) -> PreflightReport:
        preflight = SafetyPreflight(self._request.settings)
        return preflight.run(
            plan=plan,
            device=self._request.device,
            firmware=self._request.firmware,
            compatibility=self._request.compatibility,
            partition_analysis=self._request.partition_analysis,
            detection=self._request.detection,
            bootloader_info=self._request.bootloader_info,
            slot_info=self._request.slot_info,
        )

    # ------------------------------------------------------------------
    # Risk
    # ------------------------------------------------------------------

    def assess_risk(
        self,
        plan: FlashPlan,
        preflight: PreflightReport,
    ) -> RiskAssessment:
        assessor = RiskAssessor()
        return assessor.assess(
            plan=plan,
            device=self._request.device,
            firmware=self._request.firmware,
            compatibility=self._request.compatibility,
            preflight=preflight,
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(
        self,
        plan: FlashPlan,
        *,
        on_step_start: Optional[Callable[[int, str], None]] = None,
        on_step_output: Optional[Callable[[int, str], None]] = None,
        on_step_finish: Optional[Callable[[int, ExecutionResult], None]] = None,
    ) -> FlasherOutcome:
        outcome = FlasherOutcome(plan=plan)

        # Preflight must be run and must not be blocked.
        preflight = self.preflight(plan)
        outcome.preflight = preflight
        if preflight.is_blocked():
            outcome.error = "Preflight blocked the plan."
            outcome.refused = True
            return outcome

        # Risk assessment.
        risk = self.assess_risk(plan, preflight)
        outcome.risk = risk

        if risk.blocked:
            outcome.error = "Risk assessor blocked the plan."
            outcome.refused = True
            return outcome

        # Confirmation.
        if plan.confirmation_required in ("STANDARD", "ELEVATED") and not self._request.confirmed:
            outcome.error = "Confirmation was not provided."
            outcome.refused = True
            return outcome

        engine = FlashEngine(
            self._request.settings,
            self._request.fastboot_path,
            self._request.adb_path,
        )
        outcome.trace = engine.execute(
            plan,
            confirmed=self._request.confirmed,
            on_step_start=on_step_start,
            on_step_output=on_step_output,
            on_step_finish=on_step_finish,
        )
        return outcome


# ---------------------------------------------------------------------------
# Planner factory
# ---------------------------------------------------------------------------

def build_flash_plan(
    *,
    settings: Settings,
    device: Optional[DeviceIdentity],
    firmware: Optional[FirmwarePackage],
    compatibility: Optional[CompatibilityResult],
    partition_analysis: Optional[PartitionAnalysis],
    detection: Optional[DetectionResult] = None,
    bootloader_info: Optional[BootloaderInfo] = None,
    slot_info: Optional[SlotInfo] = None,
) -> FlashPlan:
    """Local import to avoid cyclic dependency at module load time."""
    from android_flasher.core.flash_plan import FlashPlan  # noqa: WPS433
    from android_flasher.safety.planner import FlashPlanner  # noqa: WPS433

    planner = FlashPlanner(settings)
    return planner.plan(
        device=device,
        firmware=firmware,
        compatibility=compatibility,
        partition_analysis=partition_analysis,
        detection=detection,
        bootloader_info=bootloader_info,
        slot_info=slot_info,
    )
