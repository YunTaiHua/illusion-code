"""Shared shell and subprocess helpers."""

from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from illusion.config import Settings, load_settings
from illusion.platforms import PlatformName, get_platform
from illusion.sandbox import wrap_command_for_sandbox


def resolve_shell_command(
    command: str,
    *,
    platform_name: PlatformName | None = None,
) -> list[str]:
    """Return argv for the best available shell on the current platform."""
    resolved_platform = platform_name or get_platform()
    if resolved_platform == "windows":
        bash = _resolve_windows_bash()
        if bash:
            return [bash, "-lc", command]
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell:
            return [powershell, "-NoLogo", "-NoProfile", "-Command", command]
        return [shutil.which("cmd.exe") or "cmd.exe", "/d", "/s", "/c", command]

    bash = shutil.which("bash")
    if bash:
        return [bash, "-lc", command]
    shell = shutil.which("sh") or os.environ.get("SHELL") or "/bin/sh"
    return [shell, "-lc", command]


async def create_shell_subprocess(
    command: str,
    *,
    cwd: str | Path,
    settings: Settings | None = None,
    stdin: int | None = None,
    stdout: int | None = None,
    stderr: int | None = None,
    env: Mapping[str, str] | None = None,
) -> asyncio.subprocess.Process:
    """Spawn a shell command with platform-aware shell selection and sandboxing."""
    resolved_settings = settings or load_settings()
    argv = resolve_shell_command(command)
    argv, cleanup_path = wrap_command_for_sandbox(argv, settings=resolved_settings)

    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(Path(cwd).resolve()),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=dict(env) if env is not None else None,
        )
    except Exception:
        if cleanup_path is not None:
            cleanup_path.unlink(missing_ok=True)
        raise

    if cleanup_path is not None:
        asyncio.create_task(_cleanup_after_exit(process, cleanup_path))
    return process


async def _cleanup_after_exit(process: asyncio.subprocess.Process, cleanup_path: Path) -> None:
    try:
        await process.wait()
    finally:
        cleanup_path.unlink(missing_ok=True)


def _resolve_windows_bash() -> str | None:
    """Resolve a usable bash executable on Windows.

    Ignore the legacy Windows system shim at C:\\Windows\\System32\\bash.exe,
    which may fail or emit unreadable output on machines without WSL setup.

    Resolution order:
    1. ILLUSION_CODE_GIT_BASH_PATH environment variable override
    2. bash found via PATH (excluding the system32 shim)
    3. bash resolved from the git executable location
    4. bash found in well-known Git for Windows install paths
    """
    # 1. Explicit override via environment variable
    env_bash = os.environ.get("ILLUSION_CODE_GIT_BASH_PATH")
    if env_bash and Path(env_bash).exists():
        return env_bash

    # 2. bash on PATH (but skip the legacy system32 shim)
    bash = shutil.which("bash")
    if bash and not _is_windows_bash_shim(bash):
        return bash

    # 3. Resolve bash from the git executable location
    git_path = shutil.which("git")
    if git_path:
        # git.exe is typically at <Git-Root>\cmd\git.exe or <Git-Root>\bin\git.exe
        # bash.exe lives at <Git-Root>\bin\bash.exe
        git_root = Path(git_path).resolve().parent.parent
        bash_via_git = git_root / "bin" / "bash.exe"
        if bash_via_git.exists():
            return str(bash_via_git)

    # 4. Search well-known Git for Windows installation paths
    for candidate in _windows_git_bash_candidates():
        if candidate.exists():
            return str(candidate)

    return None


def _windows_git_bash_candidates() -> list[Path]:
    roots: list[str] = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        value = os.environ.get(key)
        if value:
            roots.append(value)

    candidates: list[Path] = []
    for root in roots:
        base = Path(root)
        candidates.append(base / "Git" / "bin" / "bash.exe")
        candidates.append(base / "Git" / "usr" / "bin" / "bash.exe")
        candidates.append(base / "Programs" / "Git" / "bin" / "bash.exe")
        candidates.append(base / "Programs" / "Git" / "usr" / "bin" / "bash.exe")
    return candidates


def _is_windows_bash_shim(path: str) -> bool:
    normalized = path.replace("/", "\\").lower()
    return normalized.endswith("\\windows\\system32\\bash.exe")
