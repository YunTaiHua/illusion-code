"""
IllusionCode swarm 中的权限同步协议模块
======================================

本模块提供 swarm 工作者与负责人之间的权限请求/响应协调功能。

支持两种流程：
1. 基于文件的流程（目录存储）：
    1. 工作者调用 ``write_permission_request()`` → pending/{id}.json
    2. 负责人调用 ``read_pending_permissions()`` 列出待处理请求
    3. 负责人调用 ``resolve_permission()`` → 移动到 resolved/{id}.json
    4. 工作者调用 ``read_resolved_permission(id)`` 或 ``poll_for_response(id)``

2. 基于邮箱的流程：
    1. 工作者调用 ``send_permission_request_via_mailbox()``
    2. 负责人轮询邮箱，通过 ``send_permission_response_via_mailbox()`` 发送响应
    3. 工作者调用 ``poll_permission_response()`` 在自己的邮箱中轮询

文件路径：
    ~/.illusion/teams/<teamName>/permissions/pending/<id>.json
    ~/.illusion/teams/<teamName>/permissions/resolved/<id>.json

主要组件：
    - SwarmPermissionRequest: 权限请求数据结构
    - SwarmPermissionResponse: 权限响应数据结构
    - PermissionResolution: 权限决议数据结构

使用示例：
    >>> from illusion.swarm.permission_sync import create_permission_request, resolve_permission
    >>> 
    >>> # 创建权限请求
    >>> request = create_permission_request("Edit", "tool_123", {"file_path": "/test.py"})
    >>> 
    >>> # 发送请求（基于文件）
    >>> await write_permission_request(request)
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import string
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

# 导入锁文件和邮箱模块
from illusion.swarm.lockfile import exclusive_file_lock
from illusion.swarm.mailbox import (
    MailboxMessage,
    TeammateMailbox,
    create_permission_request_message,
    create_permission_response_message,
    create_sandbox_permission_request_message,
    create_sandbox_permission_response_message,
    get_team_dir,
    write_to_mailbox,
)

if TYPE_CHECKING:
    from illusion.permissions.checker import PermissionChecker


# ---------------------------------------------------------------------------
# 环境变量辅助函数
# ---------------------------------------------------------------------------


def _get_team_name() -> str | None:
    """获取团队名称环境变量。"""
    return os.environ.get("CLAUDE_CODE_TEAM_NAME")


def _get_agent_id() -> str | None:
    """获取代理 ID 环境变量。"""
    return os.environ.get("CLAUDE_CODE_AGENT_ID")


def _get_agent_name() -> str | None:
    """获取代理名称环境变量。"""
    return os.environ.get("CLAUDE_CODE_AGENT_NAME")


def _get_teammate_color() -> str | None:
    """获取队友颜色环境变量。"""
    return os.environ.get("CLAUDE_CODE_AGENT_COLOR")


# ---------------------------------------------------------------------------
# 只读工具启发式
# ---------------------------------------------------------------------------

# 只读/安全工具集合
_READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {
        "read_file",
        "glob",
        "grep",
        "web_fetch",
        "web_search",
        "task_get",
        "task_list",
        "task_output",
        "cron_list",
    }
)


def _is_read_only(tool_name: str) -> bool:
    """对于被视为安全/只读的工具返回 True。"""
    return tool_name in _READ_ONLY_TOOLS


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class SwarmPermissionRequest:
    """从工作者转发到团队负责人的权限请求。

    所有字段都存在以匹配 TS SwarmPermissionRequestSchema。
    """

    id: str
    """此请求的唯一标识符。"""

    worker_id: str
    """请求工作者的代理 ID（CLAUDE_CODE_AGENT_ID）。"""

    worker_name: str
    """请求工作者的代理名称（CLAUDE_CODE_AGENT_NAME）。"""

    team_name: str
    """用于路由的团队名称。"""

    tool_name: str
    """需要权限的工具名称（例如 'Bash', 'Edit'）。"""

    tool_use_id: str
    """工作者执行上下文中的原始工具使用 ID。"""

    description: str
    """请求操作的人类可读描述。"""

    input: dict[str, Any]
    """序列化的工具输入参数。"""

    # 可选/默认字段
    permission_suggestions: list[Any] = field(default_factory=list)
    """工作者本地权限系统产生的建议规则更新。"""

    worker_color: str | None = None
    """请求工作者的分配颜色（CLAUDE_CODE_AGENT_COLOR）。"""

    status: Literal["pending", "approved", "rejected"] = "pending"
    """请求的当前状态。"""

    resolved_by: Literal["worker", "leader"] | None = None
    """谁解决了请求。"""

    resolved_at: float | None = None
    """解决请求的时间戳（自 epoch 以来的秒数）。"""

    feedback: str | None = None
    """可选的拒绝原因或负责人评论。"""

    updated_input: dict[str, Any] | None = None
    """如果解决者修改了输入则为修改后的输入。"""

    permission_updates: list[Any] | None = None
    """解决期间应用的"始终允许"规则。"""

    created_at: float = field(default_factory=time.time)
    """请求创建时的时间戳。"""

    def to_dict(self) -> dict[str, Any]:
        """将 SwarmPermissionRequest 转换为字典。"""
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "team_name": self.team_name,
            "tool_name": self.tool_name,
            "tool_use_id": self.tool_use_id,
            "description": self.description,
            "input": self.input,
            "permission_suggestions": self.permission_suggestions,
            "worker_color": self.worker_color,
            "status": self.status,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at,
            "feedback": self.feedback,
            "updated_input": self.updated_input,
            "permission_updates": self.permission_updates,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SwarmPermissionRequest":
        """从字典数据创建 SwarmPermissionRequest 实例。"""
        return cls(
            id=data["id"],
            worker_id=data.get("worker_id", data.get("workerId", "")),
            worker_name=data.get("worker_name", data.get("workerName", "")),
            team_name=data.get("team_name", data.get("teamName", "")),
            tool_name=data.get("tool_name", data.get("toolName", "")),
            tool_use_id=data.get("tool_use_id", data.get("toolUseId", "")),
            description=data.get("description", ""),
            input=data.get("input", {}),
            permission_suggestions=data.get(
                "permission_suggestions",
                data.get("permissionSuggestions", []),
            ),
            worker_color=data.get("worker_color", data.get("workerColor")),
            status=data.get("status", "pending"),
            resolved_by=data.get("resolved_by", data.get("resolvedBy")),
            resolved_at=data.get("resolved_at", data.get("resolvedAt")),
            feedback=data.get("feedback"),
            updated_input=data.get("updated_input", data.get("updatedInput")),
            permission_updates=data.get(
                "permission_updates", data.get("permissionUpdates")
            ),
            created_at=data.get("created_at", data.get("createdAt", time.time())),
        )


@dataclass
class PermissionResolution:
    """负责人/工作者解决请求时返回的决议数据。"""

    decision: Literal["approved", "rejected"]
    """决议：批准或拒绝。"""

    resolved_by: Literal["worker", "leader"]
    """谁解决了请求。"""

    feedback: str | None = None
    """如果拒绝则可选的反馈消息。"""

    updated_input: dict[str, Any] | None = None
    """如果解决者修改了输入则为可选的更新输入。"""

    permission_updates: list[Any] | None = None
    """要应用的权限更新（例如"始终允许"规则）。"""


@dataclass
class PermissionResponse:
    """工作者轮询的旧响应类型（向后兼容）。"""

    request_id: str
    """此响应的请求 ID。"""

    decision: Literal["approved", "denied"]
    """决议：批准或拒绝。"""

    timestamp: str
    """响应创建时的 ISO 时间戳。"""

    feedback: str | None = None
    """如果拒绝则可选的反馈消息。"""

    updated_input: dict[str, Any] | None = None
    """如果解决者修改了输入则为可选的更新输入。"""

    permission_updates: list[Any] | None = None
    """要应用的权限更新。"""


@dataclass
class SwarmPermissionResponse:
    """从负责人发送回请求工作者的响应。"""

    request_id: str
    """此响应的 ``SwarmPermissionRequest`` 的 ID。"""

    allowed: bool
    """如果工具使用被批准则为 True。"""

    feedback: str | None = None
    """可选的拒绝原因或负责人评论。"""

    updated_rules: list[dict[str, Any]] = field(default_factory=list)
    """负责人决定应用的权限规则更新。"""


# ---------------------------------------------------------------------------
# 请求 ID 生成
# ---------------------------------------------------------------------------


def generate_request_id() -> str:
    """生成唯一的权限请求 ID。

    格式：``perm-{timestamp_ms}-{random7}``，匹配 TS 实现：
    ``perm-${Date.now()}-${Math.random().toString(36).substring(2, 9)}``
    """
    ts = int(time.time() * 1000)
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=7))
    return f"perm-{ts}-{rand}"


def generate_sandbox_request_id() -> str:
    """生成唯一的沙箱权限请求 ID。

    格式：``sandbox-{timestamp_ms}-{random7}``。
    """
    ts = int(time.time() * 1000)
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=7))
    return f"sandbox-{ts}-{rand}"


# ---------------------------------------------------------------------------
# 权限目录辅助函数
# ---------------------------------------------------------------------------


def get_permission_dir(team_name: str) -> Path:
    """返回 ~/.illusion/teams/{teamName}/permissions/"""
    return get_team_dir(team_name) / "permissions"


def _get_pending_dir(team_name: str) -> Path:
    """获取 pending 目录路径。"""
    return get_permission_dir(team_name) / "pending"


def _get_resolved_dir(team_name: str) -> Path:
    """获取 resolved 目录路径。"""
    return get_permission_dir(team_name) / "resolved"


def _ensure_permission_dirs(team_name: str) -> None:
    """确保权限目录存在。"""
    for d in (
        get_permission_dir(team_name),
        _get_pending_dir(team_name),
        _get_resolved_dir(team_name),
    ):
        d.mkdir(parents=True, exist_ok=True)


def _pending_request_path(team_name: str, request_id: str) -> Path:
    """获取 pending 请求文件路径。"""
    return _get_pending_dir(team_name) / f"{request_id}.json"


def _resolved_request_path(team_name: str, request_id: str) -> Path:
    """获取 resolved 请求文件路径。"""
    return _get_resolved_dir(team_name) / f"{request_id}.json"


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------


def create_permission_request(
    tool_name: str,
    tool_use_id: str,
    tool_input: dict[str, Any],
    description: str = "",
    permission_suggestions: list[Any] | None = None,
    team_name: str | None = None,
    worker_id: str | None = None,
    worker_name: str | None = None,
    worker_color: str | None = None,
) -> SwarmPermissionRequest:
    """使用生成的 ID 构建新的 :class:`SwarmPermissionRequest`。

    缺少的工作者/团队字段从环境变量读取
    （``CLAUDE_CODE_AGENT_ID``、``CLAUDE_CODE_AGENT_NAME``、
    ``CLAUDE_CODE_TEAM_NAME``、``CLAUDE_CODE_AGENT_COLOR``）。

    Args:
        tool_name: 请求权限的工具名称。
        tool_use_id: 执行上下文中的原始工具使用 ID。
        tool_input: 工具的输入参数。
        description: 操作的可选人类可读描述。
        permission_suggestions: 可选的建议权限规则字典列表。
        team_name: 团队名称（回退到 ``CLAUDE_CODE_TEAM_NAME``）。
        worker_id: 工作者代理 ID（回退到 ``CLAUDE_CODE_AGENT_ID``）。
        worker_name: 工作者代理名称（回退到 ``CLAUDE_CODE_AGENT_NAME``）。
        worker_color: 工作者颜色（回退到 ``CLAUDE_CODE_AGENT_COLOR``）。

    Returns:
        处于 *pending* 状态的新 :class:`SwarmPermissionRequest`。

    Raises:
        ValueError: 如果 team_name、worker_id 或 worker_name 无法解析。
    """
    # 解析环境变量或使用提供的值
    resolved_team = team_name or _get_team_name() or ""
    resolved_id = worker_id or _get_agent_id() or ""
    resolved_name = worker_name or _get_agent_name() or ""
    resolved_color = worker_color or _get_teammate_color()

    return SwarmPermissionRequest(
        id=generate_request_id(),
        worker_id=resolved_id,
        worker_name=resolved_name,
        worker_color=resolved_color,
        team_name=resolved_team,
        tool_name=tool_name,
        tool_use_id=tool_use_id,
        description=description,
        input=tool_input,
        permission_suggestions=permission_suggestions or [],
        status="pending",
        created_at=time.time(),
    )


# ---------------------------------------------------------------------------
# 基于文件的存储：写入/读取/解决/清理
# ---------------------------------------------------------------------------


def _sync_write_permission_request(
    request: SwarmPermissionRequest,
) -> SwarmPermissionRequest:
    """同步写入权限请求。"""
    _ensure_permission_dirs(request.team_name)
    pending_path = _pending_request_path(request.team_name, request.id)
    lock_path = _get_pending_dir(request.team_name) / ".lock"
    tmp_path = pending_path.with_suffix(".json.tmp")

    with exclusive_file_lock(lock_path):
        tmp_path.write_text(json.dumps(request.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp_path, pending_path)
    return request


async def write_permission_request(
    request: SwarmPermissionRequest,
) -> SwarmPermissionRequest:
    """将 *request* 写入 pending 目录，使用文件锁定。

    当工作者代理需要负责人批准时由工作者代理调用。

    Args:
        request: 要持久化的权限请求。

    Returns:
        写入的请求（同一对象，便于使用）。
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_write_permission_request, request)


