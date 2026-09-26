"""UI smoke tests.

These tests use pytest-qt to instantiate panels in a headless way.
They do not require a physical device: they only verify that panels
construct, accept data, and clear without errors.

If pytest-qt is not available, the tests are skipped.
"""

from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication
    _HAS_QT = True
except Exception:  # noqa: BLE001 - defensive
    _HAS_QT = False


pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PySide6 not available")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


def test_device_panel_constructs(app):
    from android_flasher.ui.device_panel import DevicePanel
    panel = DevicePanel()
    panel.update_identity(None)
    panel.clear()


def test_firmware_panel_constructs(app):
    from android_flasher.ui.firmware_panel import FirmwarePanel
    panel = FirmwarePanel()
    panel.update_package(None)
    panel.clear()


def test_compatibility_panel_constructs(app):
    from android_flasher.ui.compatibility_panel import CompatibilityPanel
    panel = CompatibilityPanel()
    panel.update_result(None)
    panel.clear()


def test_partition_panel_constructs(app):
    from android_flasher.ui.partition_panel import PartitionPanel
    panel = PartitionPanel()
    panel.update_analysis(None)
    panel.clear()


def test_flash_panel_constructs(app):
    from android_flasher.ui.flash_panel import FlashPanel
    panel = FlashPanel()
    panel.set_plan(None)
    panel.clear()
    panel.set_execution_in_progress(True)
    panel.set_execution_in_progress(False)


def test_command_panel_constructs(app):
    from android_flasher.ui.command_panel import CommandPanel
    panel = CommandPanel()
    panel.set_plan(None)
    panel.clear()


def test_progress_panel_constructs(app):
    from android_flasher.ui.progress_panel import ProgressPanel
    panel = ProgressPanel()
    panel.start_busy()
    panel.set_status("testing")
    panel.stop_busy()
    panel.start_steps(4)
    panel.mark_step_completed()
    panel.finish()
    panel.reset()


def test_log_panel_constructs(app):
    from android_flasher.ui.log_panel import LogPanel
    panel = LogPanel()
    panel.append("hello")
    panel.append_warning("warn")
    panel.append_error("error")
    assert "hello" in panel.to_text()
    panel.clear()


def test_theme_apply(app):
    from android_flasher.ui.themes import apply_theme, ThemeName
    manager = apply_theme(app, ThemeName.DARK.value)
    assert manager.current in (ThemeName.DARK,)
    manager.apply(app, ThemeName.LIGHT)
    assert manager.current == ThemeName.LIGHT
