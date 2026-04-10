"""
OpenAI Codex 订阅客户端模块
==========================

本模块提供基于 chatgpt.com Codex Responses 的 OpenAI Codex 订阅客户端。

主要功能：
    - 使用 OAuth 令牌进行认证
    - 流式文本增量生成
    - 支持工具调用
    - 自动重试 transient 错误

类说明：
    - CodexApiClient: Codex API 客户端类

使用示例：
    >>> from illusion.api.codex_client import CodexApiClient
    >>> client = CodexApiClient(auth_token="gho_...")
    >>> request = ApiMessageRequest(model="gpt-4o", messages=[])
    >>> async for event in client.stream_message(request):
    >>>     print(event)
"""

from __future__ import annotations

import base64
import json
import platform
from typing import Any, AsyncIterator

import httpx

from illusion.api.client import (
    ApiMessageCompleteEvent,
    ApiMessageRequest,
    ApiRetryEvent,
    ApiStreamEvent,
    ApiTextDeltaEvent,
)
from illusion.api.errors import AuthenticationFailure, IllusionCodeApiError, RateLimitFailure, RequestFailure
from illusion.api.usage import UsageSnapshot
from illusion.engine.messages import ConversationMessage, TextBlock, ToolResultBlock, ToolUseBlock

# 常量定义
DEFAULT_CODEX_BASE_URL = "https://chatgpt.com/backend-api"  # 默认 Codex 基础 URL
JWT_CLAIM_PATH = "https://api.openai.com/auth"  # JWT 声明路径
MAX_RETRIES = 3  # 最大重试次数
BASE_DELAY_SECONDS = 1.0  # 基础延迟（秒）
MAX_DELAY_SECONDS = 30.0  # 最大延迟（秒）


def _resolve_codex_url(base_url: str | None) -> str:
    """解析并返回 Codex API URL
    
    Args:
        base_url: 可选的基础 URL
    
    Returns:
        str: 完整的 Codex API URL
    """
    trimmed = (base_url or "").strip()
    if trimmed and "chatgpt.com/backend-api" not in trimmed:
        trimmed = ""
    raw = (trimmed or DEFAULT_CODEX_BASE_URL).rstrip("/")
    if raw.endswith("/codex/responses"):
        return raw
    if raw.endswith("/codex"):
        return f"{raw}/responses"
    return f"{raw}/codex/responses"


def _build_codex_headers(token: str, *, session_id: str | None = None) -> dict[str, str]:
    """构建 Codex API 请求头
    
    Args:
        token: Codex 访问令牌
        session_id: 可选的会话 ID
    
    Returns:
        dict[str, str]: 请求头字典
    """
    account_id = _extract_account_id(token)
    headers = {
        "Authorization": f"Bearer {token}",
        "chatgpt-account-id": account_id,
        "originator": "illusion",
        "User-Agent": f"illusion ({platform.system().lower()} {platform.machine() or 'unknown'})",
        "OpenAI-Beta": "responses=experimental",
        "accept": "text/event-stream",
        "content-type": "application/json",
    }
    if session_id:
        headers["session_id"] = session_id
    return headers


def _convert_messages_to_codex(messages: list[ConversationMessage]) -> list[dict[str, Any]]:
    """将消息转换为 Codex 格式
    
    Args:
        messages: ConversationMessage 列表
    
    Returns:
        list[dict[str, Any]]: Codex 格式的消息列表
    """
    result: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "user":
            text = "".join(block.text for block in msg.content if isinstance(block, TextBlock))
            if text.strip():
                result.append({
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                })
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    result.append({
                        "type": "function_call_output",
                        "call_id": block.tool_use_id,
                        "output": block.content,
                    })
            continue

        assistant_text = "".join(block.text for block in msg.content if isinstance(block, TextBlock))
        if assistant_text:
            result.append({
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": assistant_text, "annotations": []}],
            })
        for block in msg.content:
            if isinstance(block, ToolUseBlock):
                result.append({
                    "type": "function_call",
                    "id": f"fc_{block.id[:58]}",
                    "call_id": block.id,
                    "name": block.name,
                    "arguments": json.dumps(block.input, separators=(",", ":")),
                })
    return result


