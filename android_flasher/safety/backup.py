"""Backup abstraction.

Android partitions cannot be universally backed up over fastboot.
Attempting to present a fake backup workflow would be dangerous.

``BackupPlanner`` classifies each partition:

    SUPPORTED       - a realistic backup path exists
    NOT_APPLICABLE  - no backup needed / no meaningful data
    UNSUPPORTED     - no safe backup path exists with the current transport

The flasher must never claim a partition was backed up unless the
planner classifies it as SUPPORTED and a backup was actually produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from android_flasher.core.flash_plan import FlashOperationKind, FlashPlan
from android_flasher.logging.logger import get_logger
from android_flasher.partitions.mapping import PartitionKind, PartitionMap

log = get_logger(__name__)


class BackupSupport(str, Enum):
    SUPPORTED = "SUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


@dataclass
class BackupPlan:
    """A plan describing what can or cannot be backed up."""

    entries: dict[str, BackupSupport] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def add(self, partition: str, support: BackupSupport) -> None:
        self.entries[partition] = support

    def add_note(self, message: str) -> None:
        if message and message not in self.notes:
            self.notes.append(message)

    def unsupported(self) -> list[str]:
        return [k for k, v in self.entries.items() if v == BackupSupport.UNSUPPORTED]

    def supported(self) -> list[str]:
        return [k for k, v in self.entries.items() if v == BackupSupport.SUPPORTED]

    def to_dict(self) -> dict:
        return {
            "entries": {k: v.value for k, v in self.entries.items()},
            "notes": list(self.notes),
        }


class BackupPlanner:
    """Classifies backup support for each partition referenced by a plan."""

    def plan_for_plan(
        self,
        plan: FlashPlan,
        device_pmap: Optional[PartitionMap] = None,
    ) -> BackupPlan:
        backup = BackupPlan()

        if plan is None:
            backup.add_note("No plan provided.")
            return backup

        for op in plan.operations:
            if op.kind not in (
                FlashOperationKind.FLASH_IMAGE,
                FlashOperationKind.ERASE_PARTITION,
                FlashOperationKind.FORMAT_PARTITION,
            ):
                continue
            if not op.partition:
                continue

            record = None
            if device_pmap is not None:
                record = device_pmap.get(op.partition)

            support = self._classify(op.partition, record)
            backup.add(op.partition, support)

            if support == BackupSupport.UNSUPPORTED:
                backup.add_note(
                    f"Partition '{op.partition}' cannot be backed up safely "
                    f"with the current transport."
                )

        return backup

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _classify(partition: str, record) -> BackupSupport:
        partition_l = partition.lower()

        # Nothing meaningful to back up for userdata by default; a full
        # userdata backup is a user-driven file-level task, not a
        # fastboot operation.
        if partition_l == "userdata":
            return BackupSupport.UNSUPPORTED

        # Dynamic / logical partitions cannot be safely pulled over
        # fastboot in a universal way.
        if record is not None:
            kind = record.kind
            if kind in (
                PartitionKind.DYNAMIC,
                PartitionKind.LOGICAL,
            ):
                return BackupSupport.UNSUPPORTED
            if record.logical or record.dynamic:
                return BackupSupport.UNSUPPORTED
            if kind == PartitionKind.SLOT_AWARE:
                # Slot-aware physical partitions *may* be pullable but
                # fastboot does not guarantee a fetch implementation.
                return BackupSupport.NOT_APPLICABLE
            if kind == PartitionKind.PHYSICAL:
                return BackupSupport.NOT_APPLICABLE

        # Without a partition model we cannot claim support.
        return BackupSupport.UNKNOWN