async def read_pending_permissions(
    team_name: str | None = None,
) -> list[SwarmPermissionRequest]:
    """读取团队的所有待处理权限请求。

    由团队负责人调用以查看需要关注的请求。
    请求按最旧优先排序返回。

    Args:
        team_name: 团队名称（回退到 ``CLAUDE_CODE_TEAM_NAME``）。

    Returns:
        待处理 :class:`SwarmPermissionRequest` 对象列表。
    """
    team = team_name or _get_team_name()
    if not team:
        return []

    pending_dir = _get_pending_dir(team)
    if not pending_dir.exists():
        return []

    requests: list[SwarmPermissionRequest] = []
    for path in sorted(pending_dir.glob("*.json")):
        if path.name == ".lock":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            requests.append(SwarmPermissionRequest.from_dict(data))
        except (json.JSONDecodeError, KeyError):
            continue

    requests.sort(key=lambda r: r.created_at)
    return requests


async def read_resolved_permission(
    request_id: str,
    team_name: str | None = None,
) -> SwarmPermissionRequest | None:
    """按 ID 读取已解决的权限请求。

    由工作者调用以检查其请求是否已解决。

    Args:
        request_id: 要查找的权限请求 ID。
        team_name: 团队名称（回退到 ``CLAUDE_CODE_TEAM_NAME``）。

    Returns:
        已解决的 :class:`SwarmPermissionRequest`，如果尚未解决则返回 ``None``。
    """
    team = team_name or _get_team_name()
    if not team:
        return None

    resolved_path = _resolved_request_path(team, request_id)
    if not resolved_path.exists():
        return None

    try:
        data = json.loads(resolved_path.read_text(encoding="utf-8"))
        return SwarmPermissionRequest.from_dict(data)
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def _sync_resolve_permission(
    request_id: str,
    resolution: PermissionResolution,
    team: str,
) -> bool:
    """同步解决权限请求。"""
    _ensure_permission_dirs(team)
    pending_path = _pending_request_path(team, request_id)
    resolved_path = _resolved_request_path(team, request_id)
    lock_path = _get_pending_dir(team) / ".lock"
    tmp_path = resolved_path.with_suffix(".json.tmp")

    with exclusive_file_lock(lock_path):
        if not pending_path.exists():
            return False

        try:
            data = json.loads(pending_path.read_text(encoding="utf-8"))
            request = SwarmPermissionRequest.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return False

        # 构建已解决的请求
        resolved_request = SwarmPermissionRequest(
            id=request.id,
            worker_id=request.worker_id,
            worker_name=request.worker_name,
            worker_color=request.worker_color,
            team_name=request.team_name,
            tool_name=request.tool_name,
            tool_use_id=request.tool_use_id,
            description=request.description,
            input=request.input,
            permission_suggestions=request.permission_suggestions,
            status="approved" if resolution.decision == "approved" else "rejected",
            resolved_by=resolution.resolved_by,
            resolved_at=time.time(),
            feedback=resolution.feedback,
            updated_input=resolution.updated_input,
            permission_updates=resolution.permission_updates,
            created_at=request.created_at,
        )

        # 写入 resolved 目录并删除 pending
        tmp_path.write_text(
            json.dumps(resolved_request.to_dict(), indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, resolved_path)
        try:
            pending_path.unlink()
        except OSError:
            pass

    return True


async def resolve_permission(
    request_id: str,
    resolution: PermissionResolution,
    team_name: str | None = None,
) -> bool:
    """解决权限请求，将其从 pending/ 移动到 resolved/。

    由团队负责人（或工作者在自我解决情况下）调用。

    Args:
        request_id: 要解决的权限请求 ID。
        resolution: 决议数据（decision、resolvedBy 等）。
        team_name: 团队名称（回退到 ``CLAUDE_CODE_TEAM_NAME``）。

    Returns:
        如果找到并解决了请求返回 ``True``，否则返回 ``False``。
    """
    team = team_name or _get_team_name()
    if not team:
        return False
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _sync_resolve_permission, request_id, resolution, team
    )


