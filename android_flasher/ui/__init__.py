"""PySide6 user interface for Android Flasher (Phase 4)."""

from android_flasher.ui.command_panel import CommandPanel
from android_flasher.ui.compatibility_panel import CompatibilityPanel
from android_flasher.ui.device_panel import DevicePanel
from android_flasher.ui.dialogs import (
    TextDetailsDialog,
    show_error,
    show_information,
    show_warning,
    show_confirmation,
)
from android_flasher.ui.flash_panel import FlashPanel
from android_flasher.ui.firmware_panel import FirmwarePanel
from android_flasher.ui.log_panel import LogPanel
from android_flasher.ui.partition_panel import PartitionPanel
from android_flasher.ui.progress_panel import ProgressPanel
from android_flasher.ui.themes import ThemeManager, apply_theme

__all__ = [
    "CommandPanel",
    "CompatibilityPanel",
    "DevicePanel",
    "FlashPanel",
    "FirmwarePanel",
    "LogPanel",
    "PartitionPanel",
    "ProgressPanel",
    "TextDetailsDialog",
    "show_error",
    "show_information",
    "show_warning",
    "show_confirmation",
    "ThemeManager",
    "apply_theme",
]
