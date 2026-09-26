"""Logging package.

Only the logger module is eagerly re-exported. Session and audit
helpers are lazy so that importing ``android_flasher.logging`` never
triggers a circular import through the config package.
"""

from __future__ import annotations

from typing import Any


from android_flasher.logging.logger import (  # noqa: E402
    configure_logging,
    get_logger,
)


_LAZY_EXPORTS = {
    "AuditRecorder": ("android_flasher.logging.audit", "AuditRecorder"),
    "SessionRecorder": ("android_flasher.logging.session", "SessionRecorder"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'android_flasher.logging' has no attribute {name!r}")
    import importlib
    module = importlib.import_module(target[0])
    return getattr(module, target[1])


__all__ = [
    "configure_logging",
    "get_logger",
    "AuditRecorder",
    "SessionRecorder",
]
