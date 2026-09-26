"""Tests for the command builder (Phase 3)."""

from __future__ import annotations

from pathlib import Path

from android_flasher.core.command_builder import (
    CommandBuilder,
    CommandSpec,
    slot_aware_partition,
)
from android_flasher.core.flash_plan import (
    FlashOperation,
    FlashOperationKind,
    FlashPlan,
    FlashStep,
    FlashStepKind,
    SlotStrategy,
)


def _builder() -> CommandBuilder:
    return CommandBuilder(Path("/opt/platform-tools/fastboot"))


def test_build_flash_command() -> None:
    builder = _builder()
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
    spec = builder.build_for_step(step)
    assert spec.argv[0].endswith("fastboot")
    assert spec.argv[1] == "flash"
    assert spec.argv[2] == "boot"
    assert spec.argv[3] == "/tmp/boot.img"
    assert spec.destructive is True


def test_build_flash_with_slot_suffix() -> None:
    builder = _builder()
    op = FlashOperation(
        kind=FlashOperationKind.FLASH_IMAGE,
        partition="boot",
        slot_suffix="_a",
        image_path="/tmp/boot.img",
    )
    step = FlashStep(
        index=0,
        kind=FlashStepKind.FLASH,
        operation=op,
        description="flash boot_a",
    )
    spec = builder.build_for_step(step)
    assert spec.argv[2] == "boot_a"


def test_build_flash_with_avb_disable() -> None:
    builder = _builder()
    op = FlashOperation(
        kind=FlashOperationKind.FLASH_IMAGE,
        partition="vbmeta",
        image_path="/tmp/vbmeta.img",
        avb_disable=True,
    )
    step = FlashStep(
        index=0,
        kind=FlashStepKind.FLASH,
        operation=op,
        description="flash vbmeta",
    )
    spec = builder.build_for_step(step)
    assert "--disable-verity" in spec.argv
    assert "--disable-verification" in spec.argv


def test_build_set_active() -> None:
    builder = _builder()
    op = FlashOperation(
        kind=FlashOperationKind.SET_ACTIVE_SLOT,
        slot_suffix="_b",
    )
    step = FlashStep(
        index=0,
        kind=FlashStepKind.SET_ACTIVE,
        operation=op,
        description="set_active b",
    )
    spec = builder.build_for_step(step)
    assert spec.argv[1] == "set_active"
    assert spec.argv[2] == "b"


def test_build_reboot() -> None:
    builder = _builder()
    op = FlashOperation(kind=FlashOperationKind.REBOOT_BOOTLOADER)
    step = FlashStep(
        index=0,
        kind=FlashStepKind.REBOOT,
        operation=op,
        description="reboot bootloader",
    )
    spec = builder.build_for_step(step)
    assert spec.argv[1:] == ["reboot", "bootloader"]


def test_build_update() -> None:
    builder = _builder()
    op = FlashOperation(
        kind=FlashOperationKind.UPDATE_PACKAGE,
        package_path="/tmp/ota.zip",
    )
    step = FlashStep(
        index=0,
        kind=FlashStepKind.UPDATE,
        operation=op,
        description="update",
    )
    spec = builder.build_for_step(step)
    assert spec.argv[1] == "update"
    assert spec.argv[2] == "/tmp/ota.zip"


def test_build_for_plan_populates_steps() -> None:
    builder = _builder()
    plan = FlashPlan(plan_id="test")
    op = FlashOperation(
        kind=FlashOperationKind.FLASH_IMAGE,
        partition="boot",
        image_path="/tmp/boot.img",
    )
    step = FlashStep(
        index=0,
        kind=FlashStepKind.FLASH,
        operation=op,
        description="flash",
    )
    plan.add_step(step)
    specs = builder.build_for_plan(plan)
    assert len(specs) == 1
    assert plan.steps[0].command is not None


def test_flash_without_partition_raises() -> None:
    builder = _builder()
    op = FlashOperation(kind=FlashOperationKind.FLASH_IMAGE, image_path="/tmp/x.img")
    step = FlashStep(
        index=0,
        kind=FlashStepKind.FLASH,
        operation=op,
        description="flash",
    )
    try:
        builder.build_for_step(step)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_slot_aware_partition_helper() -> None:
    assert slot_aware_partition("boot", "_a") == "boot_a"
    assert slot_aware_partition("boot_a", "_a") == "boot_a"
    assert slot_aware_partition("boot", None) == "boot"
