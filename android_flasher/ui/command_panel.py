"""Command preview panel.

Shows the exact argv list that will be executed. This is a read-only
view: the panel never builds commands and never executes them. The
application does not expose an arbitrary command runner.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtGui import QFont
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

from android_flasher.core.flash_plan import FlashPlan


class CommandPanel(QWidget):
    """Renders the exact command argv for every step in a plan."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        note = QLabel(
            "Commands below are executed with shell=False and argument "
            "lists only. They are never passed to a shell. This panel is "
            "read-only: the application does not expose an arbitrary "
            "command runner.",
            self,
        )
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        layout.addWidget(note)

        self._group = QGroupBox("Generated Commands", self)
        group_layout = QVBoxLayout(self._group)
        group_layout.setContentsMargins(12, 14, 12, 12)
        group_layout.setSpacing(6)

        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(
            ["#", "Transport", "Description", "Argv"]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        group_layout.addWidget(self._table)

        layout.addWidget(self._group, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_plan(self, plan: Optional[FlashPlan]) -> None:
        if plan is None:
            self.clear()
            return
        self._table.setRowCount(len(plan.steps))
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        for row, step in enumerate(plan.steps):
            self._table.setItem(row, 0, QTableWidgetItem(str(step.index)))
            transport = "\u2014"
            if step.command:
                first = step.command[0].lower()
                if "fastboot" in first:
                    transport = "fastboot"
                elif "adb" in first:
                    transport = "adb"
            self._table.setItem(row, 1, QTableWidgetItem(transport))
            self._table.setItem(row, 2, QTableWidgetItem(step.description))
            argv_text = " ".join(step.command) if step.command else "\u2014"
            item = QTableWidgetItem(argv_text)
            item.setFont(mono)
            self._table.setItem(row, 3, item)

    def clear(self) -> None:
        self._table.setRowCount(0)
