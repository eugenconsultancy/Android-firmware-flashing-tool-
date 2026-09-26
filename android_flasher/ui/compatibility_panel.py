"""Compatibility matrix panel.

Renders the CompatibilityResult as a matrix of attribute / device /
firmware / state rows. States are rendered as PASS / WARNING / UNKNOWN
/ FAIL / BLOCKED. Compatibility is never overstated: an UNKNOWN state
is displayed as UNKNOWN, not as PASS.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from android_flasher.firmware.compatibility import (
    CompatibilityResult,
    CompatibilityStatus,
)


_STATE_COLORS = {
    "PASS": QColor("#4ec9b0"),
    "WARNING": QColor("#e2b341"),
    "UNKNOWN": QColor("#a0a0a0"),
    "FAIL": QColor("#f08a7a"),
    "BLOCKED": QColor("#f44747"),
}


class CompatibilityPanel(QWidget):
    """Displays the compatibility matrix."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._result: Optional[CompatibilityResult] = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Result header.
        self._result_group = QGroupBox("Compatibility Result", self)
        result_layout = QVBoxLayout(self._result_group)
        result_layout.setContentsMargins(12, 14, 12, 12)
        result_layout.setSpacing(6)

        self._status_label = QLabel("No compatibility analysis has been run.")
        self._status_label.setStyleSheet("font-size: 12pt; font-weight: 700;")
        self._status_label.setWordWrap(True)
        result_layout.addWidget(self._status_label)

        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        self._summary_label.setProperty("role", "muted")
        result_layout.addWidget(self._summary_label)

        layout.addWidget(self._result_group)

        # Matrix table.
        self._matrix_group = QGroupBox("Compatibility Matrix", self)
        matrix_layout = QVBoxLayout(self._matrix_group)
        matrix_layout.setContentsMargins(12, 14, 12, 12)
        matrix_layout.setSpacing(6)

        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(
            ["Attribute", "Device", "Firmware", "State"]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        matrix_layout.addWidget(self._table)

        layout.addWidget(self._matrix_group, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_result(self, result: Optional[CompatibilityResult]) -> None:
        self._result = result
        if result is None:
            self.clear()
            return

        status = result.status
        self._status_label.setText(f"Status: {status.value}")
        color = _status_color_for(status)
        self._status_label.setStyleSheet(
            f"font-size: 12pt; font-weight: 700; color: {color.name()};"
        )

        if result.reasons:
            self._summary_label.setText("\n".join(f"• {r}" for r in result.reasons))
        else:
            self._summary_label.setText("")

        rows = self._build_rows(result)
        self._table.setRowCount(len(rows))
        for row, (attribute, device, firmware, state) in enumerate(rows):
            self._table.setItem(row, 0, QTableWidgetItem(attribute))
            self._table.setItem(row, 1, QTableWidgetItem(device))
            self._table.setItem(row, 2, QTableWidgetItem(firmware))
            state_item = QTableWidgetItem(state)
            color = _STATE_COLORS.get(state, QColor("#a0a0a0"))
            state_item.setForeground(QBrush(color))
            self._table.setItem(row, 3, state_item)

    def clear(self) -> None:
        self._result = None
        self._status_label.setText("No compatibility analysis has been run.")
        self._status_label.setStyleSheet("font-size: 12pt; font-weight: 700;")
        self._summary_label.setText("")
        self._table.setRowCount(0)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_rows(result: CompatibilityResult) -> list[tuple[str, str, str, str]]:
        rows: list[tuple[str, str, str, str]] = []

        details = result.details if hasattr(result, "details") else {}
        device = details.get("device", {}) if isinstance(details, dict) else {}
        firmware = details.get("firmware", {}) if isinstance(details, dict) else {}

        attribute_pairs = [
            ("Manufacturer", "manufacturer"),
            ("Model", "model"),
            ("Codename", "codename"),
            ("Product", "product"),
            ("Variant", "variant"),
            ("Android", "android_version"),
            ("Architecture", "architecture"),
            ("Slot model", "slot_architecture"),
            ("Dynamic partitions", "dynamic_partitions"),
            ("Logical partitions", "logical_partitions"),
            ("Firmware integrity", "integrity"),
        ]

        for label, key in attribute_pairs:
            device_value = str(device.get(key, "—")) if device else "—"
            firmware_value = str(firmware.get(key, "—")) if firmware else "—"
            state = _derive_state(label, device_value, firmware_value, result)
            rows.append((label, device_value, firmware_value, state))

        return rows


def _derive_state(
    attribute: str,
    device_value: str,
    firmware_value: str,
    result: CompatibilityResult,
) -> str:
    if device_value == "—" and firmware_value == "—":
        return "UNKNOWN"
    if result.status == CompatibilityStatus.MISMATCH:
        if device_value != firmware_value and device_value != "—" and firmware_value != "—":
            return "FAIL"
        return "UNKNOWN"
    if result.status == CompatibilityStatus.BLOCKED:
        return "BLOCKED"
    if result.status == CompatibilityStatus.UNKNOWN:
        return "UNKNOWN"
    if device_value == "—" or firmware_value == "—":
        return "UNKNOWN"
    if device_value.lower() == firmware_value.lower():
        return "PASS"
    if result.status == CompatibilityStatus.LIKELY:
        return "WARNING"
    if result.status == CompatibilityStatus.CONFIRMED:
        return "PASS"
    return "UNKNOWN"


def _status_color_for(status: CompatibilityStatus) -> QColor:
    return {
        CompatibilityStatus.CONFIRMED: QColor("#4ec9b0"),
        CompatibilityStatus.LIKELY: QColor("#e2b341"),
        CompatibilityStatus.UNKNOWN: QColor("#a0a0a0"),
        CompatibilityStatus.MISMATCH: QColor("#f08a7a"),
        CompatibilityStatus.BLOCKED: QColor("#f44747"),
    }.get(status, QColor("#a0a0a0"))
