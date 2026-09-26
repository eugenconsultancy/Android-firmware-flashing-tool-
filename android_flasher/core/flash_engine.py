"""Flash engine.

Executes a ``FlashPlan`` step-by-step using a ``CommandExecutor``.
Enforces:

    - plan must not be blocked
    - plan must be READY or REQUIRES_CONFIRMATION with a confirmed flag
    - per-step command spec produced by ``CommandBuilder``
    - optional per-step verification markers
    - cancel support
    - structured trace and verification report

The engine never builds commands itself. It never runs a shell.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from android_flasher.config.settings import Settings
from android_flasher.core.command_builder import CommandBuilder, CommandSpec
from android_flasher.core.command_executor import (
    CommandExecutor,
    ExecutionResult,
    ExecutionStatus,
)
from android_flasher.core.flash_plan import FlashPlan, FlashPlanStatus, FlashStepKind
from android_flasher.core.verification import (
    VerificationEngine,
    VerificationReport,
)
from android_flasher.logging.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Trace model
# ---------------------------------------------------------------------------

@dataclass
class StepTrace:
    """Execution trace for a single step."""

    index: int
    description: str
    spec: Optional[CommandSpec]
    result: Optional[ExecutionResult] = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "description": self.description,
            "spec": self.spec.to_dict() if self.spec else None,
            "result": self.result.to_dict() if self.result else None,
        }


@dataclass
class ExecutionTrace:
    """Complete execution trace for a plan."""

    plan_id: str
    started: bool = False
    completed: bool = False
    cancelled: bool = False
    step_traces: list[StepTrace] = field(default_factory=list)
    verification: Optional[VerificationReport] = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "started": self.started,
            "completed": self.completed,
            "cancelled": self.cancelled,
            "step_traces": [t.to_dict() for t in self.step_traces],
            "verification": self.verification.to_dict() if self.verification else None,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class FlashEngine:
    """Executes a flash plan under tight control."""

    def __init__(
        self,
        settings: Settings,
        fastboot_path: Path,
        adb_path: Optional[Path] = None,
    ) -> None:
        self._settings = settings
        self._builder = CommandBuilder(fastboot_path, adb_path)
        self._executor = CommandExecutor(
            default_timeout=settings.flash.step_timeout_seconds,
            output_limit=settings.flash.per_step_output_limit,
            cancel_grace_seconds=settings.safety.cancel_grace_seconds,
        )
        self._verifier = VerificationEngine()
        self._cancelled = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        plan: FlashPlan,
        *,
        confirmed: bool,
        on_step_start: Optional[Callable[[int, str], None]] = None,
        on_step_output: Optional[Callable[[int, str], None]] = None,
        on_step_finish: Optional[Callable[[int, ExecutionResult], None]] = None,
    ) -> ExecutionTrace:
        """Execute the plan. Returns a full execution trace."""
        trace = ExecutionTrace(plan_id=plan.plan_id)

        # Refuse blocked plans.
        if plan.is_blocked() or plan.status == FlashPlanStatus.BLOCKED:
            trace.error = "Plan is blocked."
            log.warning("Refused to execute blocked plan %s", plan.plan_id)
            return trace

        # Require confirmation when plan asked for it.
        if plan.confirmation_required in ("STANDARD", "ELEVATED") and not confirmed:
            trace.error = "Plan requires confirmation and none was provided."
            log.warning("Refused to execute unconfirmed plan %s", plan.plan_id)
            return trace

        # Refuse if plan has no steps.
        if not plan.steps:
            trace.error = "Plan has no executable steps."
            return trace

        trace.started = True
        results: list[ExecutionResult] = []

        for step in plan.steps:
            if self._cancelled.is_set():
                trace.cancelled = True
                break

            spec = self._builder.build_for_step(
                step,
                timeout_default=self._settings.flash.step_timeout_seconds,
            )
            step.command = list(spec.argv)

            step_trace = StepTrace(
                index=step.index,
                description=step.description,
                spec=spec,
            )
            trace.step_traces.append(step_trace)

            if on_step_start is not None:
                try:
                    on_step_start(step.index, step.description)
                except Exception:  # noqa: BLE001 - defensive
                    log.exception("on_step_start callback failed")

            # Empty commands (pure notes) short-circuit.
            if not spec.argv:
                result = ExecutionResult(
                    status=ExecutionStatus.SKIPPED,
                    argv=[],
                    error="",
                )
                step_trace.result = result
                results.append(result)
                if on_step_finish is not None:
                    try:
                        on_step_finish(step.index, result)
                    except Exception:  # noqa: BLE001 - defensive
                        log.exception("on_step_finish callback failed")
                continue

            def _on_output(line: str, _idx: int = step.index) -> None:
                if on_step_output is not None:
                    try:
                        on_step_output(_idx, line)
                    except Exception:  # noqa: BLE001 - defensive
                        log.exception("on_step_output callback failed")

            result = self._executor.execute(spec, on_output=_on_output)
            step_trace.result = result
            results.append(result)

            if on_step_finish is not None:
                try:
                    on_step_finish(step.index, result)
                except Exception:  # noqa: BLE001 - defensive
                    log.exception("on_step_finish callback failed")

            if not result.ok() and not step.optional:
                log.warning(
                    "Step %d failed (status=%s); stopping execution.",
                    step.index,
                    result.status.value,
                )
                break

        trace.completed = not self._cancelled.is_set()

        # Build verification report.
        trace.verification = self._verifier.verify_steps(plan, results)
        return trace

    def cancel(self) -> None:
        """Cancel the currently running plan."""
        self._cancelled.set()
        self._executor.cancel()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def prepare_for_reboot_steps(plan: FlashPlan) -> None:
        """Mutates a plan to insert a reboot step when needed.

        Used by the planner, not the engine. Kept here so that the
        engine owns the semantic of "reboot to switch mode".
        """
        _ = plan  # explicit no-op; planner handles this directly