def _sync_cleanup_old_resolutions(team: str, max_age_seconds: float) -> int:
    """同步清理旧的已解决权限文件。"""
    resolved_dir = _get_resolved_dir(team)
    if not resolved_dir.exists():
        return 0

    now = time.time()
    cleaned = 0

    for path in resolved_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            resolved_at = data.get("resolved_at") or data.get("created_at", 0)
            if now - resolved_at >= max_age_seconds:
                path.unlink()
                cleaned += 1
        except (json.JSONDecodeError, KeyError, OSError):
            try:
                path.unlink()
                cleaned += 1
            except OSError:
                pass

    return cleaned


async def cleanup_old_resolutions(
    team_name: str | None = None,
    max_age_seconds: float = 3600.0,
) -> int:
    """清理旧的已解决权限文件。

    定期调用以防止文件积累。

    Args:
        team_name: 团队名称（回退到 ``CLAUDE_CODE_TEAM_NAME``）。
        max_age_seconds: 最大年龄（秒）（默认：1 小时）。

    Returns:
        删除的文件数量。
    """
    team = team_name or _get_team_name()
    if not team:
        return 0
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _sync_cleanup_old_resolutions, team, max_age_seconds
    )


async def delete_resolved_permission(
    request_id: str,
    team_name: str | None = None,
) -> bool:
    """在工作者处理后删除已解决的权限文件。

    Args:
        request_id: 权限请求 ID。
        team_name: 团队名称（回退到 ``CLAUDE_CODE_TEAM_NAME``）。

    Returns:
        如果找到并删除了文件返回 ``True``，否则返回 ``False``。
    """
    team = team_name or _get_team_name()
    if not team:
        return False

    resolved_path = _resolved_request_path(team, request_id)
    try:
        resolved_path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 旧版/向后兼容辅助函数
