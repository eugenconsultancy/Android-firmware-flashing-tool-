"""Flash planner.

Turns device + firmware + compatibility + partition analysis into a
concrete ``FlashPlan``.

The planner is deterministic and side-effect free. It never touches
the device. It never invokes subprocesses.

Compatibility disposition:

    CONFIRMED  -> accepted, no warning
    LIKELY     -> warning, elevated confirmation
    UNKNOWN    -> warning + elevated confirmation when
                  ``allow_unknown_compatibility`` is true; blocker
                  otherwise
    MISMATCH   -> blocker
    BLOCKED    -> blocker

The compatibility check is performed inside ``_collect_blockers`` so
that a missing compatibility result still blocks the plan before any
operation is added.
"""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from android_flasher.config.settings import Settings
from android_flasher.core.flash_plan import (
    FastbootMode,
    FlashOperation,
    FlashOperationKind,
    FlashPlan,
    FlashPlanStatus,
    FlashStep,
    FlashStepKind,
    SlotStrategy,
)
from android_flasher.devices.bootloader import BootloaderInfo
from android_flasher.devices.detection import DetectionResult
from android_flasher.devices.identification import DeviceIdentity
from android_flasher.devices.slots import SlotInfo
from android_flasher.firmware.compatibility import (
    CompatibilityResult,
    CompatibilityStatus,
)
from android_flasher.firmware.detector import FirmwareType
from android_flasher.firmware.metadata import ImageType
from android_flasher.firmware.package import FirmwarePackage
from android_flasher.logging.logger import get_logger
from android_flasher.partitions.manager import PartitionAnalysis


log = get_logger(__name__)


_LOGICAL_PARTITIONS = {
    "system", "system_ext", "product", "vendor", "odm",
}


