"""
外部 CLI 管理的订阅凭据集成模块
==============================

本模块提供与外部 CLI 管理的订阅凭据的集成功能。

主要功能：
    - 从 Codex CLI 加载外部认证凭据
    - 从 Claude CLI 加载外部认证凭据
    - 处理 OAuth 令牌刷新
    - 检测凭据过期状态
    - 生成 Claude Code 风格的请求头

类说明：
    - ExternalAuthBinding: 外部认证绑定数据类
    - ExternalAuthCredential: 外部凭据数据类
    - ExternalAuthState: 外部认证状态数据类

使用示例：
    >>> from illusion.auth.external import load_external_credential, default_binding_for_provider
    >>> binding = default_binding_for_provider("openai_codex")
    >>> cred = load_external_credential(binding)
    >>> print(cred.value)
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from illusion.auth.storage import ExternalAuthBinding

# 提供商常量定义
CODEX_PROVIDER = "openai_codex"  # Codex 提供商名称
CLAUDE_PROVIDER = "anthropic_claude"  # Claude 提供商名称
CLAUDE_CODE_VERSION_FALLBACK = "2.1.88"  # Claude Code 版本回退值
CLAUDE_OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"  # Claude OAuth 客户端 ID
CLAUDE_OAUTH_TOKEN_ENDPOINTS = (  # Claude OAuth 令牌端点列表
    "https://platform.claude.com/v1/oauth/token",
    "https://console.anthropic.com/v1/oauth/token",
)
CLAUDE_COMMON_BETAS = (  # 通用的 Beta 特性列表
    "interleaved-thinking-2025-05-14",
    "fine-grained-tool-streaming-2025-05-14",
)
CLAUDE_OAUTH_ONLY_BETAS = (  # 仅 OAuth 的 Beta 特性列表
    "claude-code-20250219",
    "oauth-2025-04-20",
)

# 模块级缓存变量
_claude_code_version_cache: str | None = None  # Claude Code 版本缓存
_claude_code_session_id: str | None = None  # Claude Code 会话 ID 缓存


@dataclass(frozen=True)
class ExternalAuthCredential:
    """运行时使用的规范化外部凭据
    
    Attributes:
        provider: 提供商名称
        value: 凭据值（访问令牌）
        auth_kind: 认证类型
        source_path: 源文件路径
        managed_by: 管理程序名称
        profile_label: 配置标签
        refresh_token: 刷新令牌
        expires_at_ms: 过期时间（毫秒时间戳）
    """

    provider: str
    value: str
    auth_kind: str
    source_path: Path
    managed_by: str
    profile_label: str = ""
    refresh_token: str = ""
    expires_at_ms: int | None = None


@dataclass(frozen=True)
class ExternalAuthState:
    """人类可读的外部认证源状态
    
    Attributes:
        configured: 是否已配置
        state: 状态字符串
        source: 来源字符串
        detail: 详细信息
    """

    configured: bool
    state: str
    source: str
    detail: str = ""


def default_binding_for_provider(provider: str) -> ExternalAuthBinding:
    """获取指定提供商的默认外部认证源
    
    Args:
        provider: 提供商名称
    
    Returns:
        ExternalAuthBinding: 外部认证绑定对象
    
    Raises:
        ValueError: 不支持的外部认证提供商
    """
    if provider == CODEX_PROVIDER:
        codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
        return ExternalAuthBinding(
            provider=provider,
            source_path=str(codex_home / "auth.json"),
            source_kind="codex_auth_json",
            managed_by="codex-cli",
            profile_label="Codex CLI",
        )
    if provider == CLAUDE_PROVIDER:
        claude_home = Path(os.environ.get("CLAUDE_HOME", "~/.claude")).expanduser()
        return ExternalAuthBinding(
            provider=provider,
            source_path=str(claude_home / ".credentials.json"),
            source_kind="claude_credentials_json",
            managed_by="claude-cli",
            profile_label="Claude CLI",
        )
    raise ValueError(f"Unsupported external auth provider: {provider}")


def load_external_credential(
    binding: ExternalAuthBinding,
    *,
    refresh_if_needed: bool = False,
) -> ExternalAuthCredential:
    """从外部认证绑定读取运行时凭据
    
    Args:
        binding: 外部认证绑定对象
        refresh_if_needed: 是否在需要时刷新凭据
    
    Returns:
        ExternalAuthCredential: 外部凭据对象
    
    Raises:
        ValueError: 外部认证源不存在或无效
    """
    source_path = Path(binding.source_path).expanduser()
    if not source_path.exists():
        raise ValueError(f"External auth source not found: {source_path}")

    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in external auth source: {source_path}") from exc

    if binding.provider == CODEX_PROVIDER:
        return _load_codex_credential(payload, source_path, binding)
    if binding.provider == CLAUDE_PROVIDER:
        return _load_claude_credential(
            payload,
            source_path,
            binding,
            refresh_if_needed=refresh_if_needed,
        )
    raise ValueError(f"Unsupported external auth provider: {binding.provider}")


def _load_codex_credential(
    payload: dict[str, Any],
    source_path: Path,
    binding: ExternalAuthBinding,
) -> ExternalAuthCredential:
    """从 Codex 认证源加载凭据（内部函数）
    
    Args:
        payload: 解析后的 JSON 数据
        source_path: 源文件路径
        binding: 外部认证绑定对象
    
    Returns:
        ExternalAuthCredential: 外部凭据对象
    
    Raises:
        ValueError: 未找到访问令牌
    """
    tokens = payload.get("tokens")
    access_token = ""
    refresh_token = ""
    if isinstance(tokens, dict):
        access_token = str(tokens.get("access_token", "") or "")
        refresh_token = str(tokens.get("refresh_token", "") or "")
    if not access_token:
        access_token = str(payload.get("OPENAI_API_KEY", "") or "")
    if not access_token:
        raise ValueError("Codex auth source does not contain an access token.")

    email = _decode_json_web_token_claim(access_token, ["https://api.openai.com/profile", "email"])
    expires_at_ms = _decode_jwt_expiry(access_token)
    return ExternalAuthCredential(
        provider=CODEX_PROVIDER,
        value=access_token,
        auth_kind="api_key",
        source_path=source_path,
        managed_by=binding.managed_by,
        profile_label=email or binding.profile_label,
        refresh_token=refresh_token,
        expires_at_ms=expires_at_ms,
    )


def _load_claude_credential(
    payload: dict[str, Any],
    source_path: Path,
    binding: ExternalAuthBinding,
    *,
    refresh_if_needed: bool,
) -> ExternalAuthCredential:
    """从 Claude 认证源加载凭据（内部函数）
    
    Args:
        payload: 解析后的 JSON 数据
        source_path: 源文件路径
        binding: 外部认证绑定对象
        refresh_if_needed: 是否在需要时刷新凭据
    
    Returns:
        ExternalAuthCredential: 外部凭据对象
    
    Raises:
        ValueError: 未找到访问令牌或凭据过期无法刷新
    """
    claude_oauth = payload.get("claudeAiOauth")
    if not isinstance(claude_oauth, dict):
        raise ValueError("Claude auth source does not contain claudeAiOauth.")

    access_token = str(claude_oauth.get("accessToken", "") or "")
    refresh_token = str(claude_oauth.get("refreshToken", "") or "")
    expires_at_raw = claude_oauth.get("expiresAt")
    if not access_token:
        raise ValueError("Claude auth source does not contain an access token.")

    expires_at_ms = _coerce_int(expires_at_raw)
    credential = ExternalAuthCredential(
        provider=CLAUDE_PROVIDER,
        value=access_token,
        auth_kind="auth_token",
        source_path=source_path,
        managed_by=binding.managed_by,
        profile_label=binding.profile_label,
        refresh_token=refresh_token,
        expires_at_ms=expires_at_ms,
    )
    if refresh_if_needed and is_credential_expired(credential):
        if not refresh_token:
            raise ValueError(
                f"Claude credentials at {source_path} are expired and cannot be refreshed."
            )
        refreshed = refresh_claude_oauth_credential(refresh_token)
        write_claude_credentials(
            source_path,
            access_token=refreshed["access_token"],
            refresh_token=refreshed["refresh_token"],
            expires_at_ms=refreshed["expires_at_ms"],
        )
        credential = ExternalAuthCredential(
            provider=CLAUDE_PROVIDER,
            value=str(refreshed["access_token"]),
            auth_kind="auth_token",
            source_path=source_path,
            managed_by=binding.managed_by,
            profile_label=binding.profile_label,
            refresh_token=str(refreshed["refresh_token"]),
            expires_at_ms=int(refreshed["expires_at_ms"]),
        )
    return credential


def describe_external_binding(binding: ExternalAuthBinding) -> ExternalAuthState:
    """获取外部认证绑定的人类可读状态
    
    Args:
        binding: 外部认证绑定对象
    
    Returns:
        ExternalAuthState: 外部认证状态对象
    """
    source_path = Path(binding.source_path).expanduser()
    if not source_path.exists():
        return ExternalAuthState(
            configured=False,
            state="missing",
            source="missing",
            detail=f"external auth source not found: {source_path}",
        )
    try:
        credential = load_external_credential(binding, refresh_if_needed=False)
    except ValueError as exc:
        return ExternalAuthState(
            configured=False,
            state="invalid",
            source="external",
            detail=str(exc),
        )
    if binding.provider == CLAUDE_PROVIDER and is_credential_expired(credential):
        if credential.refresh_token:
            return ExternalAuthState(
                configured=True,
                state="refreshable",
                source="external",
                detail=f"expired token can be refreshed from {source_path}",
            )
        return ExternalAuthState(
            configured=False,
            state="expired",
            source="external",
            detail=f"expired token at {source_path}",
        )
    return ExternalAuthState(
        configured=True,
        state="configured",
        source="external",
        detail=str(source_path),
    )


def is_credential_expired(credential: ExternalAuthCredential, *, now_ms: int | None = None) -> bool:
    """检查外部凭据是否已过期
    
    Args:
        credential: 外部凭据对象
        now_ms: 当前时间（毫秒），默认使用当前系统时间
    
    Returns:
        bool: 是否已过期
    """
    if credential.expires_at_ms is None:
        return False
    if now_ms is None:
        import time

        now_ms = int(time.time() * 1000)
    return credential.expires_at_ms <= now_ms


def get_claude_code_version() -> str:
    """获取本地安装的 Claude Code 版本，如果未安装则返回回退版本
    
    Returns:
        str: 版本号字符串
    """
    global _claude_code_version_cache
    if _claude_code_version_cache is not None:
        return _claude_code_version_cache
    for command in ("claude", "claude-code"):
        try:
            result = subprocess.run(
                [command, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            continue
        version = (result.stdout or "").strip().split(" ", 1)[0]
        if result.returncode == 0 and version and version[0].isdigit():
            _claude_code_version_cache = version
            return version
    _claude_code_version_cache = CLAUDE_CODE_VERSION_FALLBACK
    return _claude_code_version_cache


def get_claude_code_session_id() -> str:
    """获取此进程的稳定 Claude Code 风格会话标识符
    
    Returns:
        str: UUID 格式的会话 ID
    """
    global _claude_code_session_id
    if _claude_code_session_id is None:
        _claude_code_session_id = str(uuid.uuid4())
    return _claude_code_session_id


def claude_oauth_betas() -> list[str]:
    """获取 Claude OAuth Beta 特性列表，用于 SDK Beta 端点
    
    Returns:
        list[str]: Beta 特性名称列表
    """
    return list(CLAUDE_COMMON_BETAS + CLAUDE_OAUTH_ONLY_BETAS)


def claude_attribution_header() -> str:
    """获取用于系统提示的 Claude Code 计费归属前缀
    
    Returns:
        str: 计费归属头字符串
    """
    version = get_claude_code_version()
    return (
        "x-anthropic-billing-header: "
        f"cc_version={version}; cc_entrypoint=cli;"
    )


def claude_oauth_headers() -> dict[str, str]:
    """获取订阅 OAuth 流量的 Claude Code 风格请求头
    
    Returns:
        dict[str, str]: 请求头字典
    """
    all_betas = ",".join(claude_oauth_betas())
    return {
        "anthropic-beta": all_betas,
        "user-agent": f"claude-cli/{get_claude_code_version()} (external, cli)",
        "x-app": "cli",
        "X-Claude-Code-Session-Id": get_claude_code_session_id(),
    }


def refresh_claude_oauth_credential(refresh_token: str) -> dict[str, Any]:
    """刷新 Claude OAuth 令牌，不修改本地文件
    
    Args:
        refresh_token: 刷新令牌
    
    Returns:
        dict[str, Any]: 包含 access_token、refresh_token、expires_at_ms、scopes 的字典
    
    Raises:
        ValueError: 刷新失败
    """
    if not refresh_token:
        raise ValueError("refresh_token is required")

    payload = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLAUDE_OAUTH_CLIENT_ID,
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": f"claude-cli/{get_claude_code_version()} (external, cli)",
    }
    last_error: Exception | None = None
    for endpoint in CLAUDE_OAUTH_TOKEN_ENDPOINTS:
        request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            continue
        access_token = str(result.get("access_token", "") or "")
        if not access_token:
            raise ValueError("Claude OAuth refresh response missing access_token")
        next_refresh = str(result.get("refresh_token", refresh_token) or refresh_token)
        expires_in = int(result.get("expires_in", 3600) or 3600)
        return {
            "access_token": access_token,
            "refresh_token": next_refresh,
            "expires_at_ms": int(time.time() * 1000) + expires_in * 1000,
            "scopes": result.get("scope"),
        }
    if last_error is not None:
        raise ValueError(f"Claude OAuth refresh failed: {last_error}") from last_error
    raise ValueError("Claude OAuth refresh failed")


def write_claude_credentials(
    source_path: Path,
    *,
    access_token: str,
    refresh_token: str,
    expires_at_ms: int,
) -> None:
    """将刷新的 Claude 凭据写回上游凭据文件
    
    Args:
        source_path: 凭据文件路径
        access_token: 访问令牌
        refresh_token: 刷新令牌
        expires_at_ms: 过期时间（毫秒时间戳）
    """
    existing: dict[str, Any] = {}
    if source_path.exists():
        try:
            existing = json.loads(source_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    previous = existing.get("claudeAiOauth")
    next_oauth: dict[str, Any] = {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expiresAt": expires_at_ms,
    }
    if isinstance(previous, dict):
        for key in ("scopes", "rateLimitTier", "subscriptionType"):
            if key in previous:
                next_oauth[key] = previous[key]
    existing["claudeAiOauth"] = next_oauth
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    try:
        source_path.chmod(0o600)
    except OSError:
        pass


def is_third_party_anthropic_endpoint(base_url: str | None) -> bool:
    """检查是否为使用 Anthropic 兼容 API 的非 Anthropic 端点
    
    Args:
        base_url: 基础 URL
    
    Returns:
        bool: 是否为第三方端点
    """
    if not base_url:
        return False
    normalized = base_url.rstrip("/").lower()
    return "anthropic.com" not in normalized and "claude.com" not in normalized


def _coerce_int(value: Any) -> int | None:
    """将任意值转换为整数（内部函数）
    
    Args:
        value: 任意值
    
    Returns:
        int | None: 转换后的整数或 None
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed.isdigit():
            return int(trimmed)
    return None


def _decode_jwt_expiry(token: str) -> int | None:
    """解码 JWT 令牌的过期时间（内部函数）
    
    Args:
        token: JWT 令牌字符串
    
    Returns:
        int | None: 过期时间（毫秒时间戳）或 None
    """
    exp = _decode_json_web_token_claim(token, ["exp"])
    if exp is None:
        return None
    if isinstance(exp, int):
        return exp * 1000
    if isinstance(exp, float):
        return int(exp * 1000)
    if isinstance(exp, str) and exp.strip().isdigit():
        return int(exp.strip()) * 1000
    return None


def _decode_json_web_token_claim(token: str, path: list[str]) -> Any | None:
    """解码 JWT 令牌中的指定声明（内部函数）
    
    Args:
        token: JWT 令牌字符串
        path: 要获取的声明路径列表
    
    Returns:
        Any | None: 声明值或 None
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        encoded = parts[1]
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception:
        return None

    current: Any = payload
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current
