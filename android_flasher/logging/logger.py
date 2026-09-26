"""Application logger.

Deliberately does not import from ``android_flasher.config`` at module
load time so that the logging package can be imported by the config
package without creating a circular import.

``configure_logging`` accepts an optional ``settings`` object as its
first positional argument (matching the call in ``app.py``). If the
caller does not supply ``settings``, the function loads ``config.yaml``
from ``project_root`` lazily and falls back to safe defaults if that
fails.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


_LOGGER_NAMESPACE = "android_flasher"
_configured = False


def get_logger(name: str = _LOGGER_NAMESPACE) -> logging.Logger:
    """Return a namespaced logger.

    All application loggers live under the ``android_flasher``
    namespace so that a single handler configuration applies to all of
    them.
    """
    if name == _LOGGER_NAMESPACE or name.startswith(f"{_LOGGER_NAMESPACE}."):
        full_name = name
    else:
        full_name = f"{_LOGGER_NAMESPACE}.{name}"
    return logging.getLogger(full_name)


def configure_logging(
    settings: object = None,
    *,
    level: str = "INFO",
    console: bool = True,
    file: bool = True,
    session_directory: Optional[str] = None,
    error_directory: Optional[str] = None,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
    project_root: Optional[Path] = None,
) -> None:
    """Configure logging for the application.

    ``settings`` may be supplied as the first positional argument (a
    ``Settings`` instance). If it is ``None``, ``config.yaml`` is loaded
    lazily from ``project_root``; if that also fails, defaults are used.

    Explicit keyword arguments always override values drawn from
    ``settings``.
    """
    global _configured
    if _configured:
        return

    # If no settings object was supplied, try to build one lazily.
    if settings is None:
        try:
            from android_flasher.config.settings import Settings  # noqa: WPS433
            config_path = (Path(project_root) if project_root else Path.cwd()) / "config.yaml"
            settings = Settings.load(config_path)
        except Exception:  # noqa: BLE001 - fall back to defaults
            settings = None

    if settings is not None:
        log_cfg = getattr(settings, "logging", None)
        if log_cfg is not None:
            level = getattr(log_cfg, "level", level)
            console = getattr(log_cfg, "console", console)
            file = getattr(log_cfg, "file", file)
            session_directory = getattr(log_cfg, "session_directory", session_directory)
            error_directory = getattr(log_cfg, "error_directory", error_directory)
            max_bytes = getattr(log_cfg, "max_bytes", max_bytes)
            backup_count = getattr(log_cfg, "backup_count", backup_count)

    root = logging.getLogger(_LOGGER_NAMESPACE)
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    root.propagate = False

    # Clear any pre-existing handlers so repeated calls do not stack.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console:
        console_handler = logging.StreamHandler(stream=sys.stdout)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    if file:
        base = Path(project_root) if project_root else Path.cwd()
        log_dir = base / (session_directory or "logs/sessions")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / "android_flasher.log",
                maxBytes=int(max_bytes),
                backupCount=int(backup_count),
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            # File logging is best-effort. Console logging still works.
            pass

        if error_directory:
            err_dir = base / error_directory
            try:
                err_dir.mkdir(parents=True, exist_ok=True)
                error_handler = logging.handlers.RotatingFileHandler(
                    err_dir / "errors.log",
                    maxBytes=int(max_bytes),
                    backupCount=int(backup_count),
                    encoding="utf-8",
                )
                error_handler.setLevel(logging.ERROR)
                error_handler.setFormatter(formatter)
                root.addHandler(error_handler)
            except OSError:
                pass

    _configured = True
