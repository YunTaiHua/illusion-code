"""高级对话引擎。

本模块提供高级对话引擎，管理对话历史和工具感知的模型循环。

主要功能：
    - 管理对话历史
    - 执行用户消息提交
    - 支持待续工具调用继续
    - 跟踪令牌使用成本

主要类：
    - QueryEngine: 对话引擎主类

使用示例：
    >>> from illusion.engine import QueryEngine
    >>> engine = QueryEngine(
    ...     api_client=client,
    ...     tool_registry=registry,
    ...     permission_checker=checker,
    ...     cwd=".",
    ...     model="claude-3-opus",
    ...     system_prompt="你是一个助手"
    ... )
    >>> async for event in engine.submit_message("你好"):
    ...     print(event)
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from illusion.api.client import SupportsStreamingMessages
from illusion.engine.cost_tracker import CostTracker
from illusion.engine.messages import ConversationMessage, ToolResultBlock
from illusion.engine.query import AskUserPrompt, PermissionPrompt, QueryContext, run_query
from illusion.engine.stream_events import StreamEvent
from illusion.hooks import HookExecutor
from illusion.permissions.checker import PermissionChecker
from illusion.tools.base import ToolRegistry


class QueryEngine:
    """拥有对话历史和工具感知模型循环的高级引擎。

    管理整个对话生命周期，包括消息提交、工具执行、成本跟踪等。

    Attributes:
        messages: 当前对话历史（只读）
        max_turns: 每个用户输入的最大智能体轮次数
        total_usage: 跨所有轮次的总使用量

    使用示例：
        >>> engine = QueryEngine(
        ...     api_client=client,
        ...     tool_registry=registry,
        ...     permission_checker=checker,
        ...     cwd=".",
        ...     model="claude-3-opus",
        ...     system_prompt="你是一个助手"
        ... )
    """

    def __init__(
        self,
        *,
        api_client: SupportsStreamingMessages,
        tool_registry: ToolRegistry,
        permission_checker: PermissionChecker,
        cwd: str | Path,
        model: str,
        system_prompt: str,
        max_tokens: int = 4096,
        max_turns: int | None = 8,
        permission_prompt: PermissionPrompt | None = None,
        ask_user_prompt: AskUserPrompt | None = None,
        hook_executor: HookExecutor | None = None,
        tool_metadata: dict[str, object] | None = None,
    ) -> None:
        self._api_client = api_client  # API客户端
        self._tool_registry = tool_registry  # 工具注册表
        self._permission_checker = permission_checker  # 权限检查器
        self._cwd = Path(cwd).resolve()  # 当前工作目录
        self._model = model  # 模型名称
        self._system_prompt = system_prompt  # 系统提示词
        self._max_tokens = max_tokens  # 最大令牌数
        self._max_turns = max_turns  # 最大轮次
        self._permission_prompt = permission_prompt  # 权限提示回调
        self._ask_user_prompt = ask_user_prompt  # 用户询问回调
        self._hook_executor = hook_executor  # 钩子执行器
        self._tool_metadata = tool_metadata or {}  # 工具元数据
        self._messages: list[ConversationMessage] = []  # 对话消息历史
        self._cost_tracker = CostTracker()  # 成本跟踪器

    @property
    def messages(self) -> list[ConversationMessage]:
        """返回当前对话历史。

        Returns:
            list[ConversationMessage]: 消息列表的副本
        """
        return list(self._messages)

    @property
    def max_turns(self) -> int | None:
        """返回每个用户输入的最大智能体轮次数（如果有上限）。

        Returns:
            int | None: 最大轮次数或None（无限制）
        """
        return self._max_turns

    @property
    def total_usage(self):
        """返回跨所有轮次的总使用量。

        Returns:
            UsageSnapshot: 累积的使用量快照
        """
        return self._cost_tracker.total

    def clear(self) -> None:
        """清除内存中的对话历史。

        同时重置成本跟踪器。
        """
        self._messages.clear()
        self._cost_tracker = CostTracker()

    def set_system_prompt(self, prompt: str) -> None:
        """更新未来轮次的活跃系统提示词。

        Args:
            prompt: 新的系统提示词
        """
        self._system_prompt = prompt

    def set_model(self, model: str) -> None:
        """更新未来轮次的活跃模型。

        Args:
            model: 新的模型名称
        """
        self._model = model

    def set_api_client(self, api_client: SupportsStreamingMessages) -> None:
        """更新未来轮次的活跃API客户端。

        Args:
            api_client: 新的API客户端
        """
        self._api_client = api_client

    def set_max_turns(self, max_turns: int | None) -> None:
        """更新每个用户输入的最大智能体轮次数。

        Args:
            max_turns: 最大轮次数，None表示无限制
        """
        self._max_turns = None if max_turns is None else max(1, int(max_turns))

    def set_permission_checker(self, checker: PermissionChecker) -> None:
        """更新未来轮次的活跃权限检查器。

        Args:
            checker: 新的权限检查器
        """
        self._permission_checker = checker

    def load_messages(self, messages: list[ConversationMessage]) -> None:
        """替换内存中的对话历史。

        Args:
            messages: 新的消息列表
        """
        self._messages = list(messages)

    def has_pending_continuation(self) -> bool:
        """当对话以等待后续模型轮次的工具结果结束时返回True。

        用于检查是否有待续的工具调用需要继续执行。

        Returns:
            bool: 是否有待续的继续
        """
        if not self._messages:
            return False
        last = self._messages[-1]
        if last.role != "user":
            return False
        if not any(isinstance(block, ToolResultBlock) for block in last.content):
            return False
        for msg in reversed(self._messages[:-1]):
            if msg.role != "assistant":
                continue
            return bool(msg.tool_uses)
        return False

    async def submit_message(self, prompt: str) -> AsyncIterator[StreamEvent]:
        """追加用户消息并执行查询循环。

        Args:
            prompt: 用户输入的提示词

        Yields:
            StreamEvent: 流式事件

        使用示例：
            >>> async for event in engine.submit_message("你好"):
            ...     print(event)
        """
        # 将用户文本转换为消息并添加到历史记录
        self._messages.append(ConversationMessage.from_user_text(prompt))
        context = QueryContext(
            api_client=self._api_client,
            tool_registry=self._tool_registry,
            permission_checker=self._permission_checker,
            cwd=self._cwd,
            model=self._model,
            system_prompt=self._system_prompt,
            max_tokens=self._max_tokens,
            max_turns=self._max_turns,
            permission_prompt=self._permission_prompt,
            ask_user_prompt=self._ask_user_prompt,
            hook_executor=self._hook_executor,
            tool_metadata=self._tool_metadata,
        )
        async for event, usage in run_query(context, self._messages):
            if usage is not None:
                self._cost_tracker.add(usage)  # 累加使用量
            yield event

    async def continue_pending(self, *, max_turns: int | None = None) -> AsyncIterator[StreamEvent]:
        """继续被中断的工具循环，而不追加新的用户消息。

        用于恢复之前因工具执行而中断的对话。

        Args:
            max_turns: 最大轮次数（可选，默认使用引擎设置）

        Yields:
            StreamEvent: 流式事件
        """
        context = QueryContext(
            api_client=self._api_client,
            tool_registry=self._tool_registry,
            permission_checker=self._permission_checker,
            cwd=self._cwd,
            model=self._model,
            system_prompt=self._system_prompt,
            max_tokens=self._max_tokens,
            max_turns=max_turns if max_turns is not None else self._max_turns,
            permission_prompt=self._permission_prompt,
            ask_user_prompt=self._ask_user_prompt,
            hook_executor=self._hook_executor,
            tool_metadata=self._tool_metadata,
        )
        async for event, usage in run_query(context, self._messages):
            if usage is not None:
                self._cost_tracker.add(usage)  # 累加使用量
            yield event
