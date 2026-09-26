"""Configuration loading and models.

Uses PEP 562 module-level ``__getattr__`` so that submodule imports
are lazy. This avoids the circular import that occurs when
``android_flasher.config.device_profiles`` (which imports the logger)
is loaded eagerly during ``android_flasher.logging.logger``'s own
import.
"""

from __future__ import annotations

from typing import Any


from android_flasher.config.settings import (  # noqa: E402
    ApplicationSettings,
    DeviceSettings,
    FirmwareSettings,
    FlashSettings,
    LoggingSettings,
    PartitionSettings,
    PlatformToolsSettings,
    SafetySettings,
    Settings,
    TimeoutSettings,
    UISettings,
)


_LAZY_EXPORTS = {
    "DeviceProfile": ("android_flasher.config.device_profiles", "DeviceProfile"),
    "DeviceProfileRegistry": (
        "android_flasher.config.device_profiles",
        "DeviceProfileRegistry",
    ),
    "PartitionProfile": ("android_flasher.config.partition_profiles", "PartitionProfile"),
    "PartitionProfileRegistry": (
        "android_flasher.config.partition_profiles",
        "PartitionProfileRegistry",
    ),
    "CommandProfile": ("android_flasher.config.command_profiles", "CommandProfile"),
    "CommandProfileRegistry": (
        "android_flasher.config.command_profiles",
        "CommandProfileRegistry",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'android_flasher.config' has no attribute {name!r}")
    import importlib
    module = importlib.import_module(target[0])
    return getattr(module, target[1])


__all__ = [
    "Settings",
    "ApplicationSettings",
    "DeviceSettings",
    "FirmwareSettings",
    "FlashSettings",
    "LoggingSettings",
    "PartitionSettings",
    "PlatformToolsSettings",
    "SafetySettings",
    "TimeoutSettings",
    "UISettings",
    "DeviceProfile",
    "DeviceProfileRegistry",
    "PartitionProfile",
    "PartitionProfileRegistry",
    "CommandProfile",
    "CommandProfileRegistry",
]
