"""
OpenAI 兼容 API 客户端模块
=========================

本模块提供 OpenAI 兼容 API 客户端封装，支持阿里巴巴 DashScope、GitHub Models 等提供商。

主要功能：
    - 流式文本增量生成
    - Anthropic 工具格式到 OpenAI 格式转换
    - 自动重试 transient 错误
    - 支持思维模型（reasoning_content）

类说明：
    - OpenAICompatibleClient: OpenAI 兼容客户端类

使用示例：
    >>> from illusion.api.openai_client import OpenAICompatibleClient
    >>> client = OpenAICompatibleClient(api_key="sk-...")
    >>> request = ApiMessageRequest(model="qwen-plus", messages=[])
    >>> async for event in client.stream_message(request):
    >>>     print(event)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from illusion.api.client import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiStreamEvent,
    ApiTextDeltaEvent,
)
from illusion.api.errors import (
    AuthenticationFailure,
    IllusionCodeApiError,
    RateLimitFailure,
    RequestFailure,
)
from illusion.api.usage import UsageSnapshot
from illusion.engine.messages import (
    ConversationMessage,
    ContentBlock,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)

# 模块级日志记录器
log = logging.getLogger(__name__)

# 重试配置常量
MAX_RETRIES = 3  # 最大重试次数
BASE_DELAY = 1.0  # 基础延迟（秒）
MAX_DELAY = 30.0  # 最大延迟（秒）


def _convert_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将 Anthropic 工具模式转换为 OpenAI function-calling 格式
    
    Anthropic 格式：
        {"name": "...", "description": "...", "input_schema": {...}}
    OpenAI 格式：
        {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
    
    Args:
        tools: Anthropic 格式的工具定义列表
    
    Returns:
        list[dict[str, Any]]: OpenAI 格式的工具定义列表
    """
    result = []
    for tool in tools:
        result.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        })
    return result


def _convert_messages_to_openai(
    messages: list[ConversationMessage],
    system_prompt: str | None,
) -> list[dict[str, Any]]:
    """将 Anthropic 风格消息转换为 OpenAI 聊天格式
    
    主要差异：
    - Anthropic：系统提示词是单独参数
    - OpenAI：系统提示词是 role="system" 的消息
    - Anthropic：tool_use / tool_result 是 content blocks
    - OpenAI：tool_calls 在 assistant 消息上，tool results 是独立消息
    
    Args:
        messages: Anthropic 风格的消息列表
        system_prompt: 系统提示词
    
    Returns:
        list[dict[str, Any]]: OpenAI 格式的消息列表
    """
    openai_messages: list[dict[str, Any]] = []

    # 添加系统消息
    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        if msg.role == "assistant":
            openai_msg = _convert_assistant_message(msg)
            openai_messages.append(openai_msg)
        elif msg.role == "user":
            # 用户消息可能包含文本或 tool_result blocks
            tool_results = [b for b in msg.content if isinstance(b, ToolResultBlock)]
            text_blocks = [b for b in msg.content if isinstance(b, TextBlock)]

            if tool_results:
                # 每个 tool result 成为独立的 role="tool" 消息
                for tr in tool_results:
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": tr.tool_use_id,
                        "content": tr.content,
                    })
            if text_blocks:
                text = "".join(b.text for b in text_blocks)
                if text.strip():
                    openai_messages.append({"role": "user", "content": text})
            if not tool_results and not text_blocks:
                # 空用户消息（不应发生，但需优雅处理）
                openai_messages.append({"role": "user", "content": ""})

    return openai_messages


def _convert_assistant_message(msg: ConversationMessage) -> dict[str, Any]:
    """将 assistant ConversationMessage 转换为 OpenAI 格式
    
    支持思维模型（如 Kimi k2.5）的 providers 要求每个包含 tool calls 的 assistant 
    消息都有 ``reasoning_content`` 字段。在解析和回放期间，我们将原始推理文本存储在 
    ``msg._reasoning`` 中。
    
    Args:
        msg: ConversationMessage 对象
    
    Returns:
        dict[str, Any]: OpenAI 格式的消息
    """
    text_parts = [b.text for b in msg.content if isinstance(b, TextBlock)]
    tool_uses = [b for b in msg.content if isinstance(b, ToolUseBlock)]

    openai_msg: dict[str, Any] = {"role": "assistant"}

    content = "".join(text_parts)
    openai_msg["content"] = content if content else None

    # 为思维模型回放 reasoning_content（由流式解析器存储）
    reasoning = getattr(msg, "_reasoning", None)
    if reasoning:
        openai_msg["reasoning_content"] = reasoning
    elif tool_uses:
        # 思维模型即使为空也需要此字段
        openai_msg["reasoning_content"] = ""

    if tool_uses:
        openai_msg["tool_calls"] = [
            {
                "id": tu.id,
                "type": "function",
                "function": {
                    "name": tu.name,
                    "arguments": json.dumps(tu.input),
                },
            }
            for tu in tool_uses
        ]

    return openai_msg


def _parse_assistant_response(response: Any) -> ConversationMessage:
    """将 OpenAI ChatCompletion 响应解析为 ConversationMessage
    
    Args:
        response: OpenAI API 响应对象
    
    Returns:
        ConversationMessage: 解析后的消息对象
    """
    choice = response.choices[0]
    message = choice.message
    content: list[ContentBlock] = []

    if message.content:
        content.append(TextBlock(text=message.content))

    if message.tool_calls:
        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}
            content.append(ToolUseBlock(
                id=tc.id,
                name=tc.function.name,
                input=args,
            ))

    return ConversationMessage(role="assistant", content=content)


