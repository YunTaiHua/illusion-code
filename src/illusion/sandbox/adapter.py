"""
沙箱运行时适配器模块
==================

本模块实现围绕 srt（sandbox-runtime）CLI 的适配器，提供沙箱执行功能。

主要功能：
    - 检查沙箱可用性
    - 构建沙箱运行时配置
    - 包装命令用于沙箱执行

类说明：
    - SandboxUnavailableError: 当需要沙箱执行但不可用时抛出
    - SandboxAvailability: 当前环境的沙箱运行时可用性
    - build_sandbox_runtime_config: 构建 srt 设置 payload
    - get_sandbox_availability: 获取沙箱可用性状态
    - wrap_command_for_sandbox: 包装命令用于沙箱执行

使用示例：
    >>> from illusion.sandbox import get_sandbox_availability, wrap_command_for_sandbox
    >>> # 检查沙箱可用性
    >>> availability = get_sandbox_availability()
    >>> print(availability.active)  # 是否启用沙箱
    >>> # 包装命令
    >>> wrapped_cmd, settings_path = wrap_command_for_sandbox(["ls", "-la"])
"""

from __future__ import annotations

import json
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from illusion.config import Settings, load_settings
from illusion.platforms import get_platform, get_platform_capabilities


class SandboxUnavailableError(RuntimeError):
    """当需要沙箱执行但不可用时抛出。"""


@dataclass(frozen=True)
class SandboxAvailability:
    """当前环境的沙箱运行时可用性计算结果。"""

    enabled: bool
    available: bool
    reason: str | None = None
    command: str | None = None

    @property
    def active(self) -> bool:
        """返回是否应该对子进程应用沙箱。"""
        return self.enabled and self.available


def build_sandbox_runtime_config(settings: Settings) -> dict[str, Any]:
    """将 IllusionCode 设置转换为 srt 设置 payload。"""
    return {
        "network": {
            "allowedDomains": list(settings.sandbox.network.allowed_domains),
            "deniedDomains": list(settings.sandbox.network.denied_domains),
        },
        "filesystem": {
            "allowRead": list(settings.sandbox.filesystem.allow_read),
            "denyRead": list(settings.sandbox.filesystem.deny_read),
            "allowWrite": list(settings.sandbox.filesystem.allow_write),
            "denyWrite": list(settings.sandbox.filesystem.deny_write),
        },
    }


def get_sandbox_availability(settings: Settings | None = None) -> SandboxAvailability:
    """返回 srt 是否可用于当前运行时。"""
    resolved_settings = settings or load_settings()
    if not resolved_settings.sandbox.enabled:
        return SandboxAvailability(enabled=False, available=False, reason="sandbox is disabled")

    platform_name = get_platform()
    capabilities = get_platform_capabilities(platform_name)
    if not capabilities.supports_sandbox_runtime:
        if platform_name == "windows":
            reason = "sandbox runtime is not supported on native Windows; use WSL for sandboxed execution"
        else:
            reason = f"sandbox runtime is not supported on platform {platform_name}"
        return SandboxAvailability(enabled=True, available=False, reason=reason)

    enabled_platforms = {name.lower() for name in resolved_settings.sandbox.enabled_platforms}
    if enabled_platforms and platform_name not in enabled_platforms:
        return SandboxAvailability(
            enabled=True,
            available=False,
            reason=f"sandbox is disabled for platform {platform_name} by configuration",
        )

    # 检查 srt CLI 是否存在
    srt = shutil.which("srt")
    if not srt:
        return SandboxAvailability(
            enabled=True,
            available=False,
            reason=(
                "sandbox runtime CLI not found; install it with "
                "`npm install -g @anthropic-ai/sandbox-runtime`"
            ),
        )

    # 检查 Linux/WSL 需要的 bwrap
    if platform_name in {"linux", "wsl"} and shutil.which("bwrap") is None:
        return SandboxAvailability(
            enabled=True,
            available=False,
            reason="bubblewrap (`bwrap`) is required for sandbox runtime on Linux/WSL",
            command=srt,
        )

    # 检查 macOS 需要的 sandbox-exec
    if platform_name == "macos" and shutil.which("sandbox-exec") is None:
        return SandboxAvailability(
            enabled=True,
            available=False,
            reason="`sandbox-exec` is required for sandbox runtime on macOS",
            command=srt,
        )

    return SandboxAvailability(enabled=True, available=True, command=srt)


def wrap_command_for_sandbox(
    command: list[str],
    *,
    settings: Settings | None = None,
) -> tuple[list[str], Path | None]:
    """当沙箱激活时用 srt 包装 argv 列表。"""
    resolved_settings = settings or load_settings()
    availability = get_sandbox_availability(resolved_settings)
    if not availability.active:
        if resolved_settings.sandbox.enabled and resolved_settings.sandbox.fail_if_unavailable:
            raise SandboxUnavailableError(availability.reason or "sandbox runtime is unavailable")
        return command, None

    # 写入运行时设置到临时文件
    settings_path = _write_runtime_settings(build_sandbox_runtime_config(resolved_settings))
    # srt argv 形式不能可靠地保留 shell 风格命令（如 bash -lc 'exit 1'）的子进程退出码
    # 构建单个转义命令字符串并通过 -c 传递，以便钩子/工具失败仍能正确传播
    wrapped = [
        availability.command or "srt",
        "--settings",
        str(settings_path),
        "-c",
        shlex.join(command),
    ]
    return wrapped, settings_path


def _write_runtime_settings(payload: dict[str, Any]) -> Path:
    """为一个沙箱子进程持久化临时设置文件。"""
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="illusion-sandbox-",
        suffix=".json",
        delete=False,
    )
    try:
        json.dump(payload, tmp)
        tmp.write("\n")
    finally:
        tmp.close()
    return Path(tmp.name)