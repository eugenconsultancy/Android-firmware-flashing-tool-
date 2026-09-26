"""Hashing helpers.

Provides both a generic ``hash_file`` / ``hash_bytes`` API and the
specific ``hash_file_sha256`` / ``hash_file_sha512`` helpers used by
the firmware analyzer and other phase modules.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional


def hash_bytes(data: bytes, algorithm: str = "sha256") -> str:
    """Return the hex digest of ``data`` using the named algorithm."""
    digest = hashlib.new(algorithm)
    digest.update(data)
    return digest.hexdigest()


def hash_file(
    path: Path,
    algorithm: str = "sha256",
    *,
    chunk_size: int = 1024 * 1024,
    max_bytes: Optional[int] = None,
) -> str:
    """Return the hex digest of a file.

    ``max_bytes`` limits how many bytes are hashed (0 or None = all).
    """
    digest = hashlib.new(algorithm)
    remaining = max_bytes if max_bytes and max_bytes > 0 else None
    with open(path, "rb") as handle:
        while True:
            if remaining is not None:
                to_read = min(chunk_size, remaining)
                if to_read <= 0:
                    break
            else:
                to_read = chunk_size
            chunk = handle.read(to_read)
            if not chunk:
                break
            digest.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return digest.hexdigest()


def hash_file_sha256(path: Path, *, max_bytes: Optional[int] = None) -> str:
    """Return the SHA-256 hex digest of a file."""
    return hash_file(path, "sha256", max_bytes=max_bytes)


def hash_file_sha512(path: Path, *, max_bytes: Optional[int] = None) -> str:
    """Return the SHA-512 hex digest of a file."""
    return hash_file(path, "sha512", max_bytes=max_bytes)


def hash_file_both(path: Path, *, max_bytes: Optional[int] = None) -> dict[str, str]:
    """Return both SHA-256 and SHA-512 hex digests of a file."""
    return {
        "sha256": hash_file_sha256(path, max_bytes=max_bytes),
        "sha512": hash_file_sha512(path, max_bytes=max_bytes),
    }
