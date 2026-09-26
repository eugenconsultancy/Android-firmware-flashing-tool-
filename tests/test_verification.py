"""Tests for the verification engine (Phase 3)."""

from __future__ import annotations

from pathlib import Path

from android_flasher.core.command_executor import (
    ExecutionResult,
    ExecutionStatus,
)
from android_flasher.core.flash_plan import (
    FlashOperation,
    FlashOperationKind,
    FlashPlan,
    FlashStep,
    FlashStepKind,
)
from android_flasher.core.verification import (
    VerificationEngine,
    VerificationStatus,
)


def _plan_with_markers() -> FlashPlan:
    plan = FlashPlan(plan_id="verify")
    op = FlashOperation(
        kind=FlashOperationKind.FLASH_IMAGE,
        partition="boot",
        image_path="/tmp/boot.img",
    )
    step = FlashStep(
        index=0,
        kind=FlashStepKind.FLASH,
        operation=op,
        description="flash boot",
    )
    step.expected_stdout_markers = ["OKAY", "finished"]
    plan.add_step(step)
    return plan


def test_verification_success() -> None:
    plan = _plan_with_markers()
    results = [
        ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            returncode=0,
            stdout="OKAY\nfinished. total time: 0.5s\n",
        )
    ]
    report = VerificationEngine().verify_steps(plan, results)
    assert report.status == VerificationStatus.SUCCESS
    assert report.steps[0].markers_matched == ["OKAY", "finished"]


def test_verification_missing_markers_are_notes() -> None:
    plan = _plan_with_markers()
    results = [
        ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            returncode=0,
            stdout="something else",
        )
    ]
    report = VerificationEngine().verify_steps(plan, results)
    assert report.status == VerificationStatus.SUCCESS
    assert report.steps[0].markers_missing == ["OKAY", "finished"]


def test_verification_failed_step() -> None:
    plan = _plan_with_markers()
    results = [
        ExecutionResult(
            status=ExecutionStatus.FAILED,
            returncode=1,
            stdout="",
            stderr="fail",
        )
    ]
    report = VerificationEngine().verify_steps(plan, results)
    assert report.status == VerificationStatus.FAILED


def test_verification_timeout_step() -> None:
    plan = _plan_with_markers()
    results = [
        ExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            returncode=None,
            timed_out=True,
        )
    ]
    report = VerificationEngine().verify_steps(plan, results)
    assert report.status == VerificationStatus.FAILED
    assert any("timed out" in w.lower() for w in report.warnings)


def test_verification_cancelled_step() -> None:
    plan = _plan_with_markers()
    results = [
        ExecutionResult(
            status=ExecutionStatus.CANCELLED,
            returncode=None,
            cancelled=True,
        )
    ]
    report = VerificationEngine().verify_steps(plan, results)
    assert report.status == VerificationStatus.FAILED
    assert any("cancelled" in w.lower() for w in report.warnings)


def test_verification_no_steps() -> None:
    plan = FlashPlan(plan_id="empty")
    report = VerificationEngine().verify_steps(plan, [])
    assert report.status == VerificationStatus.UNKNOWN


def test_verification_mismatched_counts() -> None:
    plan = _plan_with_markers()
    results: list[ExecutionResult] = []
    report = VerificationEngine().verify_steps(plan, results)
    assert any("count" in w.lower() for w in report.warnings)


def test_verification_final_state_partial() -> None:
    plan = _plan_with_markers()
    results = [
        ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            returncode=0,
            stdout="OKAY\nfinished\n",
        )
    ]
    report = VerificationEngine().verify_steps(plan, results)
    report = VerificationEngine().add_final_device_state(report)
    assert report.status == VerificationStatus.PARTIAL