def _convert_tools_to_codex(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将工具转换为 Codex 格式
    
    Args:
        tools: 工具定义列表
    
    Returns:
        list[dict[str, Any]]: Codex 格式的工具列表
    """
    return [
        {
            "type": "function",
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {}),
        }
        for tool in tools
    ]


def _usage_from_response(response: dict[str, Any]) -> UsageSnapshot:
    """从响应中提取使用量信息
    
    Args:
        response: API 响应字典
    
    Returns:
        UsageSnapshot: 使用量快照
    """
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return UsageSnapshot()
    return UsageSnapshot(
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
    )


def _stop_reason_from_response(response: dict[str, Any], *, has_tool_calls: bool) -> str | None:
    """从响应中提取停止原因
    
    Args:
        response: API 响应字典
        has_tool_calls: 是否有工具调用
    
    Returns:
        str | None: 停止原因
    """
    status = response.get("status")
    if has_tool_calls and status == "completed":
        return "tool_use"
    if status == "completed":
        return "stop"
    if status == "incomplete":
        return "length"
    if status in {"failed", "cancelled"}:
        return "error"
    return None


def _format_error_message(status_code: int, payload: str) -> str:
    """格式化错误消息
    
    Args:
        status_code: HTTP 状态码
        payload: 响应负载
    
    Returns:
        str: 格式化的错误消息
    """
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        error = parsed.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message
        detail = parsed.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail
    text = payload.strip()
    if text:
        return text
    return f"Codex request failed with status {status_code}"


def _translate_status_error(status_code: int, message: str) -> IllusionCodeApiError:
    """转换状态码错误为统一异常类型
    
    Args:
        status_code: HTTP 状态码
        message: 错误消息
    
    Returns:
        IllusionCodeApiError: 统一异常类型
    """
    if status_code in {401, 403}:
        return AuthenticationFailure(message)
    if status_code == 429:
        return RateLimitFailure(message)
    return RequestFailure(message)


class CodexApiClient:
    """ChatGPT/Codex 订阅支持的 Codex Responses 客户端
    
    Attributes:
        _auth_token: 认证令牌
        _base_url: 基础 URL
        _url: 解析后的 API URL
    """

    def __init__(self, auth_token: str, *, base_url: str | None = None) -> None:
        self._auth_token = auth_token
        self._base_url = base_url
        self._url = _resolve_codex_url(base_url)

    async def stream_message(self, request: ApiMessageRequest) -> AsyncIterator[ApiStreamEvent]:
        """流式生成文本增量
        
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
            except Exception as exc:
                last_error = exc
                if attempt >= MAX_RETRIES or not self._is_retryable(exc):
                    raise self._translate_error(exc) from exc
                delay = min(BASE_DELAY_SECONDS * (2 ** attempt), MAX_DELAY_SECONDS)
                import asyncio

                yield ApiRetryEvent(
                    message=str(exc),
                    attempt=attempt + 1,
                    max_attempts=MAX_RETRIES + 1,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)
        if last_error is not None:
            raise self._translate_error(last_error) from last_error

    async def _stream_once(self, request: ApiMessageRequest) -> AsyncIterator[ApiStreamEvent]:
        body: dict[str, Any] = {
            "model": request.model,
            "store": False,
            "stream": True,
            "instructions": request.system_prompt or "You are illusion.",
            "input": _convert_messages_to_codex(request.messages),
            "text": {"verbosity": "medium"},
            "include": ["reasoning.encrypted_content"],
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }
        if request.tools:
            body["tools"] = _convert_tools_to_codex(request.tools)

        content: list[TextBlock | ToolUseBlock] = []
        current_text_parts: list[str] = []
        completed_response: dict[str, Any] | None = None

        headers = _build_codex_headers(self._auth_token)
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream("POST", self._url, headers=headers, json=body) as response:
                if response.status_code >= 400:
                    payload = await response.aread()
                    message = _format_error_message(response.status_code, payload.decode("utf-8", "replace"))
                    raise httpx.HTTPStatusError(message, request=response.request, response=response)

                async for event in self._iter_sse_events(response):
                    event_type = event.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event.get("delta")
                        if isinstance(delta, str) and delta:
                            current_text_parts.append(delta)
                            yield ApiTextDeltaEvent(text=delta)
                    elif event_type == "response.output_item.done":
                        item = event.get("item")
                        if not isinstance(item, dict):
                            continue
                        item_type = item.get("type")
                        if item_type == "message":
                            text = ""
                            raw_content = item.get("content")
                            if isinstance(raw_content, list):
                                parts = []
                                for block in raw_content:
                                    if isinstance(block, dict):
                                        if block.get("type") == "output_text":
                                            parts.append(str(block.get("text", "")))
                                        elif block.get("type") == "refusal":
                                            parts.append(str(block.get("refusal", "")))
                                text = "".join(parts)
                            if text:
                                content.append(TextBlock(text=text))
                        elif item_type == "function_call":
                            arguments = item.get("arguments")
                            parsed_arguments: dict[str, Any]
                            if isinstance(arguments, str) and arguments:
                                try:
                                    loaded = json.loads(arguments)
                                except json.JSONDecodeError:
                                    loaded = {}
                            else:
                                loaded = {}
                            parsed_arguments = loaded if isinstance(loaded, dict) else {}
                            call_id = item.get("call_id")
                            name = item.get("name")
                            if isinstance(call_id, str) and call_id and isinstance(name, str) and name:
                                content.append(ToolUseBlock(id=call_id, name=name, input=parsed_arguments))
                    elif event_type == "response.completed":
                        response_payload = event.get("response")
                        if isinstance(response_payload, dict):
                            completed_response = response_payload
                    elif event_type == "response.failed":
                        response_payload = event.get("response")
                        if isinstance(response_payload, dict):
                            error = response_payload.get("error")
                            if isinstance(error, dict):
                                message = str(error.get("message") or error.get("code") or "Codex response failed")
                                raise RequestFailure(message)
                        raise RequestFailure("Codex response failed")
                    elif event_type == "error":
                        message = str(event.get("message") or event.get("code") or "Codex error")
                        raise RequestFailure(message)

        if current_text_parts and not any(isinstance(block, TextBlock) for block in content):
            content.insert(0, TextBlock(text="".join(current_text_parts)))

        final_message = ConversationMessage(role="assistant", content=content)
        usage = _usage_from_response(completed_response or {})
        stop_reason = _stop_reason_from_response(
            completed_response or {},
            has_tool_calls=bool(final_message.tool_uses),
        )
        yield ApiMessageCompleteEvent(
            message=final_message,
            usage=usage,
            stop_reason=stop_reason,
        )

    async def _iter_sse_events(self, response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
        data_lines: list[str] = []
        async for line in response.aiter_lines():
            if line == "":
                if data_lines:
                    payload = "\n".join(data_lines).strip()
                    data_lines = []
                    if payload and payload != "[DONE]":
                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(event, dict):
                            yield event
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            payload = "\n".join(data_lines).strip()
            if payload and payload != "[DONE]":
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    return
                if isinstance(event, dict):
                    yield event

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {429, 500, 502, 503, 504}
        if isinstance(exc, RateLimitFailure):
            return True
        if isinstance(exc, RequestFailure):
            message = str(exc).lower()
            return any(term in message for term in ["timeout", "connect", "network", "rate", "overloaded"])
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        return False

    @staticmethod
    def _translate_error(exc: Exception) -> IllusionCodeApiError:
        if isinstance(exc, IllusionCodeApiError):
            return exc
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            return _translate_status_error(status, str(exc))
        if isinstance(exc, httpx.HTTPError):
            return RequestFailure(str(exc))
        return RequestFailure(str(exc))
