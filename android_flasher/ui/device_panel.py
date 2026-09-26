"""Device information panel.

Displays the normalized DeviceIdentity. Uses a two-column card layout
with a clear label/value typography hierarchy. Serial, build and
codename values are rendered in a monospaced font for readability.

Purely a display widget: it never runs commands.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from android_flasher.devices.identification import DeviceIdentity


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "field-label")
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    label.setMinimumWidth(110)
    return label


def _value_label() -> QLabel:
    label = QLabel("—")
    label.setProperty("role", "field-value")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return label


def _mono_value_label() -> QLabel:
    label = QLabel("—")
    label.setProperty("role", "field-value-mono")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return label


class DevicePanel(QWidget):
    """Renders a DeviceIdentity as a readable card."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._identity: Optional[DeviceIdentity] = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        group = QGroupBox("Device", self)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(16, 18, 16, 16)
        group_layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        self._state_label = _value_label()
        self._transport_label = _value_label()
        self._serial_label = _mono_value_label()
        self._manufacturer_label = _value_label()
        self._brand_label = _value_label()
        self._model_label = _value_label()
        self._codename_label = _mono_value_label()
        self._product_label = _mono_value_label()
        self._variant_label = _value_label()
        self._android_label = _value_label()
        self._sdk_label = _value_label()
        self._build_label = _mono_value_label()
        self._bootloader_label = _value_label()
        self._slot_label = _value_label()

        rows = [
            ("State", self._state_label),
            ("Transport", self._transport_label),
            ("Serial", self._serial_label),
            ("Manufacturer", self._manufacturer_label),
            ("Brand", self._brand_label),
            ("Model", self._model_label),
            ("Codename", self._codename_label),
            ("Product", self._product_label),
            ("Variant", self._variant_label),
            ("Android", self._android_label),
            ("SDK", self._sdk_label),
            ("Build", self._build_label),
            ("Bootloader", self._bootloader_label),
            ("Slot", self._slot_label),
        ]
        for index, (name, widget) in enumerate(rows):
            grid.addWidget(_field_label(f"{name}"), index, 0)
            grid.addWidget(widget, index, 1)

        group_layout.addLayout(grid)

        # Capabilities line separated by a subtle divider.
        divider = QFrame(self)
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: rgba(255,255,255,0.06);")
        group_layout.addWidget(divider)

        caps_label = QLabel("Capabilities")
        caps_label.setProperty("role", "field-label")
        group_layout.addWidget(caps_label)

        self._capabilities_label = QLabel("—")
        self._capabilities_label.setProperty("role", "muted")
        self._capabilities_label.setWordWrap(True)
        group_layout.addWidget(self._capabilities_label)

        layout.addWidget(group)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_identity(self, identity: Optional[DeviceIdentity]) -> None:
        self._identity = identity
        if identity is None:
            self.clear()
            return

        self._state_label.setText(
            getattr(identity.state, "value", None) or str(identity.state)
        )
        self._transport_label.setText(identity.transport or "—")
        self._serial_label.setText(identity.serial or "—")
        self._manufacturer_label.setText(identity.manufacturer or "—")
        self._brand_label.setText(identity.brand or "—")
        self._model_label.setText(identity.model or "—")
        self._codename_label.setText(identity.device_codename or "—")
        self._product_label.setText(identity.product or "—")
        self._variant_label.setText(identity.variant or "—")
        self._android_label.setText(identity.android_version or "—")
        self._sdk_label.setText(
            str(identity.sdk_version) if identity.sdk_version else "—"
        )
        # Fixed: DeviceIdentity exposes `fingerprint` and `build_id`,
        # not `build_fingerprint`.
        build_text = identity.fingerprint or identity.build_id or "—"
        self._build_label.setText(build_text)

        lock_state = getattr(identity.bootloader_state, "value", None)
        if lock_state is None and identity.bootloader_state is not None:
            lock_state = str(identity.bootloader_state)
        self._bootloader_label.setText(lock_state or "—")

        # Fixed: DeviceIdentity has no `slot_suffix` attribute.
        slot = identity.current_slot
        if slot:
            self._slot_label.setText(slot)
        elif identity.slot_support:
            self._slot_label.setText("(A/B supported, slot unknown)")
        else:
            self._slot_label.setText("none")

        caps = getattr(identity, "capabilities", None)
        self._capabilities_label.setText(self._format_capabilities(caps))

    def clear(self) -> None:
        for label in (
            self._state_label,
            self._transport_label,
            self._serial_label,
            self._manufacturer_label,
            self._brand_label,
            self._model_label,
            self._codename_label,
            self._product_label,
            self._variant_label,
            self._android_label,
            self._sdk_label,
            self._build_label,
            self._bootloader_label,
            self._slot_label,
            self._capabilities_label,
        ):
            label.setText("—")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _format_capabilities(caps: object) -> str:
        if caps is None:
            return "—"
        parts: list[str] = []
        checks = [
            ("supports_ab", "A/B"),
            ("supports_fastbootd", "fastbootd"),
            ("supports_dynamic_partitions", "dynamic"),
            ("supports_logical_partitions", "logical"),
            ("supports_slot_management", "slot mgmt"),
            ("supports_update", "update"),
            ("supports_flash", "flash"),
            ("supports_getvar", "getvar"),
        ]
        for attr, label in checks:
            value = getattr(caps, attr, None)
            if value is True:
                parts.append(f"✓ {label}")
            elif value is False:
                parts.append(f"✗ {label}")
        return "    ".join(parts) if parts else "—"