# ---------------------------------------------------------------------------


async def poll_for_response(
    request_id: str,
    _agent_name: str | None = None,
    team_name: str | None = None,
) -> PermissionResponse | None:
    """轮询权限响应（工作者端便捷函数）。

    将已解决的请求转换为更简单的旧版响应格式。

    Args:
        request_id: 要检查的权限请求 ID。
        _agent_name: 未使用；为 API 兼容性保留。
        team_name: 团队名称（回退到 ``CLAUDE_CODE_TEAM_NAME``）。

    Returns:
        :class:`PermissionResponse`，如果尚未解决则返回 ``None``。
    """
    from datetime import datetime, timezone

    resolved = await read_resolved_permission(request_id, team_name)
    if not resolved:
        return None

    ts = resolved.resolved_at or resolved.created_at
    return PermissionResponse(
        request_id=resolved.id,
        decision="approved" if resolved.status == "approved" else "denied",
        timestamp=datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3]
        + "Z",
        feedback=resolved.feedback,
        updated_input=resolved.updated_input,
        permission_updates=resolved.permission_updates,
    )


async def remove_worker_response(
    request_id: str,
    _agent_name: str | None = None,
    team_name: str | None = None,
) -> None:
    """在工作者处理后移除工作者的响应（delete_resolved_permission 的别名）。"""
    await delete_resolved_permission(request_id, team_name)


