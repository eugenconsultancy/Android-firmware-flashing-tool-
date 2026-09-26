"""Command builder.

Converts structured operations into concrete command specifications
(argv lists). The GUI and planner never construct raw fastboot or adb
commands directly.

Every command is produced as a list of strings — never a shell string.
``shell=False`` is enforced by the executor, not here, but the builder
must never produce a single string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from android_flasher.core.flash_plan import (
    FastbootMode,
    FlashOperation,
    FlashOperationKind,
    FlashPlan,
    FlashStep,
    FlashStepKind,
    SlotStrategy,
)
from android_flasher.logging.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# CommandSpec
# ---------------------------------------------------------------------------

@dataclass
class CommandSpec:
    """An executable command with its transport and timeout."""

    argv: list[str]
    transport: str  # "fastboot" | "adb"
    description: str = ""
    timeout_seconds: Optional[int] = None
    destructive: bool = False
    requires_fastbootd: bool = False
    expected_returncode: int = 0
    expected_stdout_markers: list[str] = field(default_factory=list)

    def as_display(self) -> str:
        """Render for UI display. Never used for execution."""
        return " ".join(self.argv)

    def to_dict(self) -> dict:
        return {
            "argv": list(self.argv),
            "transport": self.transport,
            "description": self.description,
            "timeout_seconds": self.timeout_seconds,
            "destructive": self.destructive,
            "requires_fastbootd": self.requires_fastbootd,
            "expected_returncode": self.expected_returncode,
            "expected_stdout_markers": list(self.expected_stdout_markers),
        }


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class CommandBuilder:
    """Builds ``CommandSpec`` objects from structured operations."""

    def __init__(
        self,
        fastboot_path: Path,
        adb_path: Optional[Path] = None,
    ) -> None:
        self._fastboot_path = Path(fastboot_path)
        self._adb_path = Path(adb_path) if adb_path else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_for_plan(
        self,
        plan: FlashPlan,
        timeout_default: int = 900,
    ) -> list[CommandSpec]:
        """Build command specs for every step in a plan.

        The result is parallel to ``plan.steps``; ``step.command`` is
        also populated in place so the UI can display it.
        """
        specs: list[CommandSpec] = []
        for step in plan.steps:
            spec = self.build_for_step(step, timeout_default=timeout_default)
            step.command = list(spec.argv)
            specs.append(spec)
        return specs

    def build_for_step(
        self,
        step: FlashStep,
        timeout_default: int = 900,
    ) -> CommandSpec:
        """Build a single ``CommandSpec`` from a step."""
        timeout = step.timeout_seconds or timeout_default
        op = step.operation

        if step.kind == FlashStepKind.REBOOT:
            return self._build_reboot(op, timeout, step.description)
        if step.kind == FlashStepKind.SET_ACTIVE:
            return self._build_set_active(op, timeout, step.description)
        if step.kind in (FlashStepKind.FLASH,):
            return self._build_flash(op, timeout, step.description)
        if step.kind in (FlashStepKind.UPDATE,):
            return self._build_update(op, timeout, step.description)
        if step.kind == FlashStepKind.VERIFY:
            return self._build_verify(op, timeout, step.description)
        if step.kind == FlashStepKind.WIPE:
            return self._build_wipe(op, timeout, step.description)
        if step.kind == FlashStepKind.PREPARE:
            return self._build_prepare(op, timeout, step.description)
        if step.kind == FlashStepKind.NOTE:
            return CommandSpec(
                argv=[],
                transport="none",
                description=step.description or "note",
                timeout_seconds=timeout,
            )

        raise ValueError(f"Unsupported step kind: {step.kind}")

    # ------------------------------------------------------------------
    # Kind-specific builders
    # ------------------------------------------------------------------

    def _build_prepare(
        self,
        op: FlashOperation,
        timeout: int,
        description: str,
    ) -> CommandSpec:
        # Preparation steps are advisory; the executor treats empty argv
        # as a no-op.
        if op.kind == FlashOperationKind.REBOOT_FASTBOOTD:
            return CommandSpec(
                argv=[str(self._fastboot_path), "reboot", "fastboot"],
                transport="fastboot",
                description=description or "reboot into fastbootd",
                timeout_seconds=timeout,
            )
        if op.kind == FlashOperationKind.REBOOT_BOOTLOADER:
            return CommandSpec(
                argv=[str(self._fastboot_path), "reboot", "bootloader"],
                transport="fastboot",
                description=description or "reboot into bootloader",
                timeout_seconds=timeout,
            )
        return CommandSpec(
            argv=[],
            transport="none",
            description=description or "prepare",
            timeout_seconds=timeout,
        )

    def _build_flash(
        self,
        op: FlashOperation,
        timeout: int,
        description: str,
    ) -> CommandSpec:
        if not op.partition:
            raise ValueError("flash operation requires a partition")
        if not op.image_path:
            raise ValueError("flash operation requires an image_path")

        partition = op.partition
        if op.slot_suffix:
            partition = f"{partition}{op.slot_suffix}"

        argv: list[str] = [str(self._fastboot_path), "flash"]
        if op.avb_disable:
            argv.extend(["--disable-verity", "--disable-verification"])
        argv.append(partition)
        argv.append(str(op.image_path))

        return CommandSpec(
            argv=argv,
            transport="fastboot",
            description=description or f"flash {partition}",
            timeout_seconds=timeout,
            destructive=True,
            requires_fastbootd=op.requires_fastbootd,
        )

    def _build_update(
        self,
        op: FlashOperation,
        timeout: int,
        description: str,
    ) -> CommandSpec:
        if not op.package_path:
            raise ValueError("update operation requires a package_path")

        argv: list[str] = [
            str(self._fastboot_path),
            "update",
            str(op.package_path),
        ]
        return CommandSpec(
            argv=argv,
            transport="fastboot",
            description=description or "update package",
            timeout_seconds=timeout,
            destructive=True,
            requires_fastbootd=op.requires_fastbootd,
        )

    def _build_set_active(
        self,
        op: FlashOperation,
        timeout: int,
        description: str,
    ) -> CommandSpec:
        if not op.slot_suffix:
            raise ValueError("set_active operation requires slot_suffix")
        slot = op.slot_suffix.lstrip("_")
        argv = [str(self._fastboot_path), "set_active", slot]
        return CommandSpec(
            argv=argv,
            transport="fastboot",
            description=description or f"set_active {slot}",
            timeout_seconds=timeout,
            destructive=True,
        )

    def _build_reboot(
        self,
        op: FlashOperation,
        timeout: int,
        description: str,
    ) -> CommandSpec:
        if op.kind == FlashOperationKind.REBOOT_BOOTLOADER:
            argv = [str(self._fastboot_path), "reboot", "bootloader"]
            label = description or "reboot bootloader"
        elif op.kind == FlashOperationKind.REBOOT_FASTBOOTD:
            argv = [str(self._fastboot_path), "reboot", "fastboot"]
            label = description or "reboot fastbootd"
        elif op.kind == FlashOperationKind.REBOOT_SYSTEM:
            argv = [str(self._fastboot_path), "reboot"]
            label = description or "reboot system"
        else:
            argv = [str(self._fastboot_path), "reboot"]
            label = description or "reboot"
        return CommandSpec(
            argv=argv,
            transport="fastboot",
            description=label,
            timeout_seconds=timeout,
        )

    def _build_verify(
        self,
        op: FlashOperation,
        timeout: int,
        description: str,
    ) -> CommandSpec:
        # Verification generally has no fastboot command; it is handled
        # by VerificationEngine reading device state. However a getvar
        # confirmation step can be represented.
        if op.partition:
            argv = [str(self._fastboot_path), "getvar", "current-slot"]
            return CommandSpec(
                argv=argv,
                transport="fastboot",
                description=description or "verify current-slot",
                timeout_seconds=timeout,
            )
        return CommandSpec(
            argv=[],
            transport="none",
            description=description or "verify",
            timeout_seconds=timeout,
        )

    def _build_wipe(
        self,
        op: FlashOperation,
        timeout: int,
        description: str,
    ) -> CommandSpec:
        # Wipe is modelled as `fastboot -w`; this is destructive and
        # extremely high risk. It is never added automatically.
        argv = [str(self._fastboot_path), "-w"]
        return CommandSpec(
            argv=argv,
            transport="fastboot",
            description=description or "wipe userdata",
            timeout_seconds=timeout,
            destructive=True,
        )

    # ------------------------------------------------------------------
    # Convenience builders for the UI
    # ------------------------------------------------------------------

    def build_getvar(self, name: str, timeout: int = 30) -> CommandSpec:
        return CommandSpec(
            argv=[str(self._fastboot_path), "getvar", name],
            transport="fastboot",
            description=f"getvar {name}",
            timeout_seconds=timeout,
        )

    def build_list_devices(self, timeout: int = 30) -> CommandSpec:
        return CommandSpec(
            argv=[str(self._fastboot_path), "devices"],
            transport="fastboot",
            description="fastboot devices",
            timeout_seconds=timeout,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slot_aware_partition(partition: str, slot_suffix: Optional[str]) -> str:
    """Return a partition name with a slot suffix appended when present."""
    if not slot_suffix:
        return partition
    if partition.endswith(slot_suffix):
        return partition
    return f"{partition}{slot_suffix}"
