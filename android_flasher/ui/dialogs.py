"""Reusable dialog helpers.

Provides user-friendly error / warning / information dialogs and a
details dialog for long text (stack traces, command output, logs).
Technical detail always remains available via the details dialog even
when the top-level message is user-friendly.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TextDetailsDialog(QDialog):
    """A dialog that shows long technical text (stack traces, logs)."""

    def __init__(
        self,
        title: str,
        text: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 500)

        layout = QVBoxLayout(self)

        header = QLabel(title, self)
        header.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(header)

        self._text = QPlainTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setPlainText(text)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self._text.setFont(font)
        layout.addWidget(self._text, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        copy_button = QPushButton("Copy to Clipboard", self)
        copy_button.clicked.connect(self._copy_to_clipboard)

        button_row = QHBoxLayout()
        button_row.addWidget(copy_button)
        button_row.addStretch(1)
        button_row.addWidget(buttons)
        layout.addLayout(button_row)

    def _copy_to_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._text.toPlainText())


def show_error(
    parent: Optional[QWidget],
    title: str,
    message: str,
    details: str = "",
) -> None:
    """Show a user-friendly error, with optional technical details."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(title)
    box.setText(message)
    if details:
        box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def show_warning(
    parent: Optional[QWidget],
    title: str,
    message: str,
    details: str = "",
) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(message)
    if details:
        box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def show_information(
    parent: Optional[QWidget],
    title: str,
    message: str,
    details: str = "",
) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(title)
    box.setText(message)
    if details:
        box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def show_confirmation(
    parent: Optional[QWidget],
    title: str,
    message: str,
    details: str = "",
    confirm_text: str = "Confirm",
    cancel_text: str = "Cancel",
) -> bool:
    """Ask the user to confirm. Returns True if confirmed."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(message)
    if details:
        box.setDetailedText(details)

    confirm_button = box.addButton(confirm_text, QMessageBox.ButtonRole.AcceptRole)
    cancel_button = box.addButton(cancel_text, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    box.exec()
    return box.clickedButton() is confirm_button