# 别名：submitPermissionRequest → writePermissionRequest
submit_permission_request = write_permission_request


# ---------------------------------------------------------------------------
# 团队负责人/工作者角色检测
# ---------------------------------------------------------------------------


def is_team_leader(team_name: str | None = None) -> bool:
    """如果当前代理是团队负责人则返回 True。

    团队负责人没有设置代理 ID，或其 ID 是 'team-lead'。
    """
    team = team_name or _get_team_name()
    if not team:
        return False
    agent_id = _get_agent_id()
    return not agent_id or agent_id == "team-lead"


def is_swarm_worker() -> bool:
    """如果当前代理是 swarm 中的工作者则返回 True。"""
    team_name = _get_team_name()
    agent_id = _get_agent_id()
    return bool(team_name) and bool(agent_id) and not is_team_leader()


# ---------------------------------------------------------------------------
# 负责人名称查找
# ---------------------------------------------------------------------------


async def get_leader_name(team_name: str | None = None) -> str | None:
    """从团队文件获取负责人的代理名称。

    这需要将权限请求寻址到负责人的邮箱。

    Args:
        team_name: 团队名称（回退到 ``CLAUDE_CODE_TEAM_NAME``）。

    Returns:
        负责人的名称字符串，如果团队文件缺失则返回 ``None``。
        如果未找到 lead 成员则回退到 ``'team-lead'``。
    """
    from illusion.swarm.team_lifecycle import read_team_file_async

    team = team_name or _get_team_name()
    if not team:
        return None

    team_file = await read_team_file_async(team)
    if not team_file:
        return None

    lead_id = team_file.lead_agent_id
    if lead_id and lead_id in team_file.members:
        return team_file.members[lead_id].name

    return "team-lead"


