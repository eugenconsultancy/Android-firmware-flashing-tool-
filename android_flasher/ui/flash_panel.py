"""Flash plan panel.

Displays the FlashPlan produced by the planner:

    * plan status, target, firmware, slot strategy, risk, confirmation
    * the ordered list of steps with their generated commands
    * blockers / warnings / requirements

Signals emitted to ``MainWindow``:

    generate_plan_requested
    execute_plan_requested
    cancel_execution_requested

The panel never runs commands. It only renders the plan and forwards
button clicks.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from android_flasher.core.flash_plan import FlashPlan, FlashPlanStatus


_RISK_COLORS = {
    "LOW": QColor("#4ec9b0"),
    "MEDIUM": QColor("#e2b341"),
    "HIGH": QColor("#f08a7a"),
    "CRITICAL": QColor("#f44747"),
    "UNKNOWN": QColor("#a0a0a0"),
}


class FlashPanel(QWidget):
    """Displays a flash plan and its steps."""

    generate_plan_requested = Signal()
    execute_plan_requested = Signal()
    cancel_execution_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._plan: Optional[FlashPlan] = None
        self._build()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --- Button row ---
        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        self._generate_button = QPushButton("Generate Flash Plan", self)
        self._generate_button.setProperty("kind", "primary")
        self._generate_button.clicked.connect(self.generate_plan_requested.emit)
        button_row.addWidget(self._generate_button)

        self._execute_button = QPushButton("Execute Plan\u2026", self)
        self._execute_button.setEnabled(False)
        self._execute_button.clicked.connect(self.execute_plan_requested.emit)
        button_row.addWidget(self._execute_button)

        self._cancel_button = QPushButton("Cancel Execution", self)
        self._cancel_button.setProperty("kind", "danger")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self.cancel_execution_requested.emit)
        button_row.addWidget(self._cancel_button)

        button_row.addStretch(1)
        layout.addLayout(button_row)

        # --- Plan summary card ---
        self._summary_group = QGroupBox("Plan Summary", self)
        summary_form = QFormLayout(self._summary_group)
        summary_form.setContentsMargins(14, 16, 14, 14)
        summary_form.setHorizontalSpacing(16)
        summary_form.setVerticalSpacing(8)
        summary_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._plan_id_label = QLabel("\u2014")
        self._plan_id_label.setProperty("role", "field-value-mono")
        self._status_label = QLabel("\u2014")
        self._status_label.setProperty("role", "field-value")
        self._target_label = QLabel("\u2014")
        self._target_label.setProperty("role", "field-value")
        self._firmware_label = QLabel("\u2014")
        self._firmware_label.setProperty("role", "field-value")
        self._slot_label = QLabel("\u2014")
        self._slot_label.setProperty("role", "field-value")
        self._risk_label = QLabel("\u2014")
        self._confirmation_label = QLabel("\u2014")
        self._confirmation_label.setProperty("role", "field-value")

        summary_form.addRow("Plan ID:", self._plan_id_label)
        summary_form.addRow("Status:", self._status_label)
        summary_form.addRow("Target:", self._target_label)
        summary_form.addRow("Firmware:", self._firmware_label)
        summary_form.addRow("Slot strategy:", self._slot_label)
        summary_form.addRow("Risk:", self._risk_label)
        summary_form.addRow("Confirmation:", self._confirmation_label)
        layout.addWidget(self._summary_group)

        # --- Steps card (stretches) ---
        self._steps_group = QGroupBox("Steps", self)
        steps_layout = QVBoxLayout(self._steps_group)
        steps_layout.setContentsMargins(12, 14, 12, 12)
        steps_layout.setSpacing(6)

        self._steps_table = QTableWidget(0, 4, self)
        self._steps_table.setHorizontalHeaderLabels(
            ["#", "Kind", "Description", "Command"]
        )
        header = self._steps_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._steps_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._steps_table.setAlternatingRowColors(True)
        self._steps_table.verticalHeader().setVisible(False)
        self._steps_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        steps_layout.addWidget(self._steps_table)
        layout.addWidget(self._steps_group, 3)

        # --- Blockers / warnings card (fixed minimum height) ---
        self._blockers_group = QGroupBox("Blockers & Warnings", self)
        blockers_layout = QVBoxLayout(self._blockers_group)
        blockers_layout.setContentsMargins(12, 14, 12, 12)
        blockers_layout.setSpacing(6)

        self._blockers_label = QLabel("\u2014", self)
        self._blockers_label.setWordWrap(True)
        self._blockers_label.setProperty("role", "field-value")
        self._blockers_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._blockers_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        blockers_layout.addWidget(self._blockers_label)
        self._blockers_group.setMinimumHeight(110)
        layout.addWidget(self._blockers_group, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_plan(self, plan: Optional[FlashPlan]) -> None:
        self._plan = plan
        if plan is None:
            self.clear()
            return

        self._plan_id_label.setText(plan.plan_id)
        self._status_label.setText(plan.status.value)
        self._target_label.setText(
            f"{plan.device_codename or '\u2014'} / {plan.device_serial or '\u2014'}"
        )
        self._firmware_label.setText(
            f"{plan.firmware_type or '\u2014'} ({plan.firmware_path or '\u2014'})"
        )
        self._slot_label.setText(
            f"{plan.slot_strategy.value} / current={plan.current_slot or '\u2014'} "
            f"target={plan.target_slot or '\u2014'}"
        )

        risk_color = _RISK_COLORS.get(plan.risk_level, QColor("#a0a0a0"))
        self._risk_label.setText(plan.risk_level)
        self._risk_label.setStyleSheet(
            f"color: {risk_color.name()}; font-weight: 700;"
        )
        self._confirmation_label.setText(plan.confirmation_required)

        self._populate_steps(plan)

        lines: list[str] = []
        for b in plan.blockers:
            lines.append(f"\u26d4  {b}")
        for w in plan.warnings:
            lines.append(f"\u26a0  {w}")
        for r in plan.requirements:
            lines.append(f"\u2022  {r}")
        if not lines:
            lines.append("\u2014")
        self._blockers_label.setText("\n".join(lines))

        self._execute_button.setEnabled(
            plan.status in (FlashPlanStatus.READY, FlashPlanStatus.REQUIRES_CONFIRMATION)
        )

    def set_execution_in_progress(self, in_progress: bool) -> None:
        self._execute_button.setEnabled(not in_progress)
        self._cancel_button.setEnabled(in_progress)

    def clear(self) -> None:
        self._plan = None
        for label in (
            self._plan_id_label,
            self._status_label,
            self._target_label,
            self._firmware_label,
            self._slot_label,
            self._risk_label,
            self._confirmation_label,
        ):
            label.setText("\u2014")
            label.setStyleSheet("")
        self._steps_table.setRowCount(0)
        self._blockers_label.setText("\u2014")
        self._execute_button.setEnabled(False)
        self._cancel_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _populate_steps(self, plan: FlashPlan) -> None:
        self._steps_table.setRowCount(len(plan.steps))
        for row, step in enumerate(plan.steps):
            self._steps_table.setItem(row, 0, QTableWidgetItem(str(step.index)))
            self._steps_table.setItem(row, 1, QTableWidgetItem(step.kind.value))
            self._steps_table.setItem(row, 2, QTableWidgetItem(step.description))
            command_text = " ".join(step.command) if step.command else "\u2014"
            self._steps_table.setItem(row, 3, QTableWidgetItem(command_text))
