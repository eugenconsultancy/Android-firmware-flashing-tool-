"""Filesystem helpers.

Provides directory helpers, human-readable size formatting, and the
path-resolution helpers used by the platform tools locator
(``is_executable``, ``which``, ``executable_names``).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def ensure_directory(path: Path) -> Path:
    """Create a directory (and parents) if it does not exist."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def human_size(size: Optional[int]) -> str:
    """Convert a byte count into a human-readable string."""
    if size is None:
        return "—"
    try:
        value = float(size)
    except (TypeError, ValueError):
        return str(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{size}"


def safe_filename(name: str) -> str:
    """Return a filesystem-safe version of ``name``."""
    forbidden = '<>:"/\\|?*'
    result = "".join("_" if c in forbidden else c for c in name)
    return result.strip() or "unnamed"


def is_executable(path: Path) -> bool:
    """Return True if ``path`` is an executable file."""
    path = Path(path)
    if not path.is_file():
        return False
    if sys.platform.startswith("win"):
        return path.suffix.lower() in (".exe", ".bat", ".cmd", ".com") or os.access(
            path, os.X_OK
        )
    return os.access(path, os.X_OK)


def which(name: str, *, extra_path: Optional[Path] = None) -> Optional[Path]:
    """Locate an executable.

    Searches ``extra_path`` first (if provided), then PATH.
    Returns a ``Path`` or ``None``.
    """
    if extra_path is not None:
        candidate = Path(extra_path) / name
        if is_executable(candidate):
            return candidate
        if sys.platform.startswith("win") and not name.lower().endswith(".exe"):
            for suffix in (".exe", ".bat", ".cmd"):
                candidate = Path(extra_path) / f"{name}{suffix}"
                if is_executable(candidate):
                    return candidate

    found = shutil.which(name)
    if found:
        return Path(found)
    if sys.platform.startswith("win") and not name.lower().endswith(".exe"):
        for suffix in (".exe", ".bat", ".cmd"):
            found = shutil.which(f"{name}{suffix}")
            if found:
                return Path(found)
    return None


def executable_names(base: str) -> list[str]:
    """Return the plausible executable file names for ``base``.

    On Windows this includes ``base.exe``, ``base.bat`` and ``base.cmd``.
    On other platforms it returns just ``base``.
    """
    if sys.platform.startswith("win"):
        return [f"{base}.exe", f"{base}.bat", f"{base}.cmd", base]
    return [base]