# ---------------------------------------------------------------------------
# 基于邮箱的权限发送/接收
# ---------------------------------------------------------------------------


async def send_permission_request_via_mailbox(
    request: SwarmPermissionRequest,
) -> bool:
    """通过邮箱系统将权限请求发送到负责人。

    这是转发权限请求的基于邮箱的方法。
    将 ``permission_request`` 消息写入负责人的邮箱。

    Args:
        request: 要发送的权限请求。

    Returns:
        如果消息发送成功返回 ``True``。
    """
    leader_name = await get_leader_name(request.team_name)
    if not leader_name:
        return False

    try:
        msg = create_permission_request_message(
            sender=request.worker_name,
            recipient=leader_name,
            request_data={
                "request_id": request.id,
                "agent_id": request.worker_name,
                "tool_name": request.tool_name,
                "tool_use_id": request.tool_use_id,
                "description": request.description,
                "input": request.input,
                "permission_suggestions": request.permission_suggestions,
            },
        )

        await write_to_mailbox(
            leader_name,
            {
                "from": request.worker_name,
                "text": json.dumps(msg.payload),
                "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()
                ),
                "color": request.worker_color,
            },
            request.team_name,
        )
        return True
    except OSError:
        return False


async def send_permission_response_via_mailbox(
    worker_name: str,
    resolution: PermissionResolution,
    request_id: str,
    team_name: str | None = None,
) -> bool:
    """通过邮箱系统将权限响应发送到工作者。

    在负责人批准/拒绝权限请求时调用。

    Args:
        worker_name: 要发送响应的工作者名称。
        resolution: 权限决议。
        request_id: 原始请求 ID。
        team_name: 团队名称（回退到 ``CLAUDE_CODE_TEAM_NAME``）。

    Returns:
        如果消息发送成功返回 ``True``。
    """
    team = team_name or _get_team_name()
    if not team:
        return False

    sender_name = _get_agent_name() or "team-lead"
    subtype = "success" if resolution.decision == "approved" else "error"

    try:
        msg = create_permission_response_message(
            sender=sender_name,
            recipient=worker_name,
            response_data={
                "request_id": request_id,
                "subtype": subtype,
                "error": resolution.feedback if subtype == "error" else None,
                "updated_input": resolution.updated_input,
                "permission_updates": resolution.permission_updates,
            },
        )

        await write_to_mailbox(
            worker_name,
            {
                "from": sender_name,
                "text": json.dumps(msg.payload),
                "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()
                ),
            },
            team,
        )
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 沙箱权限邮箱辅助函数
# ---------------------------------------------------------------------------


