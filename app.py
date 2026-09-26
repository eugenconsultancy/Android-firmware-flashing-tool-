"""Android Flasher — application entry point.

Loads configuration, configures logging, discovers platform tools,
starts a session recorder, applies the theme, and launches the
PySide6 main window.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from android_flasher.config.settings import Settings
from android_flasher.logging.logger import configure_logging, get_logger
from android_flasher.logging.session import SessionRecorder
from android_flasher.platform_tools.manager import PlatformToolManager
from android_flasher.ui.main_window import MainWindow
from android_flasher.ui.themes import apply_theme
from android_flasher.version import __version__


def _project_root() -> Path:
    """Return the directory containing app.py."""
    return Path(__file__).resolve().parent


def main() -> int:
    root = _project_root()
    config_path = root / "config.yaml"

    settings = Settings.load(config_path)

    # ``configure_logging`` accepts the settings object as its first
    # positional argument. Explicit keyword arguments would override
    # settings-derived values; here we let the settings file drive
    # logging configuration.
    configure_logging(settings, project_root=root)

    log = get_logger(__name__)
    log.info("Starting Android Flasher v%s (Phase 4).", __version__)

    session = SessionRecorder.start(root / settings.logging.session_directory)
    session.record("application_start", {"version": __version__})

    tool_manager = PlatformToolManager(settings=settings, project_root=root)
    try:
        tool_manager.discover()
    except Exception as exc:  # noqa: BLE001 - defensive
        log.warning("Platform tool discovery failed: %s", exc)

    app = QApplication(sys.argv)
    app.setApplicationName(settings.application.name)
    app.setApplicationVersion(__version__)

    theme_manager = apply_theme(app, settings.ui.theme)

    window = MainWindow(
        settings=settings,
        tool_manager=tool_manager,
        session=session,
        project_root=root,
        theme_manager=theme_manager,
    )
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
