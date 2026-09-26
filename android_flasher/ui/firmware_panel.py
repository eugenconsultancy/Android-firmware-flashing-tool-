"""Firmware panel.

Lets the user choose a firmware file and displays the analysis result.

Public API (used by ``MainWindow``):

    firmware_selected : Signal(object)   # emits a ``Path``
    update_package(package: FirmwarePackage) -> None
    clear() -> None

The internal slot ``_on_select_clicked`` is intentionally exposed
(without a name-mangling prefix) so that ``MainWindow._select_firmware``
can trigger the file dialog from the File menu.

Never runs any subprocess. Purely a display + file-picker widget.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from android_flasher.firmware.package import FirmwarePackage


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "field-label")
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    label.setMinimumWidth(96)
    return label


def _value_label(mono: bool = False) -> QLabel:
    label = QLabel("\u2014")
    label.setProperty("role", "field-value-mono" if mono else "field-value")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return label


class FirmwarePanel(QWidget):
    """Firmware selection and summary panel."""

    firmware_selected = Signal(object)   # Path

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._package: Optional[FirmwarePackage] = None
        self._path: Optional[Path] = None
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        group = QGroupBox("Firmware", self)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(16, 18, 16, 16)
        group_layout.setSpacing(12)

        # --- Selection row: button + hint/path label ---
        select_row = QHBoxLayout()
        select_row.setSpacing(10)

        self._select_button = QPushButton("Select Firmware\u2026", group)
        self._select_button.setProperty("kind", "primary")
        self._select_button.clicked.connect(self._on_select_clicked)
        select_row.addWidget(self._select_button)

        self._path_label = QLabel("No firmware selected.", group)
        self._path_label.setProperty("role", "hint")
        self._path_label.setWordWrap(True)
        self._path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        select_row.addWidget(self._path_label, 1)
        group_layout.addLayout(select_row)

        # --- Details grid ---
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        self._name_label = _value_label()
        self._type_label = _value_label()
        self._target_label = _value_label(mono=True)
        self._android_label = _value_label()
        self._build_label = _value_label(mono=True)
        self._images_label = _value_label()
        self._size_label = _value_label(mono=True)
        self._hash_label = _value_label(mono=True)

        form.addRow(_field_label("Name"), self._name_label)
        form.addRow(_field_label("Type"), self._type_label)
        form.addRow(_field_label("Target"), self._target_label)
        form.addRow(_field_label("Android"), self._android_label)
        form.addRow(_field_label("Build"), self._build_label)
        form.addRow(_field_label("Images"), self._images_label)
        form.addRow(_field_label("Size"), self._size_label)
        form.addRow(_field_label("SHA-256"), self._hash_label)

        group_layout.addLayout(form)

        layout.addWidget(group)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_package(self, package: Optional[FirmwarePackage]) -> None:
        """Populate the panel from a ``FirmwarePackage``.

        Passing ``None`` clears the panel.
        """
        self._package = package
        if package is None:
            self.clear()
            return

        self._path = package.path
        self._set_path_text(str(package.path), role="field-value-mono")

        metadata = package.metadata
        self._name_label.setText(metadata.source_name or "\u2014")
        self._type_label.setText(
            metadata.package_type or package.detection.firmware_type.value
        )
        self._target_label.setText(metadata.codename or "\u2014")
        self._android_label.setText(metadata.android_version or "\u2014")
        self._build_label.setText(metadata.build_id or "\u2014")

        if metadata.images:
            names = [img.name for img in metadata.images[:8]]
            suffix = ""
            if len(metadata.images) > 8:
                suffix = f" (+{len(metadata.images) - 8} more)"
            self._images_label.setText(", ".join(names) + suffix)
        else:
            self._images_label.setText("\u2014")

        self._size_label.setText(_human_size(metadata.source_size_bytes))

        if metadata.source_sha256:
            self._hash_label.setText(metadata.source_sha256)
        elif metadata.source_sha512:
            self._hash_label.setText(metadata.source_sha512)
        else:
            self._hash_label.setText("(not computed)")

    def clear(self) -> None:
        """Reset the panel to its empty state."""
        self._package = None
        self._path = None
        self._set_path_text("No firmware selected.", role="hint")
        for label in (
            self._name_label,
            self._type_label,
            self._target_label,
            self._android_label,
            self._build_label,
            self._images_label,
            self._size_label,
            self._hash_label,
        ):
            label.setText("\u2014")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _set_path_text(self, text: str, role: str) -> None:
        """Set the path label text and refresh its QSS ``role`` property."""
        self._path_label.setText(text)
        self._path_label.setProperty("role", role)
        self._path_label.style().unpolish(self._path_label)
        self._path_label.style().polish(self._path_label)

    def _on_select_clicked(self) -> None:
        """Open the file dialog and emit ``firmware_selected``."""
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select firmware file",
            "",
            "Firmware (*.img *.zip *.bin *.tgz);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        self._path = path
        self._set_path_text(str(path), role="field-value-mono")
        self.firmware_selected.emit(path)


def _human_size(size: Optional[int]) -> str:
    if size is None:
        return "\u2014"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{size} B"