async def send_sandbox_permission_request_via_mailbox(
    host: str,
    request_id: str,
    team_name: str | None = None,
) -> bool:
    """通过邮箱系统将沙箱权限请求发送到负责人。

    当沙箱运行时需要网络访问批准时由工作者调用。

    Args:
        host: 请求网络访问的主机。
        request_id: 此请求的唯一 ID。
        team_name: 可选的团队名称。

    Returns:
        如果消息发送成功返回 ``True``。
    """
    team = team_name or _get_team_name()
    if not team:
        return False

    leader_name = await get_leader_name(team)
    if not leader_name:
        return False

    worker_id = _get_agent_id()
    worker_name = _get_agent_name()
    worker_color = _get_teammate_color()

    if not worker_id or not worker_name:
        return False

    try:
        msg = create_sandbox_permission_request_message(
            sender=worker_name,
            recipient=leader_name,
            request_data={
                "requestId": request_id,
                "workerId": worker_id,
                "workerName": worker_name,
                "workerColor": worker_color,
                "host": host,
            },
        )

        await write_to_mailbox(
            leader_name,
            {
                "from": worker_name,
                "text": json.dumps(msg.payload),
                "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()
                ),
                "color": worker_color,
            },
            team,
        )
        return True
    except OSError:
        return False


async def send_sandbox_permission_response_via_mailbox(
    worker_name: str,
    request_id: str,
    host: str,
    allow: bool,
    team_name: str | None = None,
) -> bool:
    """通过邮箱系统将沙箱权限响应发送到工作者。

    在负责人批准/拒绝沙箱网络访问请求时调用。

    Args:
        worker_name: 要发送响应的工作者名称。
        request_id: 原始请求 ID。
        host: 被批准/拒绝的主机。
        allow: 是否允许连接。
        team_name: 可选的团队名称。

    Returns:
        如果消息发送成功返回 ``True``。
    """
    team = team_name or _get_team_name()
    if not team:
        return False

    sender_name = _get_agent_name() or "team-lead"

    try:
        msg = create_sandbox_permission_response_message(
            sender=sender_name,
            recipient=worker_name,
            response_data={
                "requestId": request_id,
                "host": host,
                "allow": allow,
            },
        )

        await write_to_mailbox(
            worker_name,
            {
                "from": sender_name,
                "text": json.dumps(msg.payload),
                "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()
                ),
            },
            team,
        )
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 工作者辅助函数：发送请求/轮询响应（原始的仅邮箱方法）
# ---------------------------------------------------------------------------


async def send_permission_request(
    request: SwarmPermissionRequest,
    team_name: str,
    worker_id: str,
    leader_id: str = "leader",
) -> None:
    """序列化 *request* 并写入负责人的邮箱。

    这是原始的结构化有效负载方法。对于新代码优先使用
    :func:`send_permission_request_via_mailbox`。

    Args:
        request: 要转发的权限请求。
        team_name: 用于邮箱路由的 swarm 团队名称。
        worker_id: 发送工作者的代理 ID。
        leader_id: 负责人的代理 ID（默认 ``"leader"``）。
    """
    payload: dict[str, Any] = {
        "request_id": request.id,
        "tool_name": request.tool_name,
        "tool_use_id": request.tool_use_id,
        "input": request.input,
        "description": request.description,
        "permission_suggestions": request.permission_suggestions,
        "worker_id": worker_id,
    }
    msg = MailboxMessage(
        id=str(uuid.uuid4()),
        type="permission_request",
        sender=worker_id,
        recipient=leader_id,
        payload=payload,
        timestamp=time.time(),
    )
    leader_mailbox = TeammateMailbox(team_name, leader_id)
    await leader_mailbox.write(msg)


