"""Tests for sandbox runtime adapter behavior."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from illusion.config.settings import SandboxSettings, Settings
from illusion.sandbox.adapter import (
    SandboxUnavailableError,
    build_sandbox_runtime_config,
    get_sandbox_availability,
    wrap_command_for_sandbox,
)
from illusion.utils.shell import create_shell_subprocess


def test_build_sandbox_runtime_config_maps_settings():
    settings = Settings(
        sandbox=SandboxSettings(
            enabled=True,
            network={"allowed_domains": ["github.com"], "denied_domains": ["example.com"]},
            filesystem={"allow_write": [".", "/tmp"], "deny_read": ["~/.ssh"]},
        )
    )

    config = build_sandbox_runtime_config(settings)

    assert config["network"]["allowedDomains"] == ["github.com"]
    assert config["network"]["deniedDomains"] == ["example.com"]
    assert config["filesystem"]["allowWrite"] == [".", "/tmp"]
    assert config["filesystem"]["denyRead"] == ["~/.ssh"]


def test_sandbox_availability_reports_native_windows_unsupported(monkeypatch):
    settings = Settings(sandbox=SandboxSettings(enabled=True))
    monkeypatch.setattr("illusion.sandbox.adapter.get_platform", lambda: "windows")

    availability = get_sandbox_availability(settings)

    assert availability.available is False
    assert "native Windows" in (availability.reason or "")


def test_wrap_command_for_sandbox_returns_original_when_disabled():
    command, settings_path = wrap_command_for_sandbox(["bash", "-lc", "echo hi"], settings=Settings())
    assert command == ["bash", "-lc", "echo hi"]
    assert settings_path is None


def test_wrap_command_for_sandbox_writes_settings_file(monkeypatch):
    settings = Settings(sandbox=SandboxSettings(enabled=True))

    def fake_which(name: str) -> str | None:
        mapping = {
            "srt": "/usr/local/bin/srt",
            "bwrap": "/usr/bin/bwrap",
        }
        return mapping.get(name)

    monkeypatch.setattr("illusion.sandbox.adapter.get_platform", lambda: "linux")
    monkeypatch.setattr("illusion.sandbox.adapter.shutil.which", fake_which)

    command, settings_path = wrap_command_for_sandbox(["bash", "-lc", "echo hi"], settings=settings)

    assert command[:4] == ["/usr/local/bin/srt", "--settings", str(settings_path), "-c"]
    assert command[4] == "bash -lc 'echo hi'"
    assert settings_path is not None and settings_path.exists()
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["filesystem"]["allowWrite"] == ["."]
    settings_path.unlink(missing_ok=True)


def test_wrap_command_for_sandbox_raises_when_required(monkeypatch):
    settings = Settings(sandbox=SandboxSettings(enabled=True, fail_if_unavailable=True))
    monkeypatch.setattr("illusion.sandbox.adapter.get_platform", lambda: "linux")
    monkeypatch.setattr("illusion.sandbox.adapter.shutil.which", lambda name: None)

    with pytest.raises(SandboxUnavailableError):
        wrap_command_for_sandbox(["bash", "-lc", "echo hi"], settings=settings)


@pytest.mark.skipif(shutil.which("srt") is None or shutil.which("bwrap") is None, reason="Needs local sandbox runtime")
def test_create_shell_subprocess_preserves_exit_code_with_sandbox(monkeypatch):
    import illusion.config.paths as config_paths

    async def _run() -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "settings.json"
            from illusion.config.settings import save_settings

            save_settings(Settings(sandbox=SandboxSettings(enabled=True, fail_if_unavailable=True)), cfg)
            orig = config_paths.get_config_file_path
            monkeypatch.setattr(config_paths, "get_config_file_path", lambda: cfg)
            try:
                process = await create_shell_subprocess(
                    "exit 7",
                    cwd=Path("/home/tangjiabin/IllusionCode-new"),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
            finally:
                monkeypatch.setattr(config_paths, "get_config_file_path", orig)

        assert process.returncode == 7
        assert stdout == b""
        assert stderr == b""

    asyncio.run(_run())
