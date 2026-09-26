"""Normalized partition records and mappings."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PartitionKind(str, Enum):
    """Normalized partition kind."""

    PHYSICAL = "physical"
    LOGICAL = "logical"
    DYNAMIC = "dynamic"
    SLOT_AWARE = "slot_aware"
    UNKNOWN = "unknown"


@dataclass
class PartitionRecord:
    """A single partition as modeled by the application."""

    name: str
    kind: PartitionKind = PartitionKind.UNKNOWN
    slot_suffix: Optional[str] = None
    size_bytes: Optional[int] = None
    source: str = "unknown"  # "device" | "firmware" | "profile" | "inferred"
    dynamic: bool = False
    logical: bool = False
    slot_aware: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "slot_suffix": self.slot_suffix,
            "size_bytes": self.size_bytes,
            "source": self.source,
            "dynamic": self.dynamic,
            "logical": self.logical,
            "slot_aware": self.slot_aware,
            "notes": list(self.notes),
        }


@dataclass
class PartitionMap:
    """Aggregate partition model for a device or firmware."""

    source: str = "unknown"  # "device" | "firmware" | "profile" | "merged"
    records: dict[str, PartitionRecord] = field(default_factory=dict)

    # Flags inferred from the map.
    has_super: bool = False
    has_slots: bool = False
    has_dynamic: bool = False
    has_logical: bool = False

    def add(self, record: PartitionRecord) -> None:
        self.records[record.name] = record
        self._recompute_flags()

    def get(self, name: str) -> Optional[PartitionRecord]:
        return self.records.get(name)

    def names(self) -> list[str]:
        return list(self.records.keys())

    def _recompute_flags(self) -> None:
        self.has_super = "super" in self.records
        self.has_slots = any(r.slot_aware for r in self.records.values())
        self.has_dynamic = any(r.dynamic for r in self.records.values())
        self.has_logical = any(r.logical for r in self.records.values())

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "records": [r.to_dict() for r in self.records.values()],
            "has_super": self.has_super,
            "has_slots": self.has_slots,
            "has_dynamic": self.has_dynamic,
            "has_logical": self.has_logical,
        }