async def poll_permission_response(
    team_name: str,
    worker_id: str,
    request_id: str,
    timeout: float = 60.0,
) -> SwarmPermissionResponse | None:
    """轮询工作者自己的邮箱直到收到匹配的 ``permission_response``。

    每 0.5 秒检查一次，最长 *timeout* 秒。当找到匹配
    *request_id* 的响应时，消息被标记为已读并返回解码的
    :class:`SwarmPermissionResponse`。

    Args:
        team_name: swarm 团队名称。
        worker_id: 工作者代理 ID（拥有此邮箱）。
        request_id: 要匹配的 ``SwarmPermissionRequest.id``。
        timeout: 超时前等待的最大秒数。

    Returns:
        :class:`SwarmPermissionResponse`，或超时时返回 ``None``。
    """
    worker_mailbox = TeammateMailbox(team_name, worker_id)
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        messages = await worker_mailbox.read_all(unread_only=True)
        for msg in messages:
            if msg.type == "permission_response":
                payload = msg.payload
                if payload.get("request_id") == request_id:
                    await worker_mailbox.mark_read(msg.id)
                    return SwarmPermissionResponse(
                        request_id=payload["request_id"],
                        allowed=bool(payload.get("allowed", False)),
                        feedback=payload.get("feedback"),
                        updated_rules=payload.get("updated_rules", []),
                    )
        await asyncio.sleep(0.5)

    return None


# ---------------------------------------------------------------------------
# 负责人辅助函数：评估并发送响应
# ---------------------------------------------------------------------------


async def handle_permission_request(
    request: SwarmPermissionRequest,
    checker: "PermissionChecker",
) -> SwarmPermissionResponse:
    """使用现有的 :class:`PermissionChecker` 评估 *request*。

    只读工具会自动批准，无需咨询检查器。对于
    所有其他工具，调用检查器的 ``evaluate`` 方法；如果工具被允许
    或只需要确认（且没有阻止它），则批准；否则拒绝。

    Args:
        request: 来自工作者的传入权限请求。
        checker: 已配置的 :class:`~illusion.permissions.checker.PermissionChecker`。

    Returns:
        包含决策的 :class:`SwarmPermissionResponse`。
    """
    # 只读工具自动批准
    if _is_read_only(request.tool_name):
        return SwarmPermissionResponse(
            request_id=request.id,
            allowed=True,
            feedback=None,
        )

    # 获取文件路径和命令参数
    file_path: str | None = (
        request.input.get("file_path")  # type: ignore[assignment]
        or request.input.get("path")
        or None
    )
    command: str | None = request.input.get("command")  # type: ignore[assignment]

    # 评估请求
    decision = checker.evaluate(
        request.tool_name,
        is_read_only=False,
        file_path=file_path,
        command=command,
    )

    allowed = decision.allowed
    feedback: str | None = None if allowed else decision.reason

    return SwarmPermissionResponse(
        request_id=request.id,
        allowed=allowed,
        feedback=feedback,
    )


# ---------------------------------------------------------------------------
# 负责人辅助函数：将响应写回工作者邮箱
# ---------------------------------------------------------------------------


async def send_permission_response(
    response: SwarmPermissionResponse,
    team_name: str,
    worker_id: str,
    leader_id: str = "leader",
) -> None:
    """将 *response* 写入工作者的邮箱。

    这是原始的结构化有效负载方法。对于新代码优先使用
    :func:`send_permission_response_via_mailbox`。

    Args:
        response: 要发送的决议。
        team_name: swarm 团队名称。
        worker_id: 目标工作者的代理 ID。
        leader_id: 发送负责人的代理 ID（默认 ``"leader"``）。
    """
    payload: dict[str, Any] = {
        "request_id": response.request_id,
        "allowed": response.allowed,
        "feedback": response.feedback,
        "updated_rules": response.updated_rules,
    }
    msg = MailboxMessage(
        id=str(uuid.uuid4()),
        type="permission_response",
        sender=leader_id,
        recipient=worker_id,
        payload=payload,
        timestamp=time.time(),
    )
    worker_mailbox = TeammateMailbox(team_name, worker_id)
    await worker_mailbox.write(msg)
