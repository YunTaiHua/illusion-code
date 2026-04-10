"""
Permission Dialog 权限对话框模块
=========================

本模块实现基于 prompt_toolkit 的交互式权限确认对话框。

主要功能：
    - 异步权限确认提示
    - 用户授权决策

函数说明：
    - ask_permission: 提示用户批准变异工具

使用示例：
    >>> from illusion.ui.permission_dialog import ask_permission
    >>> 
    >>> # 请求权限
    >>> allowed = await ask_permission("Bash", "需要执行 shell 命令")
    >>> if allowed:
    ...     print("已授权")
"""

from __future__ import annotations

from prompt_toolkit import PromptSession


async def ask_permission(tool_name: str, reason: str) -> bool:
    """提示用户批准变异工具。

    显示工具名称和原因，询问用户是否允许执行。

    Args:
        tool_name: 工具名称
        reason: 工具请求的原因说明

    Returns:
        bool: 用户是否允许执行该工具
    """
    # 创建 prompt 会话
    session = PromptSession()
    # 发送提示并获取用户响应
    response = await session.prompt_async(
        f"Allow tool '{tool_name}'? [{reason}] [y/N]: "
    )
    # 检查用户输入是否为肯定回答
    return response.strip().lower() in {"y", "yes"}