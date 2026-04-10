"""
命令注册模块
============

本模块提供 IllusionCode 斜杠命令注册功能。

主要组件：
    - CommandContext: 命令上下文
    - CommandRegistry: 命令注册表
    - CommandResult: 命令结果
    - SlashCommand: 斜杠命令
    - create_default_command_registry: 创建默认命令注册表

使用示例：
    >>> from illusion.commands import CommandRegistry, SlashCommand
"""

from illusion.commands.registry import (
    CommandContext,
    CommandRegistry,
    CommandResult,
    SlashCommand,
    create_default_command_registry,
)

__all__ = [
    "CommandContext",
    "CommandRegistry",
    "CommandResult",
    "SlashCommand",
    "create_default_command_registry",
]