class FlashPlanner:
    """Builds a ``FlashPlan`` from high-level inputs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def plan(
        self,
        *,
        device: Optional[DeviceIdentity],
        firmware: Optional[FirmwarePackage],
        compatibility: Optional[CompatibilityResult],
        partition_analysis: Optional[PartitionAnalysis],
        detection: Optional[DetectionResult] = None,
        bootloader_info: Optional[BootloaderInfo] = None,
        slot_info: Optional[SlotInfo] = None,
    ) -> FlashPlan:
        plan = FlashPlan(plan_id=str(uuid4()))
        plan.status = FlashPlanStatus.DRAFT

        if device is not None:
            plan.device_serial = device.serial
            plan.device_codename = device.device_codename
            plan.device_transport = device.transport
        if firmware is not None:
            plan.firmware_path = str(firmware.path)
            plan.firmware_type = (
                firmware.metadata.package_type
                or firmware.detection.firmware_type.value
            )
            plan.firmware_sha256 = firmware.metadata.source_sha256

        plan.fastboot_mode = self._detect_fastboot_mode(device, detection)
        self._decide_slot_strategy(plan, device, slot_info)

        # Compatibility is checked inside _collect_blockers so it runs
        # before any early return.
        self._collect_blockers(
            plan=plan,
            device=device,
            firmware=firmware,
            compatibility=compatibility,
            bootloader_info=bootloader_info,
        )

        if plan.is_blocked():
            plan.status = FlashPlanStatus.BLOCKED
            return plan

        if firmware is None:
            plan.add_blocker("No firmware selected.")
            plan.status = FlashPlanStatus.BLOCKED
            return plan

        fw_type = self._resolve_firmware_type(firmware)

        if fw_type in (FirmwareType.RAW_IMAGE, FirmwareType.SPARSE_IMAGE):
            self._plan_raw_image(plan, firmware, partition_analysis)
        elif fw_type == FirmwareType.SUPER_IMAGE:
            self._plan_super_image(plan, firmware)
        elif fw_type == FirmwareType.FACTORY_ZIP:
            self._plan_factory_zip(plan, firmware, partition_analysis)
        elif fw_type == FirmwareType.OTA_ZIP:
            self._plan_ota_zip(plan, firmware, device)
        elif fw_type == FirmwareType.PAYLOAD_BIN:
            plan.add_blocker(
                "Payload-only firmware cannot be flashed directly. "
                "Present the full OTA ZIP instead."
            )
        else:
            plan.add_blocker(f"Unsupported firmware type: {fw_type}")

        self._apply_slot_suffix(plan)
        self._insert_preparation_steps(plan, device)
        self._set_confirmation_level(plan, compatibility)

        if plan.is_blocked():
            plan.status = FlashPlanStatus.BLOCKED
        elif plan.confirmation_required == "NONE":
            plan.status = FlashPlanStatus.READY
        else:
            plan.status = FlashPlanStatus.REQUIRES_CONFIRMATION

        plan.verify_after_each_step = self._settings.flash.verify_after_each_step
        plan.verify_after_operation = self._settings.flash.verify_after_operation
        plan.reboot_after_flash = self._settings.flash.reboot_after_flash

        log.info("built plan %s", plan.summary())
        return plan

    # ------------------------------------------------------------------
    # Firmware type resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_firmware_type(firmware: FirmwarePackage) -> FirmwareType:
        try:
            return firmware.detection.firmware_type
        except Exception:
            value = (firmware.metadata.package_type or "").lower()
            for candidate in FirmwareType:
                if candidate.value == value:
                    return candidate
            return FirmwareType.UNKNOWN

    # ------------------------------------------------------------------
    # Planning per firmware type
    # ------------------------------------------------------------------

    def _plan_raw_image(self, plan, firmware, analysis) -> None:
        if not firmware.metadata.images:
            plan.add_blocker("Raw image package has no images.")
            return
        image = firmware.metadata.images[0]
        partition = image.partition or self._guess_partition(image)
        if not partition:
            plan.add_blocker("Cannot determine which partition this raw image targets.")
            return
        op = FlashOperation(
            kind=FlashOperationKind.FLASH_IMAGE,
            partition=partition,
            image_path=str(firmware.path),
            slot_strategy=SlotStrategy.NONE,
            destructive=True,
            reason=f"flash {image.image_type} to {partition}",
        )
        plan.add_operation(op)
        plan.add_step(FlashStep(
            index=0,
            kind=FlashStepKind.FLASH,
            operation=op,
            description=f"flash {partition}",
            timeout_seconds=self._settings.flash.step_timeout_seconds,
        ))
        plan.add_requirement(f"Partition '{partition}' must exist on the device.")

    def _plan_super_image(self, plan, firmware) -> None:
        op = FlashOperation(
            kind=FlashOperationKind.FLASH_IMAGE,
            partition="super",
            image_path=str(firmware.path),
            destructive=True,
            reason="flash super image",
        )
        plan.add_operation(op)
        plan.add_step(FlashStep(
            index=0,
            kind=FlashStepKind.FLASH,
            operation=op,
            description="flash super",
            timeout_seconds=self._settings.flash.step_timeout_seconds,
        ))

    def _plan_factory_zip(self, plan, firmware, analysis) -> None:
        if self._settings.flash.allow_extraction_for_factory_zip:
            self._plan_factory_zip_with_extraction(plan, firmware, analysis)
        else:
            self._plan_factory_zip_via_update(plan, firmware)

    def _plan_factory_zip_via_update(self, plan, firmware) -> None:
        if not self._settings.flash.allow_fastboot_update:
            plan.add_blocker(
                "Factory ZIP requires extraction or fastboot update; "
                "both are disabled by settings."
            )
            return
        op = FlashOperation(
            kind=FlashOperationKind.UPDATE_PACKAGE,
            package_path=str(firmware.path),
            destructive=True,
            reason="factory zip update",
        )
        plan.add_operation(op)
        plan.add_step(FlashStep(
            index=0,
            kind=FlashStepKind.UPDATE,
            operation=op,
            description="update factory package",
            timeout_seconds=self._settings.flash.step_timeout_seconds,
        ))
        plan.add_warning(
            "Factory ZIP is being applied via `fastboot update`. "
            "This relies on the package's own flash script."
        )

    def _plan_factory_zip_with_extraction(self, plan, firmware, analysis) -> None:
        images = firmware.metadata.images
        if not images:
            plan.add_blocker("Factory ZIP contains no images we can target.")
            return
        for image in images:
            partition = image.partition or self._guess_partition(image)
            if not partition:
                continue
            op = FlashOperation(
                kind=FlashOperationKind.FLASH_IMAGE,
                partition=partition,
                image_internal_path=image.internal_path or image.name,
                destructive=True,
                reason=f"flash {partition} from factory zip",
            )
            plan.add_operation(op)
            plan.add_step(FlashStep(
                index=0,
                kind=FlashStepKind.FLASH,
                operation=op,
                description=f"flash {partition}",
                timeout_seconds=self._settings.flash.step_timeout_seconds,
            ))
        plan.add_blocker(
            "Factory ZIP extraction-based flashing is not implemented in Phase 4."
        )

    def _plan_ota_zip(self, plan, firmware, device) -> None:
        if not self._settings.flash.allow_fastboot_update:
            plan.add_blocker("OTA ZIP requires `fastboot update`; disabled by settings.")
            return
        caps = getattr(device, "capabilities", None)
        if caps is not None and getattr(caps, "supports_update", None) is False:
            plan.add_blocker("Device reports no support for `fastboot update`.")
            return
        op = FlashOperation(
            kind=FlashOperationKind.UPDATE_PACKAGE,
            package_path=str(firmware.path),
            destructive=True,
            reason="OTA update",
        )
        plan.add_operation(op)
        plan.add_step(FlashStep(
            index=0,
            kind=FlashStepKind.UPDATE,
            operation=op,
            description="update OTA package",
            timeout_seconds=self._settings.flash.step_timeout_seconds,
        ))
        plan.add_warning(
            "OTA packages may require a specific fastboot version and "
            "sideload mechanism. Verify the device accepts `fastboot update`."
        )

    # ------------------------------------------------------------------
    # Slot handling
    # ------------------------------------------------------------------

    def _decide_slot_strategy(self, plan, device, slot_info) -> None:
        if device is None or not device.slot_support:
            plan.slot_strategy = SlotStrategy.NONE
            return
        current_slot = None
        if slot_info is not None:
            current_slot = slot_info.current_slot or slot_info.slot_suffix
        if not current_slot:
            current_slot = getattr(device, "current_slot", None)
        plan.current_slot = current_slot
        plan.slot_strategy = SlotStrategy.CURRENT
        plan.target_slot = current_slot

    def _apply_slot_suffix(self, plan) -> None:
        if plan.slot_strategy != SlotStrategy.CURRENT:
            return
        if not plan.current_slot:
            return
        suffix = (
            plan.current_slot
            if plan.current_slot.startswith("_")
            else f"_{plan.current_slot}"
        )
        for op in plan.operations:
            if op.kind == FlashOperationKind.FLASH_IMAGE and op.partition:
                if op.partition.lower() in _LOGICAL_PARTITIONS:
                    continue
                if op.partition.lower() in ("super", "userdata"):
                    continue
                op.slot_suffix = suffix

    def _insert_preparation_steps(self, plan, device) -> None:
        needs_fastbootd = any(
            op.requires_fastbootd or op.partition in _LOGICAL_PARTITIONS
            for op in plan.operations
            if op.kind == FlashOperationKind.FLASH_IMAGE
        )
        if not needs_fastbootd:
            return
        if not self._settings.safety.allow_fastbootd_mode_switch:
            plan.add_blocker(
                "Operations require fastbootd but mode switching is disabled."
            )
            return
        caps = getattr(device, "capabilities", None)
        if caps is not None and getattr(caps, "supports_fastbootd", None) is False:
            plan.add_blocker(
                "Operations require fastbootd but device reports no support."
            )
            return
        for op in plan.operations:
            if op.partition in _LOGICAL_PARTITIONS:
                op.requires_fastbootd = True
        prep = FlashOperation(
            kind=FlashOperationKind.REBOOT_FASTBOOTD,
            destructive=False,
            reason="enter fastbootd for logical partition flashing",
        )
        prep_step = FlashStep(
            index=0,
            kind=FlashStepKind.PREPARE,
            operation=prep,
            description="reboot into fastbootd",
            timeout_seconds=self._settings.timeouts.reboot,
        )
        plan.steps.insert(0, prep_step)
        for i, step in enumerate(plan.steps):
            step.index = i
        plan.fastboot_mode = FastbootMode.FASTBOOTD

    # ------------------------------------------------------------------
    # Compatibility (called from _collect_blockers)
    # ------------------------------------------------------------------

    def _apply_compatibility(self, plan, compatibility) -> None:
        """Apply compatibility disposition to the plan.

        Blocker and warning messages always contain the lowercase word
        ``compatibility`` so downstream consumers can rely on it.
        """
        if compatibility is None:
            plan.add_blocker(
                "compatibility has not been evaluated; "
                "run compatibility analysis before planning."
            )
            return
        status = compatibility.status
        if status == CompatibilityStatus.MISMATCH:
            plan.add_blocker(
                "compatibility mismatch: the firmware does not target this device."
            )
        elif status == CompatibilityStatus.BLOCKED:
            plan.add_blocker(
                "compatibility blocked by the compatibility engine."
            )
        elif status == CompatibilityStatus.UNKNOWN:
            if not self._settings.safety.allow_unknown_compatibility:
                plan.add_blocker(
                    "compatibility is UNKNOWN and settings require explicit "
                    "opt-in for unknown compatibility."
                )
            else:
                plan.add_warning(
                    "compatibility is UNKNOWN; elevated confirmation required."
                )
        elif status == CompatibilityStatus.LIKELY:
            if not self._settings.safety.allow_likely_compatibility:
                plan.add_blocker(
                    "compatibility is LIKELY but settings do not permit "
                    "likely compatibility."
                )
            else:
                plan.add_warning("compatibility is LIKELY (not confirmed).")

    # ------------------------------------------------------------------
    # Confirmation level
    # ------------------------------------------------------------------

    def _set_confirmation_level(self, plan, compatibility) -> None:
        if plan.is_blocked():
            plan.confirmation_required = "BLOCKED"
            return
        if not self._settings.safety.require_confirmation:
            plan.confirmation_required = "NONE"
            return
        if not plan.has_destructive_operations():
            plan.confirmation_required = "NONE"
            return
        elevated = False
        if any(op.avb_disable for op in plan.operations):
            elevated = True
        if plan.slot_strategy in (
            SlotStrategy.OTHER, SlotStrategy.BOTH, SlotStrategy.EXPLICIT,
        ):
            elevated = True
        if compatibility is not None and compatibility.status == CompatibilityStatus.UNKNOWN:
            elevated = True
        if compatibility is not None and compatibility.status == CompatibilityStatus.LIKELY:
            elevated = True
        plan.confirmation_required = "ELEVATED" if elevated else "STANDARD"

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    def _detect_fastboot_mode(self, device, detection) -> FastbootMode:
        if detection is not None:
            state = getattr(detection, "state", None)
            value = getattr(state, "value", None) or str(state)
            if value == "fastboot_device":
                return FastbootMode.BOOTLOADER
            if value == "fastbootd_device":
                return FastbootMode.FASTBOOTD
        if device is not None:
            if device.transport == "fastbootd":
                return FastbootMode.FASTBOOTD
            if device.transport == "fastboot":
                return FastbootMode.BOOTLOADER
        return FastbootMode.UNKNOWN

    @staticmethod
    def _guess_partition(image):
        if image.partition:
            return image.partition
        if image.image_type and image.image_type != ImageType.OTHER:
            return image.image_type
        return None

    # ------------------------------------------------------------------
    # Blocker collection (compatibility included)
    # ------------------------------------------------------------------

    def _collect_blockers(
        self, *, plan, device, firmware, compatibility, bootloader_info,
    ) -> None:
        if device is None:
            plan.add_blocker("No device is identified.")
        if firmware is None:
            plan.add_blocker("No firmware is selected.")

        if bootloader_info is not None:
            state = getattr(bootloader_info.state, "value", None) or str(
                bootloader_info.state
            )
            if state == "locked":
                plan.add_blocker("Bootloader is locked.")
        elif device is not None:
            lock = getattr(device, "bootloader_state", None)
            lock_value = getattr(lock, "value", None) if lock is not None else None
            if lock_value == "locked":
                plan.add_blocker("Bootloader is locked.")

        if not self._settings.safety.allow_flash:
            plan.add_blocker("Flashing is not enabled in safety settings.")
        if self._settings.safety.phase1_read_only:
            plan.add_blocker("Application is in read-only mode.")

        # Compatibility is checked here so it applies before any early
        # return in plan(). This guarantees a compatibility blocker is
        # present whenever compatibility is missing or in a blocking
        # state.
        self._apply_compatibility(plan, compatibility)