class OpenAICompatibleClient:
    """OpenAI 兼容 API 客户端
    
    用于 DashScope、GitHub Models 等 OpenAI 兼容 API。
    实现与 AnthropicApiClient 相同的 SupportsStreamingMessages 协议，
    因此可以在 agent 循环中作为直接替代品使用。
    
    Attributes:
        _client: AsyncOpenAI 客户端实例
    """

    def __init__(self, api_key: str, *, base_url: str | None = None) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)

    async def stream_message(self, request: ApiMessageRequest) -> AsyncIterator[ApiStreamEvent]:
        """流式生成文本增量和最终消息，匹配 Anthropic 客户端接口
        
        Args:
            request: API 消息请求
        
        Yields:
            ApiStreamEvent: 流式事件
        """
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                async for event in self._stream_once(request):
                    yield event
                return
            except IllusionCodeApiError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= MAX_RETRIES or not self._is_retryable(exc):
                    raise self._translate_error(exc) from exc

                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                log.warning(
                    "OpenAI API request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, MAX_RETRIES + 1, delay, exc,
                )
                await asyncio.sleep(delay)

        if last_error is not None:
            raise self._translate_error(last_error) from last_error

    async def _stream_once(self, request: ApiMessageRequest) -> AsyncIterator[ApiStreamEvent]:
        """单次尝试：流式 OpenAI 聊天完成
        
        Args:
            request: API 消息请求
        
        Yields:
            ApiStreamEvent: 流式事件
        """
        openai_messages = _convert_messages_to_openai(request.messages, request.system_prompt)
        openai_tools = _convert_tools_to_openai(request.tools) if request.tools else None

        params: dict[str, Any] = {
            "model": request.model,
            "messages": openai_messages,
            "max_tokens": request.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if openai_tools:
            params["tools"] = openai_tools
            # 某些 providers（如 Kimi）在 tool-call 后续请求中对空的 reasoning_content 报错
            # 如果存在 tools，则移除整个 stream_options 键，避免触发模型端思维模式
            # 该模式要求每个 assistant 消息都有 reasoning_content
            params.pop("stream_options", None)

        # 流式文本增量时收集完整响应
        collected_content = ""
        collected_reasoning = ""
        collected_tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage_data: dict[str, int] = {}

        stream = await self._client.chat.completions.create(**params)
        async for chunk in stream:
            if not chunk.choices:
                # 仅使用量块（某些 providers 在最后发送）
                if chunk.usage:
                    usage_data = {
                        "input_tokens": chunk.usage.prompt_tokens or 0,
                        "output_tokens": chunk.usage.completion_tokens or 0,
                    }
                continue

            delta = chunk.choices[0].delta
            chunk_finish = chunk.choices[0].finish_reason

            if chunk_finish:
                finish_reason = chunk_finish

            # 收集思维模型的 reasoning_content（不向用户显示）
            reasoning_piece = getattr(delta, "reasoning_content", None) or ""
            if reasoning_piece:
                collected_reasoning += reasoning_piece

            # 向用户流式传输文本内容
            if delta.content:
                collected_content += delta.content
                yield ApiTextDeltaEvent(text=delta.content)

            # 收集工具调用
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": tc_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    entry = collected_tool_calls[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["arguments"] += tc_delta.function.arguments

            # chunk 中的使用量（如果 provider 发送）
            if chunk.usage:
                usage_data = {
                    "input_tokens": chunk.usage.prompt_tokens or 0,
                    "output_tokens": chunk.usage.completion_tokens or 0,
                }

        # 构建最终 ConversationMessage
        content: list[ContentBlock] = []
        if collected_content:
            content.append(TextBlock(text=collected_content))

        for _idx in sorted(collected_tool_calls.keys()):
            tc = collected_tool_calls[_idx]
            # 跳过某些 provider 发送的空/幻影工具调用
            if not tc["name"]:
                continue
            try:
                args = json.loads(tc["arguments"])
            except (json.JSONDecodeError, TypeError):
                args = {}
            content.append(ToolUseBlock(
                id=tc["id"],
                name=tc["name"],
                input=args,
            ))

        final_message = ConversationMessage(role="assistant", content=content)

        # 为思维模型存储 reasoning，以便 _convert_assistant_message 
        # 在消息发送回 API 时可以回放
        if collected_reasoning:
            final_message._reasoning = collected_reasoning  # type: ignore[attr-defined]

        yield ApiMessageCompleteEvent(
            message=final_message,
            usage=UsageSnapshot(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
            ),
            stop_reason=finish_reason,
        )

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """检查异常是否可重试
        
        Args:
            exc: 待检查的异常
        
        Returns:
            bool: 是否可重试
        """
        status = getattr(exc, "status_code", None)
        if status and status in {429, 500, 502, 503}:
            return True
        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return True
        return False

    @staticmethod
    def _translate_error(exc: Exception) -> IllusionCodeApiError:
        """转换错误为统一异常类型
        
        Args:
            exc: 原始异常
        
        Returns:
            IllusionCodeApiError: 统一异常类型
        """
        status = getattr(exc, "status_code", None)
        msg = str(exc)
        if status == 401 or status == 403:
            return AuthenticationFailure(msg)
        if status == 429:
            return RateLimitFailure(msg)
        return RequestFailure(msg)
