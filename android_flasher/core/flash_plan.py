"""Flash plan model.

A flash plan is the immutable, pre-flight description of what the
application intends to do. It is generated *before* any execution
happens and is the single source of truth for:

    - command generation
    - safety validation
    - risk classification
    - user confirmation
    - execution
    - verification

Plans are never executed directly. ``FlashEngine`` consumes a plan and
produces an execution trace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FlashPlanStatus(str, Enum):
    """High-level disposition of a plan before execution."""

    DRAFT = "DRAFT"
    READY = "READY"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class FlashOperationKind(str, Enum):
    """Logical kind of operation the plan performs."""

    FLASH_IMAGE = "flash_image"
    UPDATE_PACKAGE = "update_package"
    SET_ACTIVE_SLOT = "set_active_slot"
    REBOOT_BOOTLOADER = "reboot_bootloader"
    REBOOT_FASTBOOTD = "reboot_fastbootd"
    REBOOT_SYSTEM = "reboot_system"
    ERASE_PARTITION = "erase_partition"
    FORMAT_PARTITION = "format_partition"
    NO_OP = "no_op"


class FlashStepKind(str, Enum):
    """Kind of a single step inside a plan."""

    PREPARE = "prepare"
    FLASH = "flash"
    UPDATE = "update"
    SET_ACTIVE = "set_active"
    REBOOT = "reboot"
    VERIFY = "verify"
    WIPE = "wipe"
    NOTE = "note"


class SlotStrategy(str, Enum):
    """How the plan selects a slot for A/B devices."""

    NONE = "none"                # device has no slots
    CURRENT = "current"
    OTHER = "other"
    BOTH = "both"
    EXPLICIT = "explicit"        # caller provided a slot suffix
    FIRMWARE_DECIDES = "firmware_decides"


class FastbootMode(str, Enum):
    """Which fastboot variant the device is currently in."""

    BOOTLOADER = "bootloader"
    FASTBOOTD = "fastbootd"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Operation
# ---------------------------------------------------------------------------

@dataclass
class FlashOperation:
    """A single logical operation that a plan performs.

    Every destructive intent lives here. ``CommandBuilder`` turns an
    operation into a ``CommandSpec`` (argv list). ``RiskAssessor``
    classifies the operation.
    """

    kind: FlashOperationKind
    partition: Optional[str] = None
    image_path: Optional[str] = None
    image_internal_path: Optional[str] = None
    package_path: Optional[str] = None
    slot_suffix: Optional[str] = None
    slot_strategy: SlotStrategy = SlotStrategy.NONE
    avb_disable: bool = False
    requires_fastbootd: bool = False
    destructive: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "partition": self.partition,
            "image_path": self.image_path,
            "image_internal_path": self.image_internal_path,
            "package_path": self.package_path,
            "slot_suffix": self.slot_suffix,
            "slot_strategy": self.slot_strategy.value,
            "avb_disable": self.avb_disable,
            "requires_fastbootd": self.requires_fastbootd,
            "destructive": self.destructive,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------

@dataclass
class FlashStep:
    """A single executable step inside a plan.

    A step references a ``CommandSpec`` (argv) but does not embed the
    stringified command; ``CommandBuilder`` fills it in.
    """

    index: int
    kind: FlashStepKind
    operation: FlashOperation
    description: str
    command: Optional[list[str]] = None
    timeout_seconds: Optional[int] = None
    expected_returncode: int = 0
    expected_stdout_markers: list[str] = field(default_factory=list)
    optional: bool = False

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "kind": self.kind.value,
            "operation": self.operation.to_dict(),
            "description": self.description,
            "command": list(self.command) if self.command else None,
            "timeout_seconds": self.timeout_seconds,
            "expected_returncode": self.expected_returncode,
            "expected_stdout_markers": list(self.expected_stdout_markers),
            "optional": self.optional,
        }


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

@dataclass
class FlashPlan:
    """A complete plan for a firmware installation or single operation."""

    plan_id: str
    status: FlashPlanStatus = FlashPlanStatus.DRAFT

    # Target.
    device_serial: Optional[str] = None
    device_codename: Optional[str] = None
    device_transport: Optional[str] = None
    fastboot_mode: FastbootMode = FastbootMode.UNKNOWN

    # Firmware.
    firmware_path: Optional[str] = None
    firmware_type: Optional[str] = None
    firmware_sha256: Optional[str] = None

    # Slot handling.
    slot_strategy: SlotStrategy = SlotStrategy.NONE
    current_slot: Optional[str] = None
    target_slot: Optional[str] = None

    # Operations and steps.
    operations: list[FlashOperation] = field(default_factory=list)
    steps: list[FlashStep] = field(default_factory=list)

    # Safety and diagnostics.
    requirements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    risk_level: str = "UNKNOWN"
    risk_reasons: list[str] = field(default_factory=list)
    confirmation_required: str = "NONE"  # NONE | STANDARD | ELEVATED | BLOCKED

    # Verification.
    verify_after_each_step: bool = True
    verify_after_operation: bool = True
    reboot_after_flash: bool = False

    def add_operation(self, operation: FlashOperation) -> None:
        self.operations.append(operation)

    def add_step(self, step: FlashStep) -> None:
        step.index = len(self.steps)
        self.steps.append(step)

    def add_warning(self, message: str) -> None:
        if message and message not in self.warnings:
            self.warnings.append(message)

    def add_blocker(self, message: str) -> None:
        if message and message not in self.blockers:
            self.blockers.append(message)

    def add_requirement(self, message: str) -> None:
        if message and message not in self.requirements:
            self.requirements.append(message)

    def is_blocked(self) -> bool:
        return bool(self.blockers) or self.status == FlashPlanStatus.BLOCKED

    def has_destructive_operations(self) -> bool:
        return any(op.destructive for op in self.operations)

    def summary(self) -> str:
        return (
            f"plan={self.plan_id} status={self.status.value} "
            f"operations={len(self.operations)} steps={len(self.steps)} "
            f"risk={self.risk_level}"
        )

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "status": self.status.value,
            "device_serial": self.device_serial,
            "device_codename": self.device_codename,
            "device_transport": self.device_transport,
            "fastboot_mode": self.fastboot_mode.value,
            "firmware_path": self.firmware_path,
            "firmware_type": self.firmware_type,
            "firmware_sha256": self.firmware_sha256,
            "slot_strategy": self.slot_strategy.value,
            "current_slot": self.current_slot,
            "target_slot": self.target_slot,
            "operations": [op.to_dict() for op in self.operations],
            "steps": [step.to_dict() for step in self.steps],
            "requirements": list(self.requirements),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
            "risk_level": self.risk_level,
            "risk_reasons": list(self.risk_reasons),
            "confirmation_required": self.confirmation_required,
            "verify_after_each_step": self.verify_after_each_step,
            "verify_after_operation": self.verify_after_operation,
            "reboot_after_flash": self.reboot_after_flash,
        }
