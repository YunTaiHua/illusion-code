"""
GitHub Copilot OAuth 设备流认证模块
===================================

本模块实现 GitHub Copilot OAuth 设备流认证流程。

认证流程：
    1. 请求设备代码 → 用户访问 URL 并输入代码
    2. 轮询 OAuth 令牌 → 获取 GitHub 访问令牌
    3. 直接使用令牌 → 将令牌用于 Copilot API

支持两种部署类型：
    - github.com — 公共 GitHub，API 地址为 https://api.githubcopilot.com
    - enterprise — GitHub Enterprise（数据驻留/自托管），
      API 地址为 https://copilot-api.<domain>

GitHub OAuth 令牌（可选的企业 URL）持久化到 ~/.illusion/copilot_auth.json。

类说明：
    - DeviceCodeResponse: GitHub 设备代码端点解析响应
    - CopilotAuthInfo: Copilot 持久化和运行时认证状态

函数说明：
    - request_device_code: 启动 OAuth 设备流
    - poll_for_access_token: 轮询获取访问令牌
    - save_copilot_auth: 保存认证信息
    - load_copilot_auth: 加载认证信息
    - clear_github_token: 清除认证信息

使用示例：
    >>> from illusion.api.copilot_auth import request_device_code, poll_for_access_token
    >>> code = request_device_code()
    >>> print(f"请访问 {code.verification_uri} 并输入代码: {code.user_code}")
    >>> token = poll_for_access_token(code.device_code, code.interval)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from illusion.config.paths import get_config_dir

# 模块级日志记录器
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# OpenCode 为 Copilot 集成的 OAuth 客户端 ID
COPILOT_CLIENT_ID = "Ov23li8tweQw6odWQebz"

# Copilot 默认 API 基础地址
COPILOT_DEFAULT_API_BASE = "https://api.githubcopilot.com"

# 轮询安全边距（秒），避免服务端速率限制
_POLL_SAFETY_MARGIN = 3.0

# 认证文件名
_AUTH_FILE_NAME = "copilot_auth.json"


def copilot_api_base(enterprise_url: str | None = None) -> str:
    """返回 Copilot API 基础 URL
    
    公共 GitHub 为 https://api.githubcopilot.com。
    企业版为 https://copilot-api.<domain>。
    
    Args:
        enterprise_url: 企业域名（可选）
    
    Returns:
        str: API 基础 URL
    """
    if enterprise_url:
        domain = enterprise_url.replace("https://", "").replace("http://", "").rstrip("/")
        return f"https://copilot-api.{domain}"
    return COPILOT_DEFAULT_API_BASE


# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceCodeResponse:
    """GitHub 设备代码端点解析响应
    
    Attributes:
        device_code: 设备代码
        user_code: 用户代码
        verification_uri: 验证 URI
        interval: 轮询间隔（秒）
        expires_in: 过期时间（秒）
    """

    device_code: str
    user_code: str
    verification_uri: str
    interval: int
    expires_in: int


@dataclass
class CopilotAuthInfo:
    """Copilot 持久化和运行时认证状态
    
    Attributes:
        github_token: GitHub OAuth 令牌
        enterprise_url: 企业 URL（可选）
    """

    github_token: str
    enterprise_url: str | None = None

    @property
    def api_base(self) -> str:
        """返回 API 基础地址"""
        return copilot_api_base(self.enterprise_url)


# ---------------------------------------------------------------------------
# 持久化辅助函数
# ---------------------------------------------------------------------------


def _auth_file_path() -> Path:
    """获取认证文件路径"""
    return get_config_dir() / _AUTH_FILE_NAME


def save_copilot_auth(token: str, *, enterprise_url: str | None = None) -> None:
    """将 GitHub OAuth 令牌（可选的企业 URL）持久化到磁盘
    
    Args:
        token: GitHub OAuth 令牌
        enterprise_url: 企业 URL（可选）
    """
    path = _auth_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"github_token": token}
    if enterprise_url:
        payload["enterprise_url"] = enterprise_url
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    # 尝试限制文件权限（Windows 上忽略）
    try:
        path.chmod(0o600)
    except OSError:
        pass
    log.info("Copilot auth saved to %s", path)


def load_copilot_auth() -> CopilotAuthInfo | None:
    """加载持久化的 Copilot 认证，返回 None 表示未认证
    
    Returns:
        CopilotAuthInfo | None: 认证信息或 None
    """
    path = _auth_file_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        token = data.get("github_token")
        if not token:
            return None
        return CopilotAuthInfo(
            github_token=token,
            enterprise_url=data.get("enterprise_url"),
        )
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        log.warning("Failed to read Copilot auth file: %s", exc)
        return None


# 保持向后兼容的别名
save_github_token = save_copilot_auth


def load_github_token() -> str | None:
    """仅加载持久化的 GitHub OAuth 令牌，返回 None 表示未认证
    
    Returns:
        str | None: 令牌或 None
    """
    info = load_copilot_auth()
    return info.github_token if info else None


def clear_github_token() -> None:
    """删除持久化的 Copilot 认证"""
    path = _auth_file_path()
    if path.exists():
        path.unlink()
        log.info("Copilot auth cleared.")


# ---------------------------------------------------------------------------
# OAuth 设备流（同步 — 由 CLI 调用）
# ---------------------------------------------------------------------------


def request_device_code(
    *,
    client_id: str = COPILOT_CLIENT_ID,
    github_domain: str = "github.com",
) -> DeviceCodeResponse:
    """启动 OAuth 设备流并返回设备/用户代码
    
    Args:
        client_id: OAuth 客户端 ID（可选）
        github_domain: GitHub 域名（可选）
    
    Returns:
        DeviceCodeResponse: 设备代码响应
    """
    url = f"https://{github_domain}/login/device/code"
    resp = httpx.post(
        url,
        json={"client_id": client_id, "scope": "read:user"},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return DeviceCodeResponse(
        device_code=data["device_code"],
        user_code=data["user_code"],
        verification_uri=data["verification_uri"],
        interval=data.get("interval", 5),
        expires_in=data.get("expires_in", 900),
    )


def poll_for_access_token(
    device_code: str,
    interval: int,
    *,
    client_id: str = COPILOT_CLIENT_ID,
    github_domain: str = "github.com",
    timeout: float = 900,
    progress_callback: Any | None = None,
) -> str:
    """轮询 GitHub 直到用户授权，返回 OAuth 访问令牌
    
    progress_callback（如果提供）在每次轮询前调用 (poll_number, elapsed_seconds)，
    以便调用者显示进度反馈。
    
    Args:
        device_code: 设备代码
        interval: 轮询间隔
        client_id: OAuth 客户端 ID（可选）
        github_domain: GitHub 域名（可选）
        timeout: 超时时间（可选，默认 900 秒）
        progress_callback: 进度回调（可选）
    
    Returns:
        str: OAuth 访问令牌
    
    Raises:
        RuntimeError: 过期或意外错误
    """
    url = f"https://{github_domain}/login/oauth/access_token"
    poll_interval = float(interval)
    deadline = time.monotonic() + timeout
    start = time.monotonic()
    poll_count = 0

    while time.monotonic() < deadline:
        time.sleep(poll_interval + _POLL_SAFETY_MARGIN)
        poll_count += 1
        if progress_callback is not None:
            progress_callback(poll_count, time.monotonic() - start)
        resp = httpx.post(
            url,
            json={
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        # 成功返回令牌
        if "access_token" in data:
            return data["access_token"]

        # 处理错误
        error = data.get("error", "")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            server_interval = data.get("interval")
            if isinstance(server_interval, (int, float)) and server_interval > 0:
                poll_interval = float(server_interval)
            else:
                poll_interval += 5.0
            continue
        # 其他错误为终止错误
        desc = data.get("error_description", error)
        raise RuntimeError(f"OAuth device flow failed: {desc}")

    raise RuntimeError("OAuth device flow timed out waiting for user authorisation.")
