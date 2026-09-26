"""Permission helpers."""

from __future__ import annotations

import os
from pathlib import Path


def is_executable(path: Path) -> bool:
    path = Path(path)
    return path.is_file() and os.access(path, os.X_OK)


def is_readable(path: Path) -> bool:
    path = Path(path)
    return path.is_file() and os.access(path, os.R_OK)
