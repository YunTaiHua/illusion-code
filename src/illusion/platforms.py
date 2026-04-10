"""
平台和功能检测模块
=================

本模块提供平台检测和功能能力查询功能。

主要功能：
    - 检测当前运行平台（macOS、Linux、Windows、WSL）
    - 查询平台支持的功能特性

类型说明：
    - PlatformName: 平台名称字面量类型
    - PlatformCapabilities: 平台功能能力数据类

使用示例：
    >>> from illusion.platforms import get_platform, get_platform_capabilities
    >>> platform = get_platform()
    >>> caps = get_platform_capabilities(platform)
    >>> print(f"支持 POSIX shell: {caps.supports_posix_shell}")
"""

from __future__ import annotations

import os  # 操作系统相关功能
import platform  # 平台信息获取
from dataclasses import dataclass  # 数据类装饰器
from functools import lru_cache  # 缓存装饰器
from typing import Literal, Mapping  # 类型注解

# 平台名称类型定义
PlatformName = Literal["macos", "linux", "windows", "wsl", "unknown"]


@dataclass(frozen=True)
class PlatformCapabilities:
    """平台功能能力数据类
    
    存储影响 shell、swarm 和沙箱决策的平台功能特性。
    
    Attributes:
        name: 平台名称
        supports_posix_shell: 是否支持 POSIX shell（bash、zsh 等）
        supports_native_windows_shell: 是否支持原生 Windows shell（PowerShell、CMD）
        supports_tmux: 是否支持 tmux 会话管理
        supports_swarm_mailbox: 是否支持 swarm 邮箱功能
        supports_sandbox_runtime: 是否支持沙箱运行时
    """

    name: PlatformName  # 平台名称
    supports_posix_shell: bool  # 是否支持 POSIX shell
    supports_native_windows_shell: bool  # 是否支持原生 Windows shell
    supports_tmux: bool  # 是否支持 tmux
    supports_swarm_mailbox: bool  # 是否支持 swarm 邮箱
    supports_sandbox_runtime: bool  # 是否支持沙箱运行时


def detect_platform(
    *,
    system_name: str | None = None,
    release: str | None = None,
    env: Mapping[str, str] | None = None,
) -> PlatformName:
    """检测并返回标准化平台名称
    
    通过检测系统信息判断当前运行平台，支持覆盖参数用于测试。
    
    Args:
        system_name: 系统名称覆盖（可选），默认自动检测
        release: 内核版本覆盖（可选），默认自动检测
        env: 环境变量映射（可选），默认使用 os.environ
    
    Returns:
        PlatformName: 标准化后的平台名称（macos、linux、windows、wsl、unknown）
    """
    env_map = env or os.environ  # 获取环境变量映射
    system = (system_name or platform.system()).lower()  # 获取系统名称并转小写
    kernel_release = (release or platform.release()).lower()  # 获取内核版本并转小写

    # Darwin 系统返回 macOS
    if system == "darwin":
        return "macos"
    # Windows 系统返回 windows
    if system == "windows":
        return "windows"
    # Linux 系统检测 WSL
    if system == "linux":
        # 检测 WSL 特征：microsoft 字符串或 WSL 环境变量
        if "microsoft" in kernel_release or env_map.get("WSL_DISTRO_NAME") or env_map.get("WSL_INTEROP"):
            return "wsl"
        return "linux"
    # 未知平台
    return "unknown"


@lru_cache(maxsize=1)
def get_platform() -> PlatformName:
    """返回当前进程的检测平台
    
    使用 LRU 缓存优化重复调用性能，缓存大小为 1。
    
    Returns:
        PlatformName: 检测到的平台名称
    """
    return detect_platform()  # 调用平台检测函数


def get_platform_capabilities(platform_name: PlatformName | None = None) -> PlatformCapabilities:
    """返回指定平台的功能能力矩阵
    
    根据平台名称返回对应的功能能力，包括 shell 支持、tmux 支持等信息。
    
    Args:
        platform_name: 平台名称（可选），默认自动检测当前平台
    
    Returns:
        PlatformCapabilities: 平台功能能力对象
    """
    name = platform_name or get_platform()  # 获取平台名称，未指定则自动检测
    # POSIX 平台（macOS、Linux、WSL）
    if name in {"macos", "linux", "wsl"}:
        return PlatformCapabilities(
            name=name,  # 平台名称
            supports_posix_shell=True,  # 支持 POSIX shell
            supports_native_windows_shell=False,  # 不支持原生 Windows shell
            supports_tmux=True,  # 支持 tmux
            supports_swarm_mailbox=True,  # 支持 swarm 邮箱
            supports_sandbox_runtime=True,  # 支持沙箱运行时
        )
    # Windows 平台
    if name == "windows":
        return PlatformCapabilities(
            name=name,  # 平台名称
            supports_posix_shell=False,  # 不支持 POSIX shell
            supports_native_windows_shell=True,  # 支持原生 Windows shell
            supports_tmux=False,  # 不支持 tmux
            supports_swarm_mailbox=False,  # 不支持 swarm 邮箱
            supports_sandbox_runtime=False,  # 不支持沙箱运行时
        )
    # 未知平台
    return PlatformCapabilities(
        name=name,  # 平台名称
        supports_posix_shell=False,  # 不支持 POSIX shell
        supports_native_windows_shell=False,  # 不支持原生 Windows shell
        supports_tmux=False,  # 不支持 tmux
        supports_swarm_mailbox=False,  # 不支持 swarm 邮箱
        supports_sandbox_runtime=False,  # 不支持沙箱运行时
    )

