"""Partition discovery from device and firmware.

Discovery is read-only. It inspects:
    - fastboot getvar partition-type:* (best-effort)
    - fastboot getvar all (best-effort)
    - firmware metadata (image list)
    - device capabilities
    - profile-provided fallbacks

Discovery never assumes a partition exists simply because a profile
mentions it. Profiles provide *reference* data, not truth.
"""

from __future__ import annotations

from typing import Iterable, Optional

from android_flasher.devices.fastboot import FastbootClient
from android_flasher.devices.identification import DeviceIdentity
from android_flasher.firmware.metadata import FirmwareMetadata
from android_flasher.logging.logger import get_logger
from android_flasher.partitions.mapping import (
    PartitionKind,
    PartitionMap,
    PartitionRecord,
)

log = get_logger(__name__)


# Known partition names (reference list, not truth).
KNOWN_PARTITIONS: tuple[str, ...] = (
    "boot",
    "init_boot",
    "vendor_boot",
    "recovery",
    "system",
    "system_ext",
    "product",
    "vendor",
    "odm",
    "vbmeta",
    "vbmeta_system",
    "vbmeta_vendor",
    "dtbo",
    "super",
    "modem",
    "radio",
    "userdata",
)


class PartitionDiscovery:
    """Discovers partitions from a device and/or firmware."""

    def discover_from_device(
        self,
        identity: DeviceIdentity,
        fastboot_client: Optional[FastbootClient] = None,
    ) -> PartitionMap:
        """Build a PartitionMap from a device."""
        pmap = PartitionMap(source="device")

        if identity is None:
            return pmap

        slot_aware = bool(identity.slot_support)
        dynamic = bool(identity.capabilities.supports_dynamic_partitions)

        # Try fastboot getvar all to discover actual partitions.
        if fastboot_client is not None and identity.serial:
            try:
                variables = fastboot_client.getvar_all(serial=identity.serial)
                self._from_getvar_all(variables, pmap, slot_aware, dynamic)
            except Exception as exc:  # noqa: BLE001 - defensive
                log.warning("fastboot getvar all failed during discovery: %s", exc)

        # Augment from known list, marking source as "inferred".
        for name in KNOWN_PARTITIONS:
            if name in pmap.records:
                continue
            record = PartitionRecord(
                name=name,
                kind=_kind_for(name, slot_aware, dynamic),
                dynamic=dynamic and name in _DYNAMIC_NAMES,
                logical=dynamic and name in _DYNAMIC_NAMES,
                slot_aware=slot_aware and name not in _NON_SLOT_NAMES,
                source="inferred",
            )
            pmap.add(record)

        return pmap

    def discover_from_firmware(self, metadata: FirmwareMetadata) -> PartitionMap:
        """Build a PartitionMap from firmware metadata."""
        pmap = PartitionMap(source="firmware")

        if metadata is None:
            return pmap

        for entry in metadata.partitions:
            kind = PartitionKind.PHYSICAL
            if entry.logical:
                kind = PartitionKind.LOGICAL
            elif entry.dynamic:
                kind = PartitionKind.DYNAMIC
            elif entry.slot_aware:
                kind = PartitionKind.SLOT_AWARE

            record = PartitionRecord(
                name=entry.name,
                kind=kind,
                dynamic=entry.dynamic,
                logical=entry.logical,
                slot_aware=entry.slot_aware,
                source="firmware",
                notes=list(entry.notes),
            )
            pmap.add(record)

        if metadata.super_partition_present and "super" not in pmap.records:
            pmap.add(PartitionRecord(
                name="super",
                kind=PartitionKind.DYNAMIC,
                dynamic=True,
                source="firmware",
                notes=["super partition declared by firmware"],
            ))

        return pmap

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _from_getvar_all(
        variables: dict[str, str],
        pmap: PartitionMap,
        slot_aware: bool,
        dynamic: bool,
    ) -> None:
        for key, value in variables.items():
            key_l = key.lower()
            if not key_l.startswith("partition-type:"):
                continue
            name = key_l.split(":", 1)[1].strip()
            if not name:
                continue
            kind = _kind_for(name, slot_aware, dynamic)
            pmap.add(PartitionRecord(
                name=name,
                kind=kind,
                dynamic=dynamic and name in _DYNAMIC_NAMES,
                logical=dynamic and name in _DYNAMIC_NAMES,
                slot_aware=slot_aware and name not in _NON_SLOT_NAMES,
                source="device",
                notes=[f"getvar reported type: {value}"] if value else [],
            ))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DYNAMIC_NAMES = {"system", "system_ext", "product", "vendor", "odm"}
_NON_SLOT_NAMES = {"super", "userdata"}


def _kind_for(name: str, slot_aware: bool, dynamic: bool) -> PartitionKind:
    if name == "super":
        return PartitionKind.DYNAMIC
    if dynamic and name in _DYNAMIC_NAMES:
        return PartitionKind.LOGICAL
    if slot_aware and name not in _NON_SLOT_NAMES:
        return PartitionKind.SLOT_AWARE
    return PartitionKind.PHYSICAL


def iter_known_partitions() -> Iterable[str]:
    return iter(KNOWN_PARTITIONS)
