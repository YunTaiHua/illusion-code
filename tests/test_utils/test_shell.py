"""Tests for shell resolution helpers."""

from __future__ import annotations

from illusion.utils.shell import (
    _is_windows_bash_shim,
    _resolve_windows_bash,
    resolve_shell_command,
)


def test_resolve_shell_command_prefers_bash_on_linux(monkeypatch):
    monkeypatch.setattr(
        "illusion.utils.shell.shutil.which",
        lambda name: "/usr/bin/bash" if name == "bash" else None,
    )

    command = resolve_shell_command("echo hi", platform_name="linux")

    assert command == ["/usr/bin/bash", "-lc", "echo hi"]


def test_resolve_shell_command_uses_powershell_on_windows(monkeypatch):
    def fake_which(name: str) -> str | None:
        mapping = {
            "pwsh": "C:/Program Files/PowerShell/7/pwsh.exe",
        }
        return mapping.get(name)

    monkeypatch.setattr("illusion.utils.shell.shutil.which", fake_which)

    command = resolve_shell_command("Write-Output hi", platform_name="windows")

    assert command == [
        "C:/Program Files/PowerShell/7/pwsh.exe",
        "-NoLogo",
        "-NoProfile",
        "-Command",
        "Write-Output hi",
    ]


def test_resolve_shell_command_ignores_windows_bash_shim(monkeypatch):
    def fake_which(name: str) -> str | None:
        mapping = {
            "bash": r"C:\Windows\System32\bash.exe",
            "powershell": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        }
        return mapping.get(name)

    monkeypatch.setattr("illusion.utils.shell.shutil.which", fake_which)

    command = resolve_shell_command("echo hi", platform_name="windows")

    assert command == [
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-Command",
        "echo hi",
    ]


def test_resolve_windows_bash_uses_env_override(monkeypatch, tmp_path):
    """CLAUDE_CODE_GIT_BASH_PATH takes priority over all other resolution."""
    fake_bash = tmp_path / "bash.exe"
    fake_bash.write_text("fake")
    monkeypatch.setenv("CLAUDE_CODE_GIT_BASH_PATH", str(fake_bash))

    assert _resolve_windows_bash() == str(fake_bash)


def test_resolve_windows_bash_finds_bash_via_git(monkeypatch, tmp_path):
    """When bash isn't on PATH, resolve it from the git executable location."""
    # Set up a fake git install tree: <root>/cmd/git.exe, <root>/bin/bash.exe
    git_root = tmp_path / "GitInstall"
    cmd_dir = git_root / "cmd"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "git.exe").write_text("fake")

    bin_dir = git_root / "bin"
    bin_dir.mkdir()
    (bin_dir / "bash.exe").write_text("fake")

    def fake_which(name: str) -> str | None:
        if name == "bash":
            return None  # bash not directly on PATH
        if name == "git":
            return str(cmd_dir / "git.exe")
        return None

    monkeypatch.setattr("illusion.utils.shell.shutil.which", fake_which)
    # Ensure env override is not set
    monkeypatch.delenv("CLAUDE_CODE_GIT_BASH_PATH", raising=False)

    result = _resolve_windows_bash()
    assert result is not None
    assert result.endswith("bash.exe")
    assert "GitInstall" in result


def test_is_windows_bash_shim():
    assert _is_windows_bash_shim(r"C:\Windows\System32\bash.exe") is True
    assert _is_windows_bash_shim(r"C:\WINDOWS\SYSTEM32\BASH.EXE") is True
    assert _is_windows_bash_shim(r"D:\Git\bin\bash.exe") is False
    assert _is_windows_bash_shim(r"C:\Program Files\Git\usr\bin\bash.exe") is False
