"""Low-level safety validation primitives.

``SafetyValidator`` accumulates ``ValidationIssue`` records. It is the
underlying machinery used by ``SafetyPreflight``. It does not decide
what to do with issues; it only records them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ValidationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKER = "BLOCKER"

    @property
    def order(self) -> int:
        return {
            ValidationSeverity.INFO: 0,
            ValidationSeverity.WARNING: 1,
            ValidationSeverity.ERROR: 2,
            ValidationSeverity.BLOCKER: 3,
        }[self]


@dataclass
class ValidationIssue:
    severity: ValidationSeverity
    code: str
    message: str
    hint: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
        }


class SafetyValidator:
    """Accumulates validation issues."""

    def __init__(self) -> None:
        self._issues: list[ValidationIssue] = []

    # ------------------------------------------------------------------
    # Issue recording
    # ------------------------------------------------------------------

    def info(self, code: str, message: str, hint: str = "") -> None:
        self._issues.append(
            ValidationIssue(ValidationSeverity.INFO, code, message, hint)
        )

    def warn(self, code: str, message: str, hint: str = "") -> None:
        self._issues.append(
            ValidationIssue(ValidationSeverity.WARNING, code, message, hint)
        )

    def error(self, code: str, message: str, hint: str = "") -> None:
        self._issues.append(
            ValidationIssue(ValidationSeverity.ERROR, code, message, hint)
        )

    def block(self, code: str, message: str, hint: str = "") -> None:
        self._issues.append(
            ValidationIssue(ValidationSeverity.BLOCKER, code, message, hint)
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def issues(self) -> list[ValidationIssue]:
        return list(self._issues)

    def has_blockers(self) -> bool:
        return any(i.severity == ValidationSeverity.BLOCKER for i in self._issues)

    def has_errors(self) -> bool:
        return any(i.severity == ValidationSeverity.ERROR for i in self._issues)

    def has_warnings(self) -> bool:
        return any(i.severity == ValidationSeverity.WARNING for i in self._issues)

    def blockers(self) -> list[ValidationIssue]:
        return [i for i in self._issues if i.severity == ValidationSeverity.BLOCKER]

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self._issues if i.severity == ValidationSeverity.ERROR]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self._issues if i.severity == ValidationSeverity.WARNING]

    def to_dict(self) -> dict:
        return {
            "issues": [i.to_dict() for i in self._issues],
            "has_blockers": self.has_blockers(),
            "has_errors": self.has_errors(),
            "has_warnings": self.has_warnings(),
        }
