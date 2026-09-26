"""Main application window (Phase 4, production UI) — redesigned layout.

Wires the panels to the engine.  The window never constructs raw
fastboot or adb commands; all command construction happens in the
engine.  All destructive execution passes through the Flasher facade,
which enforces preflight, risk assessment, and confirmation.

The layout is organised as five fixed regions:

    1. Menu bar (unchanged).
    2. Toolbar card — action buttons (left) + app identity + live status
       pill (right).  Fixed height, full width.
    3. Platform tools banner — single-row tool report.  Fixed height.
    4. Main splitter — left column (device + firmware panels) | right
       column (compact progress row + full-height tab widget).
       Region 4 stretches to fill all remaining vertical space.
    5. Status bar — scrolling message (left) + "Last update" clock (right).
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from android_flasher.config.settings import Settings
from android_flasher.core.command_executor import ExecutionResult
from android_flasher.core.flash_engine import ExecutionTrace
from android_flasher.core.flash_plan import FlashPlan, FlashPlanStatus
from android_flasher.core.flasher import Flasher, FlasherRequest
from android_flasher.devices.detection import DeviceDetector, DetectionResult
from android_flasher.devices.fastboot import FastbootClient
from android_flasher.devices.identification import DeviceIdentifier, DeviceIdentity
from android_flasher.firmware.analyzer import AnalysisOptions, FirmwareAnalyzer
from android_flasher.firmware.compatibility import (
    CompatibilityEngine,
    CompatibilityResult,
)
from android_flasher.firmware.package import FirmwarePackage
from android_flasher.logging.logger import get_logger
from android_flasher.logging.session import SessionRecorder
from android_flasher.partitions.manager import PartitionAnalysis, PartitionManager
from android_flasher.platform_tools.manager import PlatformToolManager
from android_flasher.safety.confirmation import (
    ConfirmationBuilder,
    ConfirmationPrompt,
    ConfirmationRequirement,
)
from android_flasher.safety.risk import RiskAssessor
from android_flasher.ui.command_panel import CommandPanel
from android_flasher.ui.compatibility_panel import CompatibilityPanel
from android_flasher.ui.device_panel import DevicePanel
from android_flasher.ui.dialogs import (
    show_error,
    show_information,
    show_warning,
)
from android_flasher.ui.flash_panel import FlashPanel
from android_flasher.ui.firmware_panel import FirmwarePanel
from android_flasher.ui.log_panel import LogPanel
from android_flasher.ui.partition_panel import PartitionPanel
from android_flasher.ui.progress_panel import ProgressPanel
from android_flasher.ui.themes import ThemeManager, ThemeName
from android_flasher.version import __version__

log = get_logger(__name__)

# Default splitter sizes restored by "Reset Layout".
_DEFAULT_SPLITTER_LEFT: int = 420
_DEFAULT_SPLITTER_RIGHT: int = 760


# ---------------------------------------------------------------------------
# Background workers  (unchanged from Phase 3)
# ---------------------------------------------------------------------------


class DetectionWorker(QObject):
    finished = Signal(object, object)   # DetectionResult, DeviceIdentity
    failed = Signal(str)
    log_message = Signal(str)

    def __init__(self, settings: Settings, tool_manager: PlatformToolManager) -> None:
        super().__init__()
        self._settings = settings
        self._tool_manager = tool_manager

    @Slot()
    def run(self) -> None:
        try:
            self.log_message.emit("Detecting devices...")
            detector = DeviceDetector(self._settings, self._tool_manager)
            detection: DetectionResult = detector.detect()
            self.log_message.emit(f"Detection state: {detection.state.value}")
            if detection.message:
                self.log_message.emit(detection.message)

            identifier = DeviceIdentifier(self._settings, self._tool_manager)
            identity: DeviceIdentity = identifier.identify(detection)

            self.finished.emit(detection, identity)
        except Exception as exc:  # noqa: BLE001
            log.exception("Device detection failed")
            self.failed.emit(str(exc))


class FirmwareAnalysisWorker(QObject):
    finished = Signal(object)   # FirmwarePackage
    failed = Signal(str)
    log_message = Signal(str)

    def __init__(self, settings: Settings, project_root: Path, path: Path) -> None:
        super().__init__()
        self._settings = settings
        self._project_root = Path(project_root)
        self._path = Path(path)

    @Slot()
    def run(self) -> None:
        try:
            self.log_message.emit(f"Analyzing firmware: {self._path.name}")
            options = AnalysisOptions(
                compute_hashes=self._settings.firmware.compute_hashes,
                hash_algorithm=self._settings.firmware.hash_algorithm,
                max_hash_bytes=self._settings.firmware.max_hash_bytes,
                inspect_zip_members=self._settings.firmware.analyze_zip_members,
            )
            analyzer = FirmwareAnalyzer(settings=self._settings, options=options)
            package = analyzer.analyze(self._path)
            self.finished.emit(package)
        except Exception as exc:  # noqa: BLE001
            log.exception("Firmware analysis failed")
            self.failed.emit(str(exc))


class CompatibilityWorker(QObject):
    finished = Signal(object, object)   # CompatibilityResult, PartitionAnalysis
    failed = Signal(str)
    log_message = Signal(str)

    def __init__(
        self,
        settings: Settings,
        tool_manager: PlatformToolManager,
        identity: Optional[DeviceIdentity],
        package: Optional[FirmwarePackage],
    ) -> None:
        super().__init__()
        self._settings = settings
        self._tool_manager = tool_manager
        self._identity = identity
        self._package = package

    @Slot()
    def run(self) -> None:
        try:
            self.log_message.emit("Running compatibility analysis...")
            engine = CompatibilityEngine()
            if self._identity is None or self._package is None:
                self.finished.emit(None, None)
                return

            result: CompatibilityResult = engine.compare(
                self._identity, self._package.metadata
            )
            self.log_message.emit(f"Compatibility: {result.status.value}")

            fastboot_client = None
            fastboot_path = self._tool_manager.fastboot_path()
            if fastboot_path is not None:
                fastboot_client = FastbootClient(
                    fastboot_path,
                    timeout=self._settings.timeouts.fastboot,
                )

            partition_manager = PartitionManager()
            analysis: PartitionAnalysis = partition_manager.analyze(
                self._identity,
                self._package.metadata,
                fastboot_client=fastboot_client,
            )

            self.finished.emit(result, analysis)
        except Exception as exc:  # noqa: BLE001
            log.exception("Compatibility analysis failed")
            self.failed.emit(str(exc))


class FlashExecutionWorker(QObject):
    step_started = Signal(int, str)
    step_output = Signal(int, str)
    step_finished = Signal(int, object)
    finished = Signal(object)
    failed = Signal(str)
    log_message = Signal(str)

    def __init__(self, request: FlasherRequest, plan: FlashPlan) -> None:
        super().__init__()
        self._request = request
        self._plan = plan
        self._flasher: Optional[Flasher] = None

    @Slot()
    def run(self) -> None:
        try:
            self._flasher = Flasher(self._request)
            outcome = self._flasher.execute(
                self._plan,
                on_step_start=self._on_step_start,
                on_step_output=self._on_step_output,
                on_step_finish=self._on_step_finish,
            )
            if outcome.refused:
                self.failed.emit(outcome.error or "Execution refused.")
                return
            if outcome.trace is None:
                self.failed.emit(outcome.error or "No execution trace produced.")
                return
            self.finished.emit(outcome.trace)
        except Exception as exc:  # noqa: BLE001
            log.exception("Flash execution failed")
            self.failed.emit(str(exc))

    def _on_step_start(self, index: int, description: str) -> None:
        self.step_started.emit(index, description)
        self.log_message.emit(f"Step {index}: {description}")

    def _on_step_output(self, index: int, line: str) -> None:
        self.step_output.emit(index, line)

    def _on_step_finish(self, index: int, result: ExecutionResult) -> None:
        self.step_finished.emit(index, result)
        self.log_message.emit(
            f"Step {index} finished: {result.status.value} rc={result.returncode}"
        )


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(
        self,
        settings: Settings,
        tool_manager: PlatformToolManager,
        session: SessionRecorder,
        project_root: Path,
        theme_manager: Optional[ThemeManager] = None,
    ) -> None:
        super().__init__()

        # 1. Store settings, tool_manager, session, project_root, theme_manager.
        self._settings = settings
        self._tool_manager = tool_manager
        self._session = session
        self._project_root = Path(project_root)
        self._theme_manager = theme_manager

        # 2. Initialize all Optional state fields.
        self._identity: Optional[DeviceIdentity] = None
        self._detection: Optional[DetectionResult] = None
        self._package: Optional[FirmwarePackage] = None
        self._compatibility: Optional[CompatibilityResult] = None
        self._partition_analysis: Optional[PartitionAnalysis] = None
        self._plan: Optional[FlashPlan] = None
        self._pending_firmware_path: Optional[Path] = None

        # Flash lifecycle state driving the status pill.
        # Values: "idle" | "running" | "done" | "failed"
        self._execution_state: str = "idle"

        # 3. Initialize all worker / thread fields.
        self._detection_thread: Optional[QThread] = None
        self._detection_worker: Optional[DetectionWorker] = None
        self._firmware_thread: Optional[QThread] = None
        self._firmware_worker: Optional[FirmwareAnalysisWorker] = None
        self._compat_thread: Optional[QThread] = None
        self._compat_worker: Optional[CompatibilityWorker] = None
        self._flash_thread: Optional[QThread] = None
        self._flash_worker: Optional[FlashExecutionWorker] = None

        # Splitter stored so Reset Layout can restore default proportions.
        self._main_splitter: Optional[QSplitter] = None

        # 4. Window title and object name for QSS targeting.
        self.setWindowTitle(f"{settings.application.name} v{__version__}")
        self.setObjectName("main_window")

        # 5. Enforce minimum size so the layout never opens below 1280 × 720.
        self.setMinimumSize(1280, 720)

        # 6. Initial window size — clamp settings values to the minimum.
        w = max(settings.ui.window_width or 1400, 1280)
        h = max(settings.ui.window_height or 900, 720)
        self.resize(w, h)

        # 7. Build menu.
        self._build_menu()

        # 8. Build UI.
        self._build_ui()

        # 9. Apply platform tool status to the banner.
        self._apply_platform_tool_status()

        # 10. Set the initial status pill state.
        self._update_status_pill()

        # 11. Startup log banner.
        self._log(
            f"{settings.application.name} v{__version__} started (Phase 4)."
        )

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        # File
        file_menu = menu_bar.addMenu("&File")

        refresh_action = QAction("&Refresh Devices", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.refresh_devices)
        file_menu.addAction(refresh_action)

        select_action = QAction("&Select Firmware...", self)
        select_action.setShortcut(QKeySequence("Ctrl+O"))
        select_action.triggered.connect(self._select_firmware)
        file_menu.addAction(select_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View
        view_menu = menu_bar.addMenu("&View")

        reset_layout_action = QAction("&Reset Layout", self)
        reset_layout_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        reset_layout_action.triggered.connect(self._reset_layout)
        view_menu.addAction(reset_layout_action)

        if self._theme_manager is not None:
            view_menu.addSeparator()

            dark_action = QAction("Dark Theme", self)
            dark_action.triggered.connect(lambda: self._set_theme(ThemeName.DARK))
            view_menu.addAction(dark_action)

            light_action = QAction("Light Theme", self)
            light_action.triggered.connect(lambda: self._set_theme(ThemeName.LIGHT))
            view_menu.addAction(light_action)

            system_action = QAction("System Theme", self)
            system_action.triggered.connect(lambda: self._set_theme(ThemeName.SYSTEM))
            view_menu.addAction(system_action)

        # Help
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    @Slot()
    def _show_about(self) -> None:
        show_information(
            self,
            "About Android Flasher",
            f"Android Flasher v{__version__}\n"
            f"Phase 4 — Production UI, Testing & Packaging\n\n"
            f"By default the application runs in read-only mode. "
            f"Destructive operations require explicit opt-in and user "
            f"confirmation.",
        )

    @Slot()
    def _reset_layout(self) -> None:
        """Restore the main splitter to its default proportions."""
        if self._main_splitter is not None:
            self._main_splitter.setSizes(
                [_DEFAULT_SPLITTER_LEFT, _DEFAULT_SPLITTER_RIGHT]
            )
        self._log("Layout reset to defaults.")

    def _set_theme(self, theme: ThemeName) -> None:
        if self._theme_manager is None:
            return
        app = QApplication.instance()
        if app is None:
            return
        self._theme_manager.apply(app, theme)
        self._log(f"Theme changed to {theme.value}.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 12, 16, 12)
        root_layout.setSpacing(12)

        # Region 2: Toolbar card (fixed height).
        root_layout.addWidget(self._build_toolbar_card())

        # Region 3: Platform tools banner (fixed height).
        root_layout.addWidget(self._build_platform_tools_banner())

        # Region 4: Main splitter — stretches to consume all remaining space.
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.setHandleWidth(8)

        # ---- Left column: device panel + firmware panel ----
        left_container = QWidget(self)
        left_container.setMinimumWidth(380)
        left_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self._device_panel = DevicePanel(left_container)
        self._device_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        left_layout.addWidget(self._device_panel, 1)

        self._firmware_panel = FirmwarePanel(left_container)
        self._firmware_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._firmware_panel.firmware_selected.connect(self._on_firmware_selected)
        left_layout.addWidget(self._firmware_panel, 1)

        self._main_splitter.addWidget(left_container)

        # ---- Right column: compact progress row + full-height tab widget ----
        right_container = QWidget(self)
        right_container.setMinimumWidth(560)
        right_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # Compact progress card — single row, ~64 px, never grows.
        progress_container = QWidget(right_container)
        progress_container.setObjectName("progress_container")
        progress_container.setFixedHeight(64)
        progress_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        pc_layout = QVBoxLayout(progress_container)
        pc_layout.setContentsMargins(4, 4, 4, 4)
        pc_layout.setSpacing(0)
        self._progress_panel = ProgressPanel(progress_container)
        pc_layout.addWidget(self._progress_panel)
        right_layout.addWidget(progress_container)

        # Tab widget — takes all remaining vertical space in the right column.
        self._tabs = QTabWidget(right_container)
        self._tabs.setDocumentMode(True)
        self._tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._compat_panel = CompatibilityPanel(right_container)
        self._compat_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._partition_panel = PartitionPanel(right_container)
        self._partition_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._flash_panel = FlashPanel(right_container)
        self._flash_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._flash_panel.generate_plan_requested.connect(self._on_generate_plan)
        self._flash_panel.execute_plan_requested.connect(self._on_execute_plan)
        self._flash_panel.cancel_execution_requested.connect(self._on_cancel_execution)

        self._command_panel = CommandPanel(right_container)
        self._command_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._log_panel = LogPanel(right_container)
        self._log_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._tabs.addTab(self._compat_panel, "Compatibility")
        self._tabs.addTab(self._partition_panel, "Partitions")
        self._tabs.addTab(self._flash_panel, "Flash Plan")
        self._tabs.addTab(self._command_panel, "Commands")
        self._tabs.addTab(self._log_panel, "Log")
        right_layout.addWidget(self._tabs, 1)

        self._main_splitter.addWidget(right_container)

        # Splitter proportions.
        self._main_splitter.setStretchFactor(0, 2)
        self._main_splitter.setStretchFactor(1, 3)
        self._main_splitter.setSizes([_DEFAULT_SPLITTER_LEFT, _DEFAULT_SPLITTER_RIGHT])

        root_layout.addWidget(self._main_splitter, 1)

        self.setCentralWidget(central)

        # Region 5: Status bar with permanent "Last update" clock on the right.
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready.")

        self._last_update_label = QLabel("", self)
        self._last_update_label.setProperty("role", "muted")
        self._status_bar.addPermanentWidget(self._last_update_label)

    # ------------------------------------------------------------------
    # Toolbar card (Region 2)
    # ------------------------------------------------------------------

    def _build_toolbar_card(self) -> QWidget:
        card = QWidget(self)
        card.setObjectName("toolbar_card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        # Left: action buttons with 8 px internal spacing.
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self._refresh_button = QPushButton("Refresh Devices", card)
        self._refresh_button.clicked.connect(self.refresh_devices)
        button_layout.addWidget(self._refresh_button)

        self._analyze_button = QPushButton("Analyze Firmware", card)
        self._analyze_button.setProperty("kind", "primary")
        self._analyze_button.setEnabled(False)
        self._analyze_button.clicked.connect(self._on_analyze_clicked)
        button_layout.addWidget(self._analyze_button)

        self._compat_button = QPushButton("Run Compatibility", card)
        self._compat_button.setEnabled(False)
        self._compat_button.clicked.connect(self._on_compat_clicked)
        button_layout.addWidget(self._compat_button)

        layout.addLayout(button_layout)
        layout.addStretch(1)

        # Right: app identity block (name + version) followed by the live
        # status pill.
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title_block.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(self._settings.application.name, card)
        title_label.setObjectName("app_title")
        subtitle_label = QLabel(f"v{__version__}", card)
        subtitle_label.setObjectName("app_subtitle")
        title_block.addWidget(title_label)
        title_block.addWidget(subtitle_label)
        layout.addLayout(title_block)

        layout.addSpacing(8)

        # Live status pill — updated by _update_status_pill().
        self._status_pill = QLabel("No Device", card)
        self._status_pill.setProperty("role", "pill")
        self._status_pill.setProperty("state", "idle")
        layout.addWidget(self._status_pill)

        return card

    # ------------------------------------------------------------------
    # Status pill (live)
    # ------------------------------------------------------------------

    def _update_status_pill(self) -> None:
        """Derive the correct pill label and colour-state from current fields.

        Priority (highest first):
          1. Flash execution: running / done / failed.
          2. Flash plan status: BLOCKED / REQUIRES_CONFIRMATION / READY.
          3. Compatibility result status.
          4. Firmware package loaded.
          5. Device identity detected.
          6. Default (no state).
        """
        label: str
        state: str

        if self._execution_state == "running":
            label, state = "Flashing\u2026", "idle"

        elif self._execution_state == "failed":
            label, state = "Failed", "error"

        elif self._execution_state == "done":
            label, state = "Done", "armed"

        elif self._plan is not None:
            plan_status = getattr(self._plan, "status", None)
            status_val: str = (
                plan_status.value
                if plan_status is not None and hasattr(plan_status, "value")
                else str(plan_status or "")
            )
            if status_val == "BLOCKED":
                label, state = "Plan Blocked", "error"
            elif status_val == "REQUIRES_CONFIRMATION":
                label, state = "Confirm to Flash", "readonly"
            else:
                label, state = "Plan Ready", "armed"

        elif self._compatibility is not None:
            compat_status = getattr(self._compatibility, "status", None)
            cs: str = (
                compat_status.value
                if compat_status is not None and hasattr(compat_status, "value")
                else str(compat_status or "")
            )
            if cs in ("CONFIRMED", "LIKELY"):
                label = f"Compatibility {cs}"
                state = "armed"
            elif cs in ("MISMATCH", "BLOCKED"):
                label = f"Compatibility {cs}"
                state = "error"
            else:
                label = f"Compatibility {cs}" if cs else "Compatibility"
                state = "idle"

        elif self._package is not None:
            label, state = "Firmware Ready", "idle"

        elif self._identity is not None:
            label, state = "Device Ready", "idle"

        else:
            label, state = "No Device", "idle"

        self._status_pill.setText(label)
        self._status_pill.setProperty("state", state)
        self._status_pill.style().unpolish(self._status_pill)
        self._status_pill.style().polish(self._status_pill)

    # ------------------------------------------------------------------
    # Platform tools banner (Region 3)
    # ------------------------------------------------------------------

    def _build_platform_tools_banner(self) -> QWidget:
        banner = QWidget(self)
        banner.setObjectName("platform_tools_banner")
        banner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(banner)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title = QLabel("Platform Tools", banner)
        title.setObjectName("platform_tools_banner_title")
        layout.addWidget(title)

        self._tools_label = QLabel("Not checked yet.", banner)
        self._tools_label.setProperty("role", "field-value-mono")
        self._tools_label.setWordWrap(True)
        self._tools_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._tools_label)

        return banner

    def _apply_platform_tool_status(self) -> None:
        report = self._tool_manager.report
        if report is None:
            self._tools_label.setText("Platform tools not discovered.")
            return
        lines: list[str] = []
        for name, tool in report.tools.items():
            if tool.available:
                version = tool.version or "unknown version"
                lines.append(f"{name}: {tool.path}  ({version})")
            else:
                lines.append(
                    f"{name}: NOT FOUND  ({tool.error or 'unavailable'})"
                )
        if not lines:
            lines.append("No platform tools configured.")
        self._tools_label.setText("   \u2022   ".join(lines))

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------

    @Slot()
    def refresh_devices(self) -> None:
        if self._detection_thread is not None and self._detection_thread.isRunning():
            self._log("Detection already in progress.")
            return

        self._refresh_button.setEnabled(False)
        self._progress_panel.start_busy()
        self._progress_panel.set_status("Detecting devices...")
        self._status_bar.showMessage("Detecting devices...")

        self._detection_thread = QThread(self)
        self._detection_worker = DetectionWorker(self._settings, self._tool_manager)
        self._detection_worker.moveToThread(self._detection_thread)

        self._detection_thread.started.connect(self._detection_worker.run)
        self._detection_worker.log_message.connect(self._log)
        self._detection_worker.finished.connect(self._on_detection_finished)
        self._detection_worker.failed.connect(self._on_detection_failed)
        self._detection_worker.finished.connect(self._detection_thread.quit)
        self._detection_worker.failed.connect(self._detection_thread.quit)
        self._detection_thread.finished.connect(self._on_detection_thread_finished)

        self._detection_thread.start()

    @Slot(object, object)
    def _on_detection_finished(
        self,
        detection: DetectionResult,
        identity: DeviceIdentity,
    ) -> None:
        self._identity = identity
        self._detection = detection
        # Fresh detection resets execution state so the pill reflects the
        # new device rather than a stale execution outcome.
        self._execution_state = "idle"

        self._device_panel.update_identity(identity)
        self._progress_panel.stop_busy()
        self._progress_panel.set_status(detection.message or "Detection complete.")
        self._progress_panel._set_pill("Ready", "armed")
        self._status_bar.showMessage(detection.message or "Detection complete.")
        try:
            self._session.record("device_identity", identity.to_dict())
        except Exception:  # noqa: BLE001
            log.exception("Could not record device identity")
        self._refresh_button.setEnabled(True)
        self._update_action_buttons()
        self._update_status_pill()

    @Slot(str)
    def _on_detection_failed(self, message: str) -> None:
        self._progress_panel.stop_busy()
        self._progress_panel.set_status("Detection failed.")
        self._progress_panel.set_error("Failed")
        self._status_bar.showMessage("Detection failed.")
        self._log(f"Detection failed: {message}")
        try:
            self._session.record("detection_error", {"message": message})
        except Exception:  # noqa: BLE001
            log.exception("Could not record detection error")
        self._refresh_button.setEnabled(True)
        self._update_action_buttons()
        self._update_status_pill()
        show_error(
            self,
            "Detection Failed",
            "The application could not detect a device. "
            "See the Log tab for technical details.",
            details=message,
        )

    @Slot()
    def _on_detection_thread_finished(self) -> None:
        if self._detection_thread is not None:
            self._detection_thread.deleteLater()
        if self._detection_worker is not None:
            self._detection_worker.deleteLater()
        self._detection_thread = None
        self._detection_worker = None

    # ------------------------------------------------------------------
    # Firmware selection and analysis
    # ------------------------------------------------------------------

    @Slot()
    def _select_firmware(self) -> None:
        try:
            self._firmware_panel._on_select_clicked()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            log.exception("Could not open firmware file dialog")

    @Slot(object)
    def _on_firmware_selected(self, payload: object) -> None:
        if isinstance(payload, Path):
            self._pending_firmware_path = payload
            self._analyze_button.setEnabled(True)
            self._log(f"Firmware selected: {payload}")

    @Slot()
    def _on_analyze_clicked(self) -> None:
        if self._pending_firmware_path is None:
            self._log("No firmware selected.")
            return

        if self._firmware_thread is not None and self._firmware_thread.isRunning():
            self._log("Firmware analysis already in progress.")
            return

        self._analyze_button.setEnabled(False)
        self._progress_panel.start_busy()
        self._progress_panel.set_status("Analyzing firmware...")
        self._status_bar.showMessage("Analyzing firmware...")

        self._firmware_thread = QThread(self)
        self._firmware_worker = FirmwareAnalysisWorker(
            self._settings, self._project_root, self._pending_firmware_path
        )
        self._firmware_worker.moveToThread(self._firmware_thread)

        self._firmware_thread.started.connect(self._firmware_worker.run)
        self._firmware_worker.log_message.connect(self._log)
        self._firmware_worker.finished.connect(self._on_firmware_finished)
        self._firmware_worker.failed.connect(self._on_firmware_failed)
        self._firmware_worker.finished.connect(self._firmware_thread.quit)
        self._firmware_worker.failed.connect(self._firmware_thread.quit)
        self._firmware_thread.finished.connect(self._on_firmware_thread_finished)

        self._firmware_thread.start()

    @Slot(object)
    def _on_firmware_finished(self, package: FirmwarePackage) -> None:
        self._package = package
        # Fresh firmware analysis resets the execution state.
        self._execution_state = "idle"

        self._firmware_panel.update_package(package)
        self._progress_panel.stop_busy()
        summary = f"Firmware analyzed: {package.metadata.package_type or 'unknown'}"
        self._progress_panel.set_status(summary)
        self._progress_panel._set_pill("Analyzed", "armed")
        self._status_bar.showMessage(summary)
        try:
            self._session.record("firmware_metadata", package.metadata.to_dict())
        except Exception:  # noqa: BLE001
            log.exception("Could not record firmware metadata")
        self._analyze_button.setEnabled(True)
        self._update_action_buttons()
        self._update_status_pill()

    @Slot(str)
    def _on_firmware_failed(self, message: str) -> None:
        self._progress_panel.stop_busy()
        self._progress_panel.set_status("Firmware analysis failed.")
        self._progress_panel.set_error("Failed")
        self._status_bar.showMessage("Firmware analysis failed.")
        self._log(f"Firmware analysis failed: {message}")
        try:
            self._session.record("firmware_error", {"message": message})
        except Exception:  # noqa: BLE001
            log.exception("Could not record firmware error")
        self._analyze_button.setEnabled(True)
        self._update_action_buttons()
        self._update_status_pill()
        show_error(
            self,
            "Firmware Analysis Failed",
            "The firmware file could not be analyzed. "
            "See the Log tab for technical details.",
            details=message,
        )

    @Slot()
    def _on_firmware_thread_finished(self) -> None:
        if self._firmware_thread is not None:
            self._firmware_thread.deleteLater()
        if self._firmware_worker is not None:
            self._firmware_worker.deleteLater()
        self._firmware_thread = None
        self._firmware_worker = None

    # ------------------------------------------------------------------
    # Compatibility
    # ------------------------------------------------------------------

    @Slot()
    def _on_compat_clicked(self) -> None:
        if self._identity is None or self._package is None:
            self._log("Need both a detected device and an analyzed firmware.")
            return

        if self._compat_thread is not None and self._compat_thread.isRunning():
            self._log("Compatibility analysis already in progress.")
            return

        self._compat_button.setEnabled(False)
        self._progress_panel.start_busy()
        self._progress_panel.set_status("Running compatibility analysis...")
        self._status_bar.showMessage("Running compatibility analysis...")

        self._compat_thread = QThread(self)
        self._compat_worker = CompatibilityWorker(
            self._settings,
            self._tool_manager,
            self._identity,
            self._package,
        )
        self._compat_worker.moveToThread(self._compat_thread)

        self._compat_thread.started.connect(self._compat_worker.run)
        self._compat_worker.log_message.connect(self._log)
        self._compat_worker.finished.connect(self._on_compat_finished)
        self._compat_worker.failed.connect(self._on_compat_failed)
        self._compat_worker.finished.connect(self._compat_thread.quit)
        self._compat_worker.failed.connect(self._compat_thread.quit)
        self._compat_thread.finished.connect(self._on_compat_thread_finished)

        self._compat_thread.start()

    @Slot(object, object)
    def _on_compat_finished(
        self,
        result: Optional[CompatibilityResult],
        analysis: Optional[PartitionAnalysis],
    ) -> None:
        self._compatibility = result
        self._partition_analysis = analysis
        # Fresh compatibility result resets the execution state so the pill
        # reflects the new analysis rather than a stale execution outcome.
        self._execution_state = "idle"

        self._compat_panel.update_result(result)
        self._partition_panel.update_analysis(analysis)

        self._progress_panel.stop_busy()
        if result is not None:
            self._progress_panel.set_status(f"Compatibility: {result.status.value}")
            self._progress_panel._set_pill(result.status.value.title(), "idle")
            self._status_bar.showMessage(f"Compatibility: {result.status.value}")
            try:
                self._session.record("compatibility", result.to_dict())
            except Exception:  # noqa: BLE001
                log.exception("Could not record compatibility")
        else:
            self._progress_panel.set_status("Compatibility analysis complete.")
            self._status_bar.showMessage("Compatibility analysis complete.")

        if analysis is not None:
            try:
                self._session.record("partition_analysis", analysis.to_dict())
            except Exception:  # noqa: BLE001
                log.exception("Could not record partition analysis")

        self._compat_button.setEnabled(True)
        self._update_action_buttons()
        self._update_status_pill()

    @Slot(str)
    def _on_compat_failed(self, message: str) -> None:
        self._progress_panel.stop_busy()
        self._progress_panel.set_status("Compatibility analysis failed.")
        self._progress_panel.set_error("Failed")
        self._status_bar.showMessage("Compatibility analysis failed.")
        self._log(f"Compatibility analysis failed: {message}")
        try:
            self._session.record("compatibility_error", {"message": message})
        except Exception:  # noqa: BLE001
            log.exception("Could not record compatibility error")
        self._compat_button.setEnabled(True)
        self._update_action_buttons()
        self._update_status_pill()
        show_error(
            self,
            "Compatibility Analysis Failed",
            "Compatibility could not be evaluated. "
            "See the Log tab for technical details.",
            details=message,
        )

    @Slot()
    def _on_compat_thread_finished(self) -> None:
        if self._compat_thread is not None:
            self._compat_thread.deleteLater()
        if self._compat_worker is not None:
            self._compat_worker.deleteLater()
        self._compat_thread = None
        self._compat_worker = None

    # ------------------------------------------------------------------
    # Flash plan
    # ------------------------------------------------------------------

    @Slot()
    def _on_generate_plan(self) -> None:
        if self._identity is None:
            self._log("No device identified. Cannot generate a plan.")
            return
        if self._package is None:
            self._log("No firmware selected. Cannot generate a plan.")
            return
        if self._compatibility is None:
            self._log("Run compatibility first.")
            return

        fastboot_path = self._tool_manager.fastboot_path()
        if fastboot_path is None:
            self._log("fastboot is not available; cannot generate a plan.")
            return

        request = FlasherRequest(
            settings=self._settings,
            fastboot_path=fastboot_path,
            adb_path=self._tool_manager.adb_path(),
            device=self._identity,
            firmware=self._package,
            compatibility=self._compatibility,
            partition_analysis=self._partition_analysis,
            detection=self._detection,
            bootloader_info=None,
            slot_info=None,
            confirmed=False,
        )
        flasher = Flasher(request)
        plan = flasher.build_plan()

        preflight = flasher.preflight(plan)
        risk = flasher.assess_risk(plan, preflight)
        plan.risk_level = risk.level.value
        plan.risk_reasons = list(risk.reasons)

        self._plan = plan
        # Generating a new plan resets execution state.
        self._execution_state = "idle"

        self._flash_panel.set_plan(plan)
        self._command_panel.set_plan(plan)
        self._tabs.setCurrentWidget(self._flash_panel)

        try:
            self._session.record("flash_plan", plan.to_dict())
        except Exception:  # noqa: BLE001
            log.exception("Could not record flash plan")
        self._log(f"Plan generated: {plan.summary()}")
        self._update_status_pill()

    @Slot()
    def _on_execute_plan(self) -> None:
        if self._plan is None:
            self._log("No plan to execute. Generate a plan first.")
            return

        if self._flash_thread is not None and self._flash_thread.isRunning():
            self._log("Execution already in progress.")
            return

        builder = ConfirmationBuilder(self._settings)
        risk = RiskAssessor().assess(
            plan=self._plan,
            device=self._identity,
            firmware=self._package,
            compatibility=self._compatibility,
            preflight=None,
        )
        prompt = builder.build(
            plan=self._plan,
            risk=risk,
            compatibility=self._compatibility,
        )

        if prompt.requirement == ConfirmationRequirement.BLOCKED:
            show_warning(self, "Blocked", prompt.body)
            self._log(f"Execution refused: {prompt.body}")
            return

        confirmed = False
        if prompt.requirement == ConfirmationRequirement.NONE:
            confirmed = True
        else:
            confirmed = self._ask_confirmation(prompt)

        if not confirmed:
            self._log("Execution cancelled by user.")
            try:
                self._session.record("flash_cancelled", {"reason": "user"})
            except Exception:  # noqa: BLE001
                log.exception("Could not record cancellation")
            return

        fastboot_path = self._tool_manager.fastboot_path()
        if fastboot_path is None:
            self._log("fastboot disappeared.")
            return

        request = FlasherRequest(
            settings=self._settings,
            fastboot_path=fastboot_path,
            adb_path=self._tool_manager.adb_path(),
            device=self._identity,
            firmware=self._package,
            compatibility=self._compatibility,
            partition_analysis=self._partition_analysis,
            detection=self._detection,
            bootloader_info=None,
            slot_info=None,
            confirmed=True,
        )

        # Mark execution as running before the thread starts so the pill
        # updates immediately.
        self._execution_state = "running"
        self._update_status_pill()

        self._flash_panel.set_execution_in_progress(True)
        self._progress_panel.start_steps(len(self._plan.steps))
        self._progress_panel.set_status("Executing flash plan...")
        self._status_bar.showMessage("Executing flash plan...")

        self._flash_thread = QThread(self)
        self._flash_worker = FlashExecutionWorker(request, self._plan)
        self._flash_worker.moveToThread(self._flash_thread)

        self._flash_thread.started.connect(self._flash_worker.run)
        self._flash_worker.log_message.connect(self._log)
        self._flash_worker.step_started.connect(self._on_flash_step_started)
        self._flash_worker.step_output.connect(self._on_flash_step_output)
        self._flash_worker.step_finished.connect(self._on_flash_step_finished)
        self._flash_worker.finished.connect(self._on_flash_finished)
        self._flash_worker.failed.connect(self._on_flash_failed)
        self._flash_worker.finished.connect(self._flash_thread.quit)
        self._flash_worker.failed.connect(self._flash_thread.quit)
        self._flash_thread.finished.connect(self._on_flash_thread_finished)

        self._flash_thread.start()

    @Slot()
    def _on_cancel_execution(self) -> None:
        self._log("Cancellation requested.")
        try:
            self._session.record("cancel_requested", {"time": time.time()})
        except Exception:  # noqa: BLE001
            log.exception("Could not record cancellation request")

    @Slot(int, str)
    def _on_flash_step_started(self, index: int, description: str) -> None:
        self._progress_panel.set_status(f"Step {index}: {description}")
        self._progress_panel.set_operation(description)
        # Re-confirm "Flashing…" in case the pill was updated by a race.
        self._update_status_pill()

    @Slot(int, str)
    def _on_flash_step_output(self, index: int, line: str) -> None:
        if line:
            self._log(f"[step {index}] {line}")

    @Slot(int, object)
    def _on_flash_step_finished(self, index: int, result: ExecutionResult) -> None:
        self._log(
            f"Step {index} finished: {result.status.value} rc={result.returncode}"
        )
        self._progress_panel.mark_step_completed()

    @Slot(object)
    def _on_flash_finished(self, trace: ExecutionTrace) -> None:
        self._execution_state = "done"

        self._flash_panel.set_execution_in_progress(False)
        self._progress_panel.stop_busy()
        self._progress_panel.finish()

        if trace.verification is not None:
            status = trace.verification.status.value
            self._progress_panel.set_status(f"Execution finished: {status}")
            self._status_bar.showMessage(f"Execution finished: {status}")
            self._log(f"Verification: {status}")
            try:
                self._session.record("verification", trace.verification.to_dict())
            except Exception:  # noqa: BLE001
                log.exception("Could not record verification")
        else:
            self._progress_panel.set_status("Execution finished.")
            self._status_bar.showMessage("Execution finished.")

        try:
            self._session.record("execution_trace", trace.to_dict())
        except Exception:  # noqa: BLE001
            log.exception("Could not record execution trace")

        self._update_status_pill()

    @Slot(str)
    def _on_flash_failed(self, message: str) -> None:
        self._execution_state = "failed"

        self._flash_panel.set_execution_in_progress(False)
        self._progress_panel.stop_busy()
        self._progress_panel.set_status("Execution failed.")
        self._progress_panel.set_error("Failed")
        self._status_bar.showMessage("Execution failed.")
        self._log(f"Execution failed: {message}")
        try:
            self._session.record("execution_error", {"message": message})
        except Exception:  # noqa: BLE001
            log.exception("Could not record execution error")

        self._update_status_pill()
        show_error(
            self,
            "Execution Failed",
            "The flash plan failed. The device may be in an intermediate "
            "state. Review the Log tab before retrying.",
            details=message,
        )

    @Slot()
    def _on_flash_thread_finished(self) -> None:
        if self._flash_thread is not None:
            self._flash_thread.deleteLater()
        if self._flash_worker is not None:
            self._flash_worker.deleteLater()
        self._flash_thread = None
        self._flash_worker = None

    # ------------------------------------------------------------------
    # Confirmation dialog
    # ------------------------------------------------------------------

    def _ask_confirmation(self, prompt: ConfirmationPrompt) -> bool:
        text = prompt.body
        if prompt.require_typed_phrase:
            text += (
                f"\n\nThis is an elevated-risk operation. "
                f"Typed acknowledgement phrase: {prompt.require_typed_phrase}"
            )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(prompt.title)
        box.setText(text)
        if prompt.extra_notes:
            box.setDetailedText("\n".join(prompt.extra_notes))
        box.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        result = box.exec()
        return result == QMessageBox.StandardButton.Ok

    # ------------------------------------------------------------------
    # Button enable state
    # ------------------------------------------------------------------

    def _update_action_buttons(self) -> None:
        has_firmware = self._package is not None
        has_device = self._identity is not None
        self._analyze_button.setEnabled(self._pending_firmware_path is not None)
        self._compat_button.setEnabled(has_firmware and has_device)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @Slot(str)
    def _log(self, message: str) -> None:
        if not message:
            return
        self._log_panel.append(message)
        log.info(message)
        # Update the permanent "Last update" clock in the status bar.
        now = datetime.now().strftime("%H:%M:%S")
        self._last_update_label.setText(f"Last update: {now}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        for thread in (
            self._detection_thread,
            self._firmware_thread,
            self._compat_thread,
            self._flash_thread,
        ):
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(2000)

        try:
            self._session.write_summary()
        except Exception:  # noqa: BLE001
            log.exception("Could not write session summary")

        super().closeEvent(event)