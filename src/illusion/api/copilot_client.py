"""
GitHub Copilot API 客户端模块
===========================

本模块提供 GitHub Copilot 的 API 客户端封装。

主要功能：
    - 使用 GitHub OAuth 令牌进行认证
    - 支持企业版 GitHub
    - 实现流式消息协议

类说明：
    - CopilotClient: Copilot API 客户端类

使用示例：
    >>> from illusion.api.copilot_client import CopilotClient
    >>> client = CopilotClient()
    >>> request = ApiMessageRequest(model="gpt-4o", messages=[])
    >>> async for event in client.stream_message(request):
    >>>     print(event)
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from illusion.api.client import (
    ApiMessageRequest,
    ApiStreamEvent,
)
from illusion.api.copilot_auth import (
    copilot_api_base,
    load_copilot_auth,
)
from illusion.api.errors import AuthenticationFailure
from illusion.api.openai_client import OpenAICompatibleClient

log = logging.getLogger(__name__)

# 模块版本号，用于 User-Agent 头
_VERSION = "0.1.0"  # IllusionCode version for User-Agent

# Copilot 请求的默认模型，当配置的模型不在 Copilot 模型目录中时使用
COPILOT_DEFAULT_MODEL = "gpt-4o"


class CopilotClient:
    """Copilot API 客户端
    
    实现 SupportsStreamingMessages 协议，使用 GitHub OAuth 令牌直接作为 Bearer 令牌。
    不需要额外的令牌交换或会话管理。
    
    Attributes:
        _token: GitHub OAuth 令牌
        _enterprise_url: 企业 URL（可选）
        _model: 默认模型名称
        _inner: 内部 OpenAI 兼容客户端
    """

    def __init__(
        self,
        github_token: str | None = None,
        *,
        enterprise_url: str | None = None,
        model: str | None = None,
    ) -> None:
        # 加载持久化的认证信息
        auth_info = load_copilot_auth()
        # 优先使用显式参数，否则从持久化文件加载
        token = github_token or (auth_info.github_token if auth_info else None)
        if not token:
            raise AuthenticationFailure(
                "未找到 GitHub Copilot 令牌。请先运行 'illusion auth copilot-login'。"
            )

        # 解析企业 URL：显式参数 > 持久化认证 > None（公共版）
        ent_url = enterprise_url or (auth_info.enterprise_url if auth_info else None)

        self._token = token
        self._enterprise_url = ent_url
        self._model = model

        # 构建内部 OpenAI 兼容客户端
        base_url = copilot_api_base(ent_url)
        default_headers: dict[str, str] = {
            "User-Agent": f"illusion/{_VERSION}",
            "Openai-Intent": "conversation-edits",
        }
        raw_openai = AsyncOpenAI(
            api_key=token,
            base_url=base_url,
            default_headers=default_headers,
        )
        self._inner = OpenAICompatibleClient(
            api_key=token,
            base_url=base_url,
        )
        # 替换底层 SDK 客户端以使用 Copilot 头
        self._inner._client = raw_openai  # noqa: SLF001

        log.info(
            "CopilotClient 已初始化 (api_base=%s, enterprise=%s)",
            base_url,
            ent_url or "none",
        )

    async def stream_message(self, request: ApiMessageRequest) -> AsyncIterator[ApiStreamEvent]:
        """从 Copilot API 流式获取聊天完成
        
        满足 IllusionCode 查询引擎期望的 SupportsStreamingMessages 协议。
        
        如果构造时提供了 model 参数，则覆盖请求中的模型；否则传递请求模型。
        
        Args:
            request: API 消息请求
        
        Yields:
            ApiStreamEvent: 流式事件
        """
        # 使用默认模型或请求中的模型
        effective_model = self._model or request.model
        patched = ApiMessageRequest(
            model=effective_model,
            messages=request.messages,
            system_prompt=request.system_prompt,
            max_tokens=request.max_tokens,
            tools=request.tools,
        )
        # 委托给内部客户端
        async for event in self._inner.stream_message(patched):
            yield event
