"""Confirmation model.

The UI presents a structured confirmation dialog based on a
``ConfirmationPrompt``. Confirmation cannot be silently overridden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from android_flasher.config.settings import Settings
from android_flasher.core.flash_plan import FlashPlan
from android_flasher.firmware.compatibility import (
    CompatibilityResult,
    CompatibilityStatus,
)
from android_flasher.safety.risk import RiskAssessment, RiskLevel


class ConfirmationRequirement(str, Enum):
    NONE = "NONE"
    STANDARD = "STANDARD"
    ELEVATED = "ELEVATED"
    BLOCKED = "BLOCKED"


@dataclass
class ConfirmationPrompt:
    """The message presented to the user before execution."""

    requirement: ConfirmationRequirement
    title: str
    body: str
    must_acknowledge: bool = True
    require_typed_phrase: Optional[str] = None
    extra_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "requirement": self.requirement.value,
            "title": self.title,
            "body": self.body,
            "must_acknowledge": self.must_acknowledge,
            "require_typed_phrase": self.require_typed_phrase,
            "extra_notes": list(self.extra_notes),
        }


@dataclass
class ConfirmationDecision:
    """Result of a confirmation interaction."""

    confirmed: bool
    reason: str = ""

    def to_dict(self) -> dict:
        return {"confirmed": self.confirmed, "reason": self.reason}


class ConfirmationBuilder:
    """Builds a ``ConfirmationPrompt`` for a plan."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(
        self,
        *,
        plan: FlashPlan,
        risk: RiskAssessment,
        compatibility: Optional[CompatibilityResult],
    ) -> ConfirmationPrompt:
        # Blocked plans never prompt.
        if plan is None or plan.is_blocked():
            return ConfirmationPrompt(
                requirement=ConfirmationRequirement.BLOCKED,
                title="Operation Blocked",
                body="The plan is blocked and cannot be executed.",
            )

        if risk is not None and risk.blocked:
            return ConfirmationPrompt(
                requirement=ConfirmationRequirement.BLOCKED,
                title="Operation Blocked",
                body=risk.blocking_reason
                or "The operation is blocked by the risk engine.",
            )

        if not self._settings.safety.require_confirmation:
            return ConfirmationPrompt(
                requirement=ConfirmationRequirement.NONE,
                title="Confirmation Disabled",
                body="Confirmation is disabled in settings.",
                must_acknowledge=False,
            )

        if risk is None:
            return ConfirmationPrompt(
                requirement=ConfirmationRequirement.STANDARD,
                title="Confirm Operation",
                body="Confirm execution of this plan.",
            )

        require_elevated = False

        if (
            compatibility is not None
            and compatibility.status == CompatibilityStatus.UNKNOWN
            and self._settings.safety.allow_unknown_compatibility
        ):
            require_elevated = True

        if (
            risk.level == RiskLevel.HIGH
            and self._settings.safety.require_confirmation_for_high
        ):
            require_elevated = True

        if risk.level == RiskLevel.CRITICAL:
            if self._settings.safety.block_critical:
                return ConfirmationPrompt(
                    requirement=ConfirmationRequirement.BLOCKED,
                    title="Operation Blocked (CRITICAL risk)",
                    body="This operation has CRITICAL risk and is blocked by settings.",
                )
            if self._settings.safety.require_confirmation_for_critical:
                require_elevated = True

        requirement = (
            ConfirmationRequirement.ELEVATED
            if require_elevated
            else ConfirmationRequirement.STANDARD
        )

        body_lines: list[str] = []
        body_lines.append(f"Plan: {plan.plan_id}")
        body_lines.append(f"Risk level: {risk.level.value}")
        if plan.target_slot:
            body_lines.append(f"Target slot: {plan.target_slot}")
        if compatibility is not None:
            body_lines.append(f"Compatibility: {compatibility.status.value}")

        prompt = ConfirmationPrompt(
            requirement=requirement,
            title=(
                "Confirm HIGH RISK Operation"
                if requirement == ConfirmationRequirement.ELEVATED
                else "Confirm Operation"
            ),
            body="\n".join(body_lines),
            must_acknowledge=True,
        )

        if requirement == ConfirmationRequirement.ELEVATED:
            prompt.require_typed_phrase = "FLASH"
            prompt.extra_notes.append(
                "Type FLASH to confirm this elevated-risk operation."
            )

        return prompt
