"""
IllusionCode 沙箱集成辅助模块
==========================

本模块提供沙箱集成的公共接口。

导出内容：
    - SandboxAvailability: 沙箱可用性状态
    - SandboxUnavailableError: 沙箱不可用错误
    - build_sandbox_runtime_config: 构建运行时配置
    - get_sandbox_availability: 获取沙箱可用性
    - wrap_command_for_sandbox: 包装命令用于沙箱执行
"""

from illusion.sandbox.adapter import (
    SandboxAvailability,
    SandboxUnavailableError,
    build_sandbox_runtime_config,
    get_sandbox_availability,
    wrap_command_for_sandbox,
)

__all__ = [
    "SandboxAvailability",
    "SandboxUnavailableError",
    "build_sandbox_runtime_config",
    "get_sandbox_availability",
    "wrap_command_for_sandbox",
]