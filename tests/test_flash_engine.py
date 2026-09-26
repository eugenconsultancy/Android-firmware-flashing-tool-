"""Tests for the flash engine (Phase 3)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from android_flasher.config.settings import Settings
from android_flasher.core.command_builder import CommandBuilder, CommandSpec
from android_flasher.core.command_executor import (
    CommandExecutor,
    ExecutionResult,
    ExecutionStatus,
)
from android_flasher.core.flash_plan import (
    FlashOperation,
    FlashOperationKind,
    FlashPlan,
    FlashPlanStatus,
    FlashStep,
    FlashStepKind,
)


class StubExecutor(CommandExecutor):
    """Executor that returns canned results without spawning processes."""

    def __init__(self, responses: list[ExecutionResult]) -> None:
        super().__init__()
        self._responses = list(responses)
        self.calls: list[list[str]] = []

    def execute(self, spec: CommandSpec, *, cwd=None, env=None, on_output=None) -> ExecutionResult:  # type: ignore[override]
        self.calls.append(list(spec.argv))
        if on_output:
            on_output("stub output")
        if self._responses:
            return self._responses.pop(0)
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            returncode=0,
            argv=list(spec.argv),
        )


def _plan(tmp_path: Path) -> FlashPlan:
    plan = FlashPlan(plan_id="engine-test")
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


def test_engine_refuses_blocked_plan(tmp_path: Path, monkeypatch) -> None:
    from android_flasher.core import flash_engine as fe

    plan = _plan(tmp_path)
    plan.status = FlashPlanStatus.BLOCKED
    plan.add_blocker("test blocker")

    engine = fe.FlashEngine(Settings(), Path("/tmp/fastboot"))
    trace = engine.execute(plan, confirmed=True)
    assert trace.started is False
    assert trace.error != ""


def test_engine_refuses_unconfirmed_plan(tmp_path: Path) -> None:
    from android_flasher.core import flash_engine as fe

    plan = _plan(tmp_path)
    plan.confirmation_required = "ELEVATED"
    plan.status = FlashPlanStatus.REQUIRES_CONFIRMATION

    engine = fe.FlashEngine(Settings(), Path("/tmp/fastboot"))
    trace = engine.execute(plan, confirmed=False)
    assert trace.started is False
    assert "confirm" in trace.error.lower()


def test_engine_runs_steps(tmp_path: Path) -> None:
    from android_flasher.core import flash_engine as fe

    plan = _plan(tmp_path)
    plan.status = FlashPlanStatus.READY
    plan.confirmation_required = "NONE"

    engine = fe.FlashEngine(Settings(), Path("/tmp/fastboot"))
    # Replace the executor with a stub.
    engine._executor = StubExecutor([
        ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            returncode=0,
            stdout="flashed",
            argv=[],
        )
    ])

    trace = engine.execute(plan, confirmed=True)
    assert trace.started is True
    assert trace.completed is True
    assert trace.verification is not None
    assert trace.verification.status.value in ("SUCCESS", "PARTIAL")


def test_engine_records_failed_step(tmp_path: Path) -> None:
    from android_flasher.core import flash_engine as fe

    plan = _plan(tmp_path)
    plan.status = FlashPlanStatus.READY
    plan.confirmation_required = "NONE"

    engine = fe.FlashEngine(Settings(), Path("/tmp/fastboot"))
    engine._executor = StubExecutor([
        ExecutionResult(
            status=ExecutionStatus.FAILED,
            returncode=1,
            stdout="",
            stderr="boom",
            argv=[],
        )
    ])
    trace = engine.execute(plan, confirmed=True)
    assert trace.verification is not None
    assert trace.verification.status.value == "FAILED"


def test_executor_returns_skipped_for_empty_argv() -> None:
    executor = CommandExecutor()
    spec = CommandSpec(argv=[], transport="none", description="note")
    result = executor.execute(spec)
    assert result.status == ExecutionStatus.SKIPPED


def test_executor_shell_false_invocation(monkeypatch) -> None:
    captured = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.stdout = None
            self.stderr = None
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    import android_flasher.core.command_executor as ce

    monkeypatch.setattr(ce.subprocess, "Popen", FakePopen)

    executor = ce.CommandExecutor()
    spec = CommandSpec(
        argv=["/usr/bin/fastboot", "getvar", "product"],
        transport="fastboot",
    )
    executor.execute(spec)
    assert captured["kwargs"].get("shell") is False
