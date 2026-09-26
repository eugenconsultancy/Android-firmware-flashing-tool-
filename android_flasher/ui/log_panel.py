"""Log panel.

Displays application log lines, flash session output, command output,
errors and warnings. The filter row occupies a single line; the log
box stretches to fill the tab and provides its own scrollbar.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Slot
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class LogPanel(QWidget):
    """Append-only log view with severity filters."""

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

        # --- Compact filter row ---
        controls = QHBoxLayout()
        controls.setSpacing(10)

        show_label = QLabel("Show:", self)
        show_label.setProperty("role", "field-label")
        controls.addWidget(show_label)

        self._show_info = QCheckBox("Info", self)
        self._show_info.setChecked(True)
        controls.addWidget(self._show_info)

        self._show_warnings = QCheckBox("Warnings", self)
        self._show_warnings.setChecked(True)
        controls.addWidget(self._show_warnings)

        self._show_errors = QCheckBox("Errors", self)
        self._show_errors.setChecked(True)
        controls.addWidget(self._show_errors)

        controls.addStretch(1)

        self._copy_button = QPushButton("Copy All", self)
        self._copy_button.setToolTip("Copy the full log to the clipboard.")
        self._copy_button.clicked.connect(self._copy_all)
        controls.addWidget(self._copy_button)

        self._clear_button = QPushButton("Clear", self)
        self._clear_button.setToolTip("Clear the log view.")
        self._clear_button.clicked.connect(self.clear)
        controls.addWidget(self._clear_button)

        layout.addLayout(controls)

        # --- Log box (stretches) ---
        self._group = QGroupBox("Log", self)
        group_layout = QVBoxLayout(self._group)
        group_layout.setContentsMargins(12, 14, 12, 12)
        group_layout.setSpacing(6)

        self._text = QPlainTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(20000)
        self._text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self._text.setFont(font)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        group_layout.addWidget(self._text)

        layout.addWidget(self._group, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @Slot(str)
    def append(self, message: str) -> None:
        if not message:
            return
        lowered = message.lower()
        if "error" in lowered or "critical" in lowered:
            if not self._show_errors.isChecked():
                return
        elif "warn" in lowered:
            if not self._show_warnings.isChecked():
                return
        else:
            if not self._show_info.isChecked():
                return

        self._text.appendPlainText(message)
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text.setTextCursor(cursor)

    def append_error(self, message: str) -> None:
        self.append(f"ERROR: {message}")

    def append_warning(self, message: str) -> None:
        self.append(f"WARNING: {message}")

    def clear(self) -> None:
        self._text.clear()

    def to_text(self) -> str:
        return self._text.toPlainText()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _copy_all(self) -> None:
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._text.toPlainText())
