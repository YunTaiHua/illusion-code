"""
Anthropic API 客户端模块
=======================

本模块提供 Anthropic API 客户端封装，带有重试逻辑。

主要功能：
    - 流式文本增量生成
    - 自动重试 transient 错误
    - OAuth 支持
    - 错误转换

类说明：
    - AnthropicApiClient: Anthropic 异步 SDK 封装类
    - ApiMessageRequest: 模型调用输入参数
    - ApiTextDeltaEvent: 增量文本事件
    - ApiMessageCompleteEvent: 完整消息事件
    - ApiRetryEvent: 重试事件

使用示例：
    >>> from illusion.api.client import AnthropicApiClient, ApiMessageRequest
    >>> client = AnthropicApiClient(api_key="sk-...")
    >>> request = ApiMessageRequest(model="claude-3-sonnet", messages=[])
    >>> async for event in client.stream_message(request):
    >>>     print(event)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Protocol

from anthropic import APIError, APIStatusError, AsyncAnthropic

from illusion.api.errors import (
    AuthenticationFailure,
    IllusionCodeApiError,
    RateLimitFailure,
    RequestFailure,
)
from illusion.auth.external import (
    claude_attribution_header,
    claude_oauth_betas,
    claude_oauth_headers,
    get_claude_code_session_id,
)
from illusion.api.usage import UsageSnapshot
from illusion.engine.messages import ConversationMessage, assistant_message_from_api

# 模块级日志记录器
log = logging.getLogger(__name__)

# 重试配置常量
MAX_RETRIES = 3  # 最大重试次数
BASE_DELAY = 1.0  # 基础延迟（秒）
MAX_DELAY = 30.0  # 最大延迟（秒）
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}  # 可重试的状态码集合
OAUTH_BETA_HEADER = "oauth-2025-04-20"  # OAuth beta 版本头


@dataclass(frozen=True)
class ApiMessageRequest:
    """模型调用输入参数
    
    包含调用模型所需的所有参数。
    
    Attributes:
        model: 模型名称
        messages: 对话消息列表
        system_prompt: 系统提示词（可选）
        max_tokens: 最大令牌数（默认 4096）
        tools: 工具定义列表（默认空列表）
    """

    model: str
    messages: list[ConversationMessage]
    system_prompt: str | None = None
    max_tokens: int = 4096
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ApiTextDeltaEvent:
    """增量文本事件
    
    模型产生的增量文本输出。
    
    Attributes:
        text: 增量文本内容
    """

    text: str


@dataclass(frozen=True)
class ApiMessageCompleteEvent:
    """完整消息事件
    
    包含最终助手消息和完整使用量信息的事件。
    
    Attributes:
        message: 对话消息对象
        usage: 使用量快照
        stop_reason: 停止原因
    """

    message: ConversationMessage
    usage: UsageSnapshot
    stop_reason: str | None = None


@dataclass(frozen=True)
class ApiRetryEvent:
    """重试事件
    
    表示可恢复的上游错误，将自动重试。
    
    Attributes:
        message: 错误消息
        attempt: 当前尝试次数
        max_attempts: 最大尝试次数
        delay_seconds: 延迟秒数
    """

    message: str
    attempt: int
    max_attempts: int
    delay_seconds: float


# 流事件联合类型
ApiStreamEvent = ApiTextDeltaEvent | ApiMessageCompleteEvent | ApiRetryEvent


class SupportsStreamingMessages(Protocol):
    """流式消息协议
    
    查询引擎在测试和生产中使用的协议。
    """

    async def stream_message(self, request: ApiMessageRequest) -> AsyncIterator[ApiStreamEvent]:
        """为请求产生流式事件"""


def _is_retryable(exc: Exception) -> bool:
    """检查异常是否可重试
    
    Args:
        exc: 待检查的异常
    
    Returns:
        bool: 是否可重试
    """
    # API 状态错误：检查状态码
    if isinstance(exc, APIStatusError):
        return exc.status_code in RETRYABLE_STATUS_CODES
    # API 错误：网络错误可重试
    if isinstance(exc, APIError):
        return True
    # 连接错误可重试
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    return False


def _get_retry_delay(attempt: int, exc: Exception | None = None) -> float:
    """计算指数退避延迟（带抖动）
    
    Args:
        attempt: 当前尝试次数
        exc: 异常对象（可选）
    
    Returns:
        float: 延迟秒数
    """
    import random

    # 检查 Retry-After 头
    if isinstance(exc, APIStatusError):
        retry_after = getattr(exc, "headers", {})
        if hasattr(retry_after, "get"):
            val = retry_after.get("retry-after")
            if val:
                try:
                    return min(float(val), MAX_DELAY)
                except (ValueError, TypeError):
                    pass

    # 指数退避计算
    delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
    # 添加随机抖动（0-25%）
    jitter = random.uniform(0, delay * 0.25)
    return delay + jitter


class AnthropicApiClient:
    """Anthropic 异步 SDK 封装类
    
    带重试逻辑的 Anthropic API 薄封装。
    
    Attributes:
        _api_key: API 密钥
        _auth_token: 认证令牌
        _base_url: 基础 URL
        _claude_oauth: 是否使用 OAuth
        _auth_token_resolver: 认证令牌解析器
        _session_id: 会话 ID
        _client: AsyncAnthropic 客户端实例
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        auth_token: str | None = None,
        base_url: str | None = None,
        claude_oauth: bool = False,
        auth_token_resolver: Callable[[], str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._auth_token = auth_token
        self._base_url = base_url
        self._claude_oauth = claude_oauth
        self._auth_token_resolver = auth_token_resolver
        self._session_id = get_claude_code_session_id() if claude_oauth else ""
        self._client = self._create_client()

    def _create_client(self) -> AsyncAnthropic:
        """创建 Anthropic 客户端
        
        Returns:
            AsyncAnthropic: 配置好的客户端实例
        """
        kwargs: dict[str, Any] = {}
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._auth_token:
            kwargs["auth_token"] = self._auth_token
            kwargs["default_headers"] = (
                claude_oauth_headers()
                if self._claude_oauth
                else {"anthropic-beta": OAUTH_BETA_HEADER}
            )
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return AsyncAnthropic(**kwargs)

    def _refresh_client_auth(self) -> None:
        """刷新客户端认证
        
        如果使用 OAuth 且有令牌解析器，则刷新认证令牌。
        """
        if not self._claude_oauth or self._auth_token_resolver is None:
            return
        next_token = self._auth_token_resolver()
        if next_token and next_token != self._auth_token:
            self._auth_token = next_token
            self._client = self._create_client()

    async def stream_message(self, request: ApiMessageRequest) -> AsyncIterator[ApiStreamEvent]:
        """流式生成文本增量并在 transient 错误时自动重试
        
        Args:
            request: API 消息请求
        
        Yields:
            ApiStreamEvent: 流式事件（文本增量或完整消息）
        """
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                self._refresh_client_auth()
                async for event in self._stream_once(request):
                    yield event
                return  # 成功
            except IllusionCodeApiError:
                raise  # 认证错误不重试
            except Exception as exc:
                last_error = exc
                # 超过最大重试次数或不可重试
                if attempt >= MAX_RETRIES or not _is_retryable(exc):
                    if isinstance(exc, APIError):
                        raise _translate_api_error(exc) from exc
                    raise RequestFailure(str(exc)) from exc

                # 计算延迟并发送重试事件
                delay = _get_retry_delay(attempt, exc)
                status = getattr(exc, "status_code", "?")
                log.warning(
                    "API request failed (attempt %d/%d, status=%s), retrying in %.1fs: %s",
                    attempt + 1, MAX_RETRIES + 1, status, delay, exc,
                )
                yield ApiRetryEvent(
                    message=str(exc),
                    attempt=attempt + 1,
                    max_attempts=MAX_RETRIES + 1,
                    delay_seconds=delay,
                )
                await asyncio.sleep(delay)

        # 最终错误处理
        if last_error is not None:
            if isinstance(last_error, APIError):
                raise _translate_api_error(last_error) from last_error
            raise RequestFailure(str(last_error)) from last_error

    async def _stream_once(self, request: ApiMessageRequest) -> AsyncIterator[ApiStreamEvent]:
        """单次尝试流式消息
        
        Args:
            request: API 消息请求
        
        Yields:
            ApiStreamEvent: 流式事件
        """
        # 构建请求参数
        params: dict[str, Any] = {
            "model": request.model,
            "messages": [message.to_api_param() for message in request.messages],
            "max_tokens": request.max_tokens,
        }
        # 添加系统提示词
        if request.system_prompt:
            params["system"] = request.system_prompt
        # OAuth 认证：添加归属头
        if self._claude_oauth:
            attribution = claude_attribution_header()
            params["system"] = (
                f"{attribution}\n{params['system']}"
                if params.get("system")
                else attribution
            )
        # 添加工具定义
        if request.tools:
            params["tools"] = request.tools
        # OAuth 附加参数
        if self._claude_oauth:
            params["betas"] = claude_oauth_betas()
            params["metadata"] = {
                "user_id": json.dumps(
                    {
                        "device_id": "illusion",
                        "session_id": self._session_id,
                        "account_uuid": "",
                    },
                    separators=(",", ":"),
                )
            }
            params["extra_headers"] = {"x-client-request-id": str(uuid.uuid4())}

        try:
            # 根据是否使用 OAuth 选择 API 端点
            stream_api = self._client.beta.messages if self._claude_oauth else self._client.messages
            async with stream_api.stream(**params) as stream:
                async for event in stream:
                    # 只处理文本增量事件
                    if getattr(event, "type", None) != "content_block_delta":
                        continue
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", None) != "text_delta":
                        continue
                    text = getattr(delta, "text", "")
                    if text:
                        yield ApiTextDeltaEvent(text=text)

                # 获取最终消息
                final_message = await stream.get_final_message()
        except APIError as exc:
            # 可重试状态码直接抛出，让重试逻辑处理
            if isinstance(exc, APIStatusError) and exc.status_code in RETRYABLE_STATUS_CODES:
                raise
            raise _translate_api_error(exc) from exc

        # 提取使用量并发送完成事件
        usage = getattr(final_message, "usage", None)
        yield ApiMessageCompleteEvent(
            message=assistant_message_from_api(final_message),
            usage=UsageSnapshot(
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            ),
            stop_reason=getattr(final_message, "stop_reason", None),
        )


def _translate_api_error(exc: APIError) -> IllusionCodeApiError:
    """转换 API 错误为统一异常类型
    
    Args:
        exc: Anthropic API 错误
    
    Returns:
        IllusionCodeApiError: 统一异常类型
    """
    name = exc.__class__.__name__
    # 认证错误
    if name in {"AuthenticationError", "PermissionDeniedError"}:
        return AuthenticationFailure(str(exc))
    # 速率限制错误
    if name == "RateLimitError":
        return RateLimitFailure(str(exc))
    # 请求失败
    return RequestFailure(str(exc))
