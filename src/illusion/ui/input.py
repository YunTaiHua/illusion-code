"""
Input 输入模块
=============

本模块实现基于 prompt_toolkit 的异步输入会话功能。

主要功能：
    - 异步命令行输入会话
    - 用户提示和问答支持

类说明：
    - InputSession: 异步输入会话封装类

使用示例：
    >>> from illusion.ui.input import InputSession
    >>> 
    >>> # 创建输入会话
    >>> session = InputSession()
    >>> 
    >>> # 获取用户输入
    >>> user_input = await session.prompt()
    >>> 
    >>> # 提问并获取答案
    >>> answer = await session.ask("请输入您的姓名")
"""

from __future__ import annotations

from prompt_toolkit import PromptSession


class InputSession:
    """异步输入会话封装类。

    基于 prompt_toolkit 的 PromptSession 实现异步命令行输入。
    支持普通提示输入和自定义问答。

    Attributes:
        _session: prompt_toolkit 会话实例
        _prompt: 提示符字符串

    使用示例：
        >>> session = InputSession()
        >>> user_input = await session.prompt()
    """

    def __init__(self) -> None:
        # 创建 prompt_toolkit 会话实例
        self._session = PromptSession()
        # 设置默认提示符
        self._prompt = "> "

    def set_modes(self, *, vim_enabled: bool = False, voice_enabled: bool = False) -> None:
        """设置输入模式。

        注意：vim 和 voice 模式已从 UI 提示符中移除，此方法保留用于兼容性。

        Args:
            vim_enabled: Vim 模式开关（已废弃）
            voice_enabled: 语音模式开关（已废弃）
        """
        # 忽略废弃参数以保持 API 兼容性
        del vim_enabled, voice_enabled
        # 重置为默认提示符
        self._prompt = "> "

    async def prompt(self) -> str:
        """提示用户输入一行文本。

        Returns:
            str: 用户输入的文本（已去除首尾空白）
        """
        return await self._session.prompt_async(self._prompt)

    async def ask(self, question: str) -> str:
        """提示用户回答一个问题。

        Args:
            question: 要询问用户的问题

        Returns:
            str: 用户输入的答案（已去除首尾空白）
        """
        # 构建问答提示符，格式为 "[question] 问题内容\n> "
        prompt = f"[question] {question}\n> "
        return await self._session.prompt_async(prompt)