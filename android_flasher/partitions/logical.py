"""Logical partition modeling.

Logical partitions live inside the ``super`` partition on modern Android
devices. They are addressed by name but stored inside a container.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from android_flasher.partitions.mapping import PartitionKind, PartitionRecord


LOGICAL_PARTITION_NAMES: tuple[str, ...] = (
    "system",
    "system_ext",
    "product",
    "vendor",
    "odm",
)


@dataclass
class LogicalPartitionSet:
    """A normalized view of logical partitions inside super."""

    names: list[str] = field(default_factory=list)
    source: str = "inferred"

    @classmethod
    def from_names(cls, names: Iterable[str], source: str = "inferred") -> "LogicalPartitionSet":
        return cls(names=list(names), source=source)

    def contains(self, name: str) -> bool:
        return name in self.names

    def to_records(self) -> list[PartitionRecord]:
        return [
            PartitionRecord(
                name=name,
                kind=PartitionKind.LOGICAL,
                logical=True,
                dynamic=True,
                source=self.source,
            )
            for name in self.names
        ]

    def to_dict(self) -> dict:
        return {
            "names": list(self.names),
            "source": self.source,
        }
