"""Session recording.

Every application run gets a unique session directory under
``logs/sessions/<timestamp>/``. The session stores structured
artifacts:

    session.json      – top-level metadata and events
    commands.log      – every command that was executed
    device.json       – detected device information
    firmware.json     – firmware metadata
    result.json       – final verification result
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from android_flasher.utils.filesystem import ensure_directory


@dataclass
class SessionRecorder:
    """Records structured events and writes session artifacts."""

    root: Path
    session_id: str
    directory: Path
    events: list[dict] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def start(cls, root: Path) -> "SessionRecorder":
        root = Path(root)
        ensure_directory(root)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_id = stamp
        directory = root / stamp
        counter = 1
        while directory.exists():
            counter += 1
            directory = root / f"{stamp}_{counter}"
            session_id = f"{stamp}_{counter}"
        ensure_directory(directory)
        recorder = cls(root=root, session_id=session_id, directory=directory)
        recorder.record("session_start", {"session_id": session_id})
        return recorder

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, event: str, payload: Any) -> None:
        entry = {
            "time": time.time(),
            "event": event,
            "payload": payload,
        }
        self.events.append(entry)
        self._append_event(entry)

    def record_command(self, argv: list[str], result: Optional[dict] = None) -> None:
        self.record("command", {"argv": list(argv), "result": result})
        self._append_command(argv, result)

    # ------------------------------------------------------------------
    # Artifact writers
    # ------------------------------------------------------------------

    def write_device(self, payload: dict) -> None:
        self._write_json("device.json", payload)

    def write_firmware(self, payload: dict) -> None:
        self._write_json("firmware.json", payload)

    def write_result(self, payload: dict) -> None:
        self._write_json("result.json", payload)

    def write_summary(self) -> None:
        summary = {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": time.time(),
            "events": self.events,
        }
        self._write_json("session.json", summary)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write_json(self, name: str, payload: Any) -> None:
        path = self.directory / name
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, default=str)
        except OSError:
            pass

    def _append_event(self, entry: dict) -> None:
        path = self.directory / "session.jsonl"
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass

    def _append_command(self, argv: list[str], result: Optional[dict]) -> None:
        path = self.directory / "commands.log"
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(f"# {datetime.now().isoformat()}\n")
                handle.write(" ".join(argv) + "\n")
                if result is not None:
                    handle.write(json.dumps(result, default=str) + "\n")
                handle.write("\n")
        except OSError:
            pass
