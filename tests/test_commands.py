"""Tests for command construction and executor safety."""

from __future__ import annotations

from pathlib import Path

from android_flasher.core.command_builder import CommandBuilder
from android_flasher.core.command_executor import (
    CommandExecutor,
    ExecutionStatus,
)
from android_flasher.core.command_builder import CommandSpec


def test_builder_never_produces_a_shell_string() -> None:
    builder = CommandBuilder(Path("/tmp/fastboot"))
    spec = builder.build_getvar("product")
    assert isinstance(spec.argv, list)
    assert all(isinstance(arg, str) for arg in spec.argv)


def test_executor_empty_argv_is_skipped() -> None:
    executor = CommandExecutor()
    result = executor.execute(CommandSpec(argv=[], transport="none"))
    assert result.status == ExecutionStatus.SKIPPED


def test_executor_uses_shell_false(monkeypatch) -> None:
    captured = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.stdout = None
            self.stderr = None
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    import android_flasher.core.command_executor as ce
    monkeypatch.setattr(ce.subprocess, "Popen", FakePopen)

    executor = CommandExecutor()
    executor.execute(CommandSpec(argv=["/tmp/fastboot", "devices"], transport="fastboot"))
    assert captured["kwargs"].get("shell") is False
