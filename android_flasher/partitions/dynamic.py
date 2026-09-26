"""Dynamic partition modeling.

Dynamic partitions are logical partitions managed by Android's dynamic
partition system (super partition). This module provides helpers to
reason about them without touching the device.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from android_flasher.partitions.mapping import PartitionMap, PartitionRecord


# Partitions that are normally dynamic-only when inside super.
DYNAMIC_ONLY_NAMES: tuple[str, ...] = (
    "system",
    "system_ext",
    "product",
    "vendor",
    "odm",
)


@dataclass
class DynamicPartitionModel:
    """Model describing dynamic partition support for a device or firmware."""

    supported: Optional[bool] = None
    super_present: Optional[bool] = None
    slot_aware: Optional[bool] = None
    logical_names: list[str] = field(default_factory=list)
    source: str = "inferred"
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_map(cls, pmap: PartitionMap) -> "DynamicPartitionModel":
        model = cls(source=pmap.source)
        model.super_present = pmap.has_super
        model.supported = pmap.has_super or pmap.has_dynamic or pmap.has_logical
        model.slot_aware = pmap.has_slots
        model.logical_names = [
            r.name for r in pmap.records.values() if r.logical or r.dynamic
        ]
        return model

    @classmethod
    def from_names(cls, names: Iterable[str], source: str = "inferred") -> "DynamicPartitionModel":
        model = cls(source=source)
        model.logical_names = [n for n in names if n in DYNAMIC_ONLY_NAMES]
        model.supported = bool(model.logical_names)
        return model

    def contains(self, name: str) -> bool:
        return name in self.logical_names

    def to_dict(self) -> dict:
        return {
            "supported": self.supported,
            "super_present": self.super_present,
            "slot_aware": self.slot_aware,
            "logical_names": list(self.logical_names),
            "source": self.source,
            "notes": list(self.notes),
        }
