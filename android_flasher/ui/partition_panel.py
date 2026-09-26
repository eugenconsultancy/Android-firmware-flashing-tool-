"""Partition analysis panel.

Displays the PartitionAnalysis produced by the partition manager.
Shows physical, logical, dynamic, and slot-aware partitions, with
their sizes and sources.

Layout: a compact summary strip at the top, a full-height table below.
The table stretches to fill the tab; the summary never consumes more
than a few lines of vertical space.
"""

from __future__ import annotations

from typing import Optional

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

from android_flasher.partitions.manager import PartitionAnalysis


class PartitionPanel(QWidget):
    """Displays the partition analysis."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._analysis: Optional[PartitionAnalysis] = None
        self._build()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --- Compact summary card ---
        self._summary_group = QGroupBox("Partition Summary", self)
        summary_layout = QVBoxLayout(self._summary_group)
        summary_layout.setContentsMargins(12, 14, 12, 12)
        summary_layout.setSpacing(4)

        self._summary_label = QLabel("No partition analysis available.", self)
        self._summary_label.setWordWrap(True)
        self._summary_label.setProperty("role", "field-value")
        summary_layout.addWidget(self._summary_label)
        layout.addWidget(self._summary_group)

        # --- Full-height table ---
        self._table_group = QGroupBox("Partition Table", self)
        table_layout = QVBoxLayout(self._table_group)
        table_layout.setContentsMargins(12, 14, 12, 12)
        table_layout.setSpacing(6)

        self._table = QTableWidget(0, 5, self)
        self._table.setHorizontalHeaderLabels(
            ["Partition", "Kind", "Size", "Slot aware", "Source"]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        table_layout.addWidget(self._table)
        layout.addWidget(self._table_group, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_analysis(self, analysis: Optional[PartitionAnalysis]) -> None:
        self._analysis = analysis
        if analysis is None:
            self.clear()
            return

        counts = {
            "device": 0,
            "firmware": 0,
            "matched": 0,
            "extra_firmware": 0,
            "missing_firmware": 0,
        }
        try:
            if analysis.device is not None:
                counts["device"] = len(list(analysis.device))
            if analysis.firmware is not None:
                counts["firmware"] = len(list(analysis.firmware))
            if getattr(analysis, "matched", None) is not None:
                counts["matched"] = len(analysis.matched)
            if getattr(analysis, "extra_firmware", None) is not None:
                counts["extra_firmware"] = len(analysis.extra_firmware)
            if getattr(analysis, "missing_firmware", None) is not None:
                counts["missing_firmware"] = len(analysis.missing_firmware)
        except Exception:  # noqa: BLE001 - defensive
            pass

        summary_lines = [
            f"Device partitions: {counts['device']}",
            f"Firmware partitions: {counts['firmware']}",
            f"Matched: {counts['matched']}",
            f"Extra in firmware: {counts['extra_firmware']}",
            f"Missing from firmware: {counts['missing_firmware']}",
        ]
        self._summary_label.setText("\n".join(summary_lines))

        rows = self._collect_rows(analysis)
        self._table.setRowCount(len(rows))
        for row, (name, kind, size, slot_aware, source) in enumerate(rows):
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(kind))
            self._table.setItem(row, 2, QTableWidgetItem(size))
            self._table.setItem(row, 3, QTableWidgetItem(slot_aware))
            self._table.setItem(row, 4, QTableWidgetItem(source))

    def clear(self) -> None:
        self._analysis = None
        self._summary_label.setText("No partition analysis available.")
        self._table.setRowCount(0)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_rows(analysis: PartitionAnalysis) -> list[tuple[str, str, str, str, str]]:
        rows: list[tuple[str, str, str, str, str]] = []

        if analysis.device is not None:
            try:
                for record in analysis.device:
                    rows.append(_record_to_row(record, "device"))
            except Exception:  # noqa: BLE001 - defensive
                pass

        if analysis.firmware is not None:
            try:
                for record in analysis.firmware:
                    rows.append(_record_to_row(record, "firmware"))
            except Exception:  # noqa: BLE001 - defensive
                pass

        return rows


def _record_to_row(record, source: str) -> tuple[str, str, str, str, str]:
    name = getattr(record, "name", "\u2014")
    kind = getattr(record, "kind", None)
    kind_value = getattr(kind, "value", None) if kind else "\u2014"
    size = getattr(record, "size_bytes", None)
    size_text = _human_size(size)
    slot_aware = "yes" if getattr(record, "slot_aware", False) else "no"
    return (str(name), str(kind_value), size_text, slot_aware, source)


def _human_size(size) -> str:
    if size is None:
        return "\u2014"
    try:
        value = float(size)
    except (TypeError, ValueError):
        return str(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{size}"
