"""Progress panel.

Compact single-row status strip. Fits inside the fixed-height
``#progress_container`` that the redesigned main window places above
the tab widget.

Layout (one horizontal row):

    [ status pill ]   [ status text .................. ]   [ bar ]   [ % ]   [ elapsed ]

Public API used by ``MainWindow``:

    start_busy()                              — indeterminate spin
    stop_busy()                               — cancel the spin
    start_steps(total: int)                   — determinate mode
    mark_step_completed()                     — advance the bar
    finish()                                  — force 100%, done pill
    reset()                                   — clear everything
    set_status(message: str)                  — middle label
    set_operation(operation: str)             — operation line
    set_partition(partition: str)             — partition line
    set_error(message: str = "Failed")        — red pill
    _set_pill(text: str, state: str)          — pill text + QSS state

The panel never runs commands. It only reflects state.
"""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ProgressPanel(QWidget):
    """Compact progress strip."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._start_time: Optional[float] = None
        self._busy = False
        self._total_steps = 0
        self._completed_steps = 0
        self._build()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Single row.
        row = QHBoxLayout()
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(12)

        # Pill.
        self._status_pill = QLabel("Idle", self)
        self._status_pill.setProperty("role", "pill")
        self._status_pill.setProperty("state", "idle")
        self._status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._status_pill)

        # Status text (expands).
        self._status_label = QLabel("Ready.", self)
        self._status_label.setProperty("role", "field-value")
        self._status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._status_label.setMinimumWidth(120)
        row.addWidget(self._status_label, 1)

        # Progress bar.
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(10)
        self._progress_bar.setFixedWidth(180)
        row.addWidget(self._progress_bar)

        # Percent.
        self._percent_label = QLabel("0%", self)
        self._percent_label.setProperty("role", "field-value-mono")
        self._percent_label.setMinimumWidth(44)
        self._percent_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row.addWidget(self._percent_label)

        # Elapsed.
        self._elapsed_label = QLabel("Elapsed: 00:00", self)
        self._elapsed_label.setProperty("role", "field-value-mono")
        self._elapsed_label.setMinimumWidth(120)
        self._elapsed_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row.addWidget(self._elapsed_label)

        outer.addLayout(row)

        # Hidden fields kept for API parity with the wider panel. They
        # are surfaced via tooltips so the information is still reachable.
        self._operation_label = QLabel("—", self)
        self._operation_label.setVisible(False)
        self._partition_label = QLabel("—", self)
        self._partition_label.setVisible(False)

    # ------------------------------------------------------------------
    # Lifecycle: busy / steps / idle
    # ------------------------------------------------------------------

    def start_busy(self) -> None:
        self._busy = True
        self._start_time = time.monotonic()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._percent_label.setText("\u2026")
        self._set_pill("Working", "idle")
        self._timer.start()

    def stop_busy(self) -> None:
        self._busy = False
        self._progress_bar.setRange(0, 100)
        self._timer.stop()

    def start_steps(self, total_steps: int) -> None:
        self._total_steps = max(0, int(total_steps))
        self._completed_steps = 0
        self._start_time = time.monotonic()
        self._timer.start()
        self._progress_bar.setRange(0, 100)
        self._set_pill("Running", "idle")
        self._update_percentage()

    def mark_step_completed(self) -> None:
        self._completed_steps += 1
        self._update_percentage()

    def finish(self) -> None:
        if self._total_steps > 0:
            self._completed_steps = self._total_steps
            self._update_percentage()
        elif self._progress_bar.maximum() == 0:
            # Was in indeterminate mode; switch to a full bar.
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(100)
            self._percent_label.setText("100%")
        self._timer.stop()
        self._set_pill("Done", "armed")

    def reset(self) -> None:
        self._busy = False
        self._start_time = None
        self._total_steps = 0
        self._completed_steps = 0
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._percent_label.setText("0%")
        self._status_label.setText("Idle.")
        self._elapsed_label.setText("Elapsed: 00:00")
        self._set_pill("Idle", "idle")
        self._timer.stop()

    # ------------------------------------------------------------------
    # Status setters
    # ------------------------------------------------------------------

    def set_status(self, message: str) -> None:
        text = message or "\u2014"
        self._status_label.setText(text)
        self._status_label.setToolTip(text)

    def set_operation(self, operation: str) -> None:
        self._operation_label.setText(operation or "\u2014")
        # Fold the operation into the visible status tooltip so it is not lost.
        current = self._status_label.toolTip() or self._status_label.text()
        self._status_label.setToolTip(
            f"{current}\nOperation: {operation or '\u2014'}"
        )

    def set_partition(self, partition: str) -> None:
        self._partition_label.setText(partition or "\u2014")
        current = self._status_label.toolTip() or self._status_label.text()
        self._status_label.setToolTip(
            f"{current}\nPartition: {partition or '\u2014'}"
        )

    def set_error(self, message: str = "Failed") -> None:
        self._timer.stop()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100)
        self._percent_label.setText("100%")
        self._set_pill(message or "Failed", "error")

    # ------------------------------------------------------------------
    # Pill helper (called by MainWindow)
    # ------------------------------------------------------------------

    def _set_pill(self, text: str, state: str) -> None:
        """Update the pill label text and QSS state, then re-polish."""
        self._status_pill.setText(text)
        self._status_pill.setProperty("state", state)
        self._status_pill.style().unpolish(self._status_pill)
        self._status_pill.style().polish(self._status_pill)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _update_percentage(self) -> None:
        if self._total_steps <= 0:
            self._progress_bar.setValue(0)
            self._percent_label.setText("0%")
            return
        pct = int((self._completed_steps / self._total_steps) * 100)
        pct = max(0, min(100, pct))
        self._progress_bar.setValue(pct)
        self._percent_label.setText(f"{pct}%")

    @Slot()
    def _tick(self) -> None:
        if self._start_time is None:
            return
        elapsed = int(time.monotonic() - self._start_time)
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            self._elapsed_label.setText(
                f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}"
            )
        else:
            self._elapsed_label.setText(f"Elapsed: {minutes:02d}:{seconds:02d}")
