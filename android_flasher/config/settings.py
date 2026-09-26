"""Typed configuration models for Android Flasher.

Loads and validates `config.yaml`. Never contains device-specific
flashing rules — those belong in profile data, not code.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import yaml


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

@dataclass
class ApplicationSettings:
    name: str = "Android Flasher"
    version: str = "2.0.0-phase4"
    development_mode: bool = False


@dataclass
class LoggingSettings:
    level: str = "INFO"
    console: bool = True
    file: bool = True
    session_directory: str = "logs/sessions"
    error_directory: str = "logs/errors"
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 5
    json_sessions: bool = True


@dataclass
class TimeoutSettings:
    adb: int = 30
    fastboot: int = 60
    getprop: int = 20
    version_check: int = 15
    flash: int = 900
    verification: int = 120
    reboot: int = 60

    def for_operation(self, name: str) -> int:
        """Return the timeout for a named operation, with a safe default."""
        return int(getattr(self, name, self.adb))


@dataclass
class PlatformToolsSettings:
    search_paths: list[str] = field(default_factory=lambda: [
        "platform-tools",
        "platform-tools/bin",
        "platform_tools",
    ])
    executable_names: dict[str, str] = field(default_factory=lambda: {
        "adb": "adb",
        "fastboot": "fastboot",
    })
    allow_system_path: bool = True
    allow_bundled: bool = True


@dataclass
class SafetySettings:
    """Safety controls enforced across the application.

    These defaults are intentionally conservative. Enabling flashing
    requires an explicit opt-in via ``allow_flash``. Phase 4 keeps all
    destructive operations gated behind user confirmation and the
    risk engine.
    """

    require_confirmation: bool = True
    require_compatibility_check: bool = True
    require_bootloader_check: bool = True
    require_hash_verification: bool = True

    # Destructive permissions.
    allow_flash: bool = False
    allow_erase: bool = False
    allow_format: bool = False
    allow_unlock: bool = False
    allow_wipe: bool = False
    allow_set_active: bool = False
    allow_reboot: bool = True

    # Phase 1 read-only flag. When True, no destructive operation may run
    # regardless of other settings. This is intentionally defaulted to
    # True so that the application stays in a safe state until the user
    # explicitly disables it.
    phase1_read_only: bool = True

    # Compatibility gating.
    allow_unknown_compatibility: bool = False
    allow_likely_compatibility: bool = True

    # Risk gating.
    max_auto_risk_level: str = "LOW"      # LOW | MEDIUM | HIGH | CRITICAL
    require_confirmation_for_medium: bool = True
    require_confirmation_for_high: bool = True
    require_confirmation_for_critical: bool = True
    block_critical: bool = True

    # Transport / capability gating.
    allow_fastbootd_mode_switch: bool = True
    allow_ab_slot_change: bool = False
    require_serial_match: bool = True

    # Timeouts and execution.
    cancel_grace_seconds: int = 3
    max_output_bytes: int = 4 * 1024 * 1024


@dataclass
class DeviceSettings:
    poll_interval_ms: int = 2000
    auto_refresh: bool = True


@dataclass
class FirmwareSettings:
    """Configuration for firmware analysis."""

    compute_hashes: bool = True
    hash_algorithm: str = "sha256"  # "sha256" | "sha512" | "both"
    max_hash_bytes: int = 0         # 0 = unlimited
    allow_img: bool = True
    allow_zip: bool = True
    allow_payload: bool = True
    allow_sparse: bool = True
    max_archive_entries: int = 10000
    analyze_zip_members: bool = True
    profiles_root: str = "profiles"


@dataclass
class PartitionSettings:
    """Configuration for partition modeling."""

    include_inferred: bool = True
    warn_on_extra_firmware_partitions: bool = True
    dynamic_partition_names: list[str] = field(default_factory=lambda: [
        "system",
        "system_ext",
        "product",
        "vendor",
        "odm",
    ])


@dataclass
class FlashSettings:
    """Configuration for the flash planner and executor.

    These values control how the planner produces steps, how the
    executor runs commands, and how verification is performed. None of
    them enable destructive behaviour on their own; destructive
    behaviour still requires ``SafetySettings.allow_flash`` and the
    user-facing confirmation flow.
    """

    plan_max_steps: int = 64
    step_timeout_seconds: int = 900
    per_step_output_limit: int = 65536
    allow_extraction_for_factory_zip: bool = False
    factory_zip_extraction_root: str = "firmware/incoming"
    allow_fastboot_update: bool = True
    allow_slot_switch: bool = False
    allow_avb_disable: bool = False
    require_integrity_check: bool = True
    verify_after_each_step: bool = True
    verify_after_operation: bool = True
    reboot_after_flash: bool = False
    preserve_logs: bool = True


@dataclass
class UISettings:
    """User interface preferences."""

    theme: str = "dark"          # "dark" | "light" | "system"
    window_width: int = 1400
    window_height: int = 900
    font_size: int = 10
    show_advanced: bool = False
    confirm_on_close: bool = True
    remember_geometry: bool = True


# ---------------------------------------------------------------------------
# Root settings model
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    application: ApplicationSettings = field(default_factory=ApplicationSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    timeouts: TimeoutSettings = field(default_factory=TimeoutSettings)
    platform_tools: PlatformToolsSettings = field(default_factory=PlatformToolsSettings)
    safety: SafetySettings = field(default_factory=SafetySettings)
    device: DeviceSettings = field(default_factory=DeviceSettings)
    firmware: FirmwareSettings = field(default_factory=FirmwareSettings)
    partitions: PartitionSettings = field(default_factory=PartitionSettings)
    flash: FlashSettings = field(default_factory=FlashSettings)
    ui: UISettings = field(default_factory=UISettings)

    # Where the config was loaded from (not serialized).
    source_path: Optional[Path] = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "Settings":
        """Load settings from a YAML file.

        Missing file or missing sections fall back to safe defaults.
        """
        data: dict[str, Any] = {}
        if path and Path(path).is_file():
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    loaded = yaml.safe_load(handle) or {}
                if isinstance(loaded, dict):
                    data = loaded
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

        settings = cls(
            application=_build(ApplicationSettings, data.get("application")),
            logging=_build(LoggingSettings, data.get("logging")),
            timeouts=_build(TimeoutSettings, data.get("timeouts")),
            platform_tools=_build(PlatformToolsSettings, data.get("platform_tools")),
            safety=_build(SafetySettings, data.get("safety")),
            device=_build(DeviceSettings, data.get("device")),
            firmware=_build(FirmwareSettings, data.get("firmware")),
            partitions=_build(PartitionSettings, data.get("partitions")),
            flash=_build(FlashSettings, data.get("flash")),
            ui=_build(UISettings, data.get("ui")),
        )
        settings.source_path = Path(path) if path else None
        return settings

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "application": asdict(self.application),
            "logging": asdict(self.logging),
            "timeouts": asdict(self.timeouts),
            "platform_tools": asdict(self.platform_tools),
            "safety": asdict(self.safety),
            "device": asdict(self.device),
            "firmware": asdict(self.firmware),
            "partitions": asdict(self.partitions),
            "flash": asdict(self.flash),
            "ui": asdict(self.ui),
        }


def _build(model: type, payload: Any) -> Any:
    """Build a dataclass instance from a mapping, ignoring unknown keys."""
    if not isinstance(payload, dict):
        return model()
    valid_keys = {f.name for f in model.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {k: v for k, v in payload.items() if k in valid_keys}
    return model(**filtered)
