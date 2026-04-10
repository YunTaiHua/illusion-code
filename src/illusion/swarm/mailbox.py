"""
基于文件的异步消息队列模块
==========================

本模块为 IllusionCode swarm 中的负责人-工作者通信提供基于文件的异步消息队列。

每条消息存储为单独的 JSON 文件：
    ~/.illusion/teams/<team>/agents/<agent_id>/inbox/<timestamp>_<message_id>.json

原子写入使用 .tmp 文件后跟 os.rename 以防止部分读取。

主要组件：
    - MailboxMessage: 邮箱消息数据类
    - TeammateMailbox: 队友邮箱类
    - get_team_dir: 获取团队目录
    - get_agent_mailbox_dir: 获取代理邮箱目录

消息类型：
    - user_message: 用户消息
    - permission_request: 权限请求
    - permission_response: 权限响应
    - sandbox_permission_request: 沙箱权限请求
    - sandbox_permission_response: 沙箱权限响应
    - shutdown: 关闭消息
    - idle_notification: 空闲通知

使用示例：
    >>> from illusion.swarm.mailbox import TeammateMailbox, MailboxMessage
    >>> 
    >>> # 创建邮箱
    >>> mailbox = TeammateMailbox("my-team", "researcher")
    >>> 
    >>> # 写入消息
    >>> msg = MailboxMessage(...)
    >>> await mailbox.write(msg)
    >>> 
    >>> # 读取消息
    >>> messages = await mailbox.read_all()
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# 导入锁文件模块
from illusion.swarm.lockfile import exclusive_file_lock


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

# 消息类型字面量
MessageType = Literal[
    "user_message",
    "permission_request",
    "permission_response",
    "sandbox_permission_request",
    "sandbox_permission_response",
    "shutdown",
    "idle_notification",
]


@dataclass
class MailboxMessage:
    """在 swarm 代理之间交换的单个消息。"""

    id: str
    type: MessageType
    sender: str
    recipient: str
    payload: dict[str, Any]
    timestamp: float
    read: bool = False

    # ------------------------------------------------------------------
    # 序列化辅助函数
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """将 MailboxMessage 转换为字典。"""
        return {
            "id": self.id,
            "type": self.type,
            "sender": self.sender,
            "recipient": self.recipient,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "read": self.read,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MailboxMessage":
        """从字典创建 MailboxMessage 实例。"""
        return cls(
            id=data["id"],
            type=data["type"],
            sender=data["sender"],
            recipient=data["recipient"],
            payload=data.get("payload", {}),
            timestamp=data["timestamp"],
            read=data.get("read", False),
        )


# ---------------------------------------------------------------------------
# 目录辅助函数
# ---------------------------------------------------------------------------


def get_team_dir(team_name: str) -> Path:
    """返回 ~/.illusion/teams/<team_name>/"""
    base = Path.home() / ".illusion" / "teams" / team_name
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_agent_mailbox_dir(team_name: str, agent_id: str) -> Path:
    """返回 ~/.illusion/teams/<team_name>/agents/<agent_id>/inbox/"""
    inbox = get_team_dir(team_name) / "agents" / agent_id / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    return inbox


# ---------------------------------------------------------------------------
# TeammateMailbox
# ---------------------------------------------------------------------------


class TeammateMailbox:
    """团队中单个代理的基于文件的邮箱。

    每条消息存在于其自己的 JSON 文件中，命名为 ``<timestamp>_<id>.json``
    在代理的 inbox 目录中。写入是原子的：有效负载首先写入
    ``.tmp`` 文件，然后重命名到目标位置，以便读者永远不会看到部分消息。
    """

    def __init__(self, team_name: str, agent_id: str) -> None:
        """初始化邮箱。"""
        self.team_name = team_name
        self.agent_id = agent_id

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def get_mailbox_dir(self) -> Path:
        """返回 inbox 目录路径，必要时创建。"""
        return get_agent_mailbox_dir(self.team_name, self.agent_id)

    def _lock_path(self) -> Path:
        """获取写入锁文件路径。"""
        return self.get_mailbox_dir() / ".write_lock"

    async def write(self, msg: MailboxMessage) -> None:
        """原子性地将 *msg* 作为 JSON 文件写入 inbox。

        文件首先写入 ``<name>.tmp`` 然后重命名到 inbox 目录，
        以便并发读者永远不会观察到部分写入。

        此方法使用线程池进行阻塞 I/O 操作，并获取独占锁以防止并发写入冲突。
        """
        inbox = self.get_mailbox_dir()
        filename = f"{msg.timestamp:.6f}_{msg.id}.json"
        final_path = inbox / filename
        tmp_path = inbox / f"{filename}.tmp"
        lock_path = inbox / ".write_lock"

        # 序列化消息
        payload = json.dumps(msg.to_dict(), indent=2)

        # 原子写入函数
        def _write_atomic() -> None:
            with exclusive_file_lock(lock_path):
                tmp_path.write_text(payload, encoding="utf-8")
                os.replace(tmp_path, final_path)

        # 将阻塞 I/O 卸载到线程池
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write_atomic)

    async def read_all(self, unread_only: bool = True) -> list[MailboxMessage]:
        """从 inbox 返回消息，按时间戳排序（最旧优先）。

        Args:
            unread_only: 当为 *True*（默认）时仅返回未读消息。
                         传递 *False* 以检索所有消息，包括已读的。
        """
        inbox = self.get_mailbox_dir()

        def _read_all() -> list[MailboxMessage]:
            messages: list[MailboxMessage] = []
            for path in sorted(inbox.glob("*.json")):
                # 跳过锁文件和临时文件
                if path.name.startswith(".") or path.name.endswith(".tmp"):
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    msg = MailboxMessage.from_dict(data)
                    if not unread_only or not msg.read:
                        messages.append(msg)
                except (json.JSONDecodeError, KeyError):
                    # 跳过损坏的消息文件而不是崩溃。
                    continue
            return messages

        # 将阻塞 I/O 卸载到线程池
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _read_all)

    async def mark_read(self, message_id: str) -> None:
        """将 *message_id* 的消息标记为已读（就地更新）。"""
        inbox = self.get_mailbox_dir()
        lock_path = self._lock_path()

        def _mark_read() -> bool:
            with exclusive_file_lock(lock_path):
                for path in inbox.glob("*.json"):
                    # 跳过锁文件和临时文件
                    if path.name.startswith(".") or path.name.endswith(".tmp"):
                        continue
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        continue

                    if data.get("id") == message_id:
                        data["read"] = True
                        tmp_path = path.with_suffix(".json.tmp")
                        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        os.replace(tmp_path, path)
                        return True
                return False

        # 将阻塞 I/O 卸载到线程池
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _mark_read)

    async def clear(self) -> None:
        """从 inbox 中删除所有消息文件。"""
        inbox = self.get_mailbox_dir()
        lock_path = self._lock_path()

        def _clear() -> None:
            with exclusive_file_lock(lock_path):
                for path in inbox.glob("*.json"):
                    # 跳过锁文件
                    if path.name.startswith("."):
                        continue
                    try:
                        path.unlink()
                    except OSError:
                        pass

        # 将阻塞 I/O 卸载到线程池
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _clear)


# ---------------------------------------------------------------------------
# 工厂辅助函数（基础）
# ---------------------------------------------------------------------------


def _make_message(
    msg_type: MessageType,
    sender: str,
    recipient: str,
    payload: dict[str, Any],
) -> MailboxMessage:
    """创建邮箱消息的内部函数。"""
    return MailboxMessage(
        id=str(uuid.uuid4()),
        type=msg_type,
        sender=sender,
        recipient=recipient,
        payload=payload,
        timestamp=time.time(),
    )


def create_user_message(sender: str, recipient: str, content: str) -> MailboxMessage:
    """创建纯文本用户消息。"""
    return _make_message("user_message", sender, recipient, {"content": content})


def create_shutdown_request(sender: str, recipient: str) -> MailboxMessage:
    """创建关闭请求消息。"""
    return _make_message("shutdown", sender, recipient, {})


def create_idle_notification(
    sender: str, recipient: str, summary: str
) -> MailboxMessage:
    """创建带有简要摘要的空闲通知消息。"""
    return _make_message(
        "idle_notification", sender, recipient, {"summary": summary}
    )


# ---------------------------------------------------------------------------
# 权限消息工厂函数（匹配 TS teammateMailbox.ts）
# ---------------------------------------------------------------------------


def create_permission_request_message(
    sender: str,
    recipient: str,
    request_data: dict[str, Any],
) -> MailboxMessage:
    """从工作者到负责人创建 permission_request 消息。

    Args:
        sender: 发送工作者的代理名称。
        recipient: 接收负责人的代理名称。
        request_data: 包含以下键的字典：request_id, agent_id, tool_name,
            tool_use_id, description, input, permission_suggestions。

    Returns:
        类型为 ``permission_request`` 的 :class:`MailboxMessage`。
    """
    payload: dict[str, Any] = {
        "type": "permission_request",
        "request_id": request_data.get("request_id", ""),
        "agent_id": request_data.get("agent_id", sender),
        "tool_name": request_data.get("tool_name", ""),
        "tool_use_id": request_data.get("tool_use_id", ""),
        "description": request_data.get("description", ""),
        "input": request_data.get("input", {}),
        "permission_suggestions": request_data.get("permission_suggestions", []),
    }
    return _make_message("permission_request", sender, recipient, payload)


def create_permission_response_message(
    sender: str,
    recipient: str,
    response_data: dict[str, Any],
) -> MailboxMessage:
    """从负责人到工作者创建 permission_response 消息。

    Args:
        sender: 发送负责人的代理名称。
        recipient: 目标工作者的代理名称。
        response_data: 包含以下键的字典：request_id, subtype ('success'|'error'),
            error (可选), updated_input (可选), permission_updates (可选)。

    Returns:
        类型为 ``permission_response`` 的 :class:`MailboxMessage`。
    """
    subtype = response_data.get("subtype", "success")
    if subtype == "error":
        payload: dict[str, Any] = {
            "type": "permission_response",
            "request_id": response_data.get("request_id", ""),
            "subtype": "error",
            "error": response_data.get("error", "Permission denied"),
        }
    else:
        payload = {
            "type": "permission_response",
            "request_id": response_data.get("request_id", ""),
            "subtype": "success",
            "response": {
                "updated_input": response_data.get("updated_input"),
                "permission_updates": response_data.get("permission_updates"),
            },
        }
    return _make_message("permission_response", sender, recipient, payload)


def create_sandbox_permission_request_message(
    sender: str,
    recipient: str,
    request_data: dict[str, Any],
) -> MailboxMessage:
    """从工作者到负责人创建 sandbox_permission_request 消息。

    Args:
        sender: 发送工作者的代理名称。
        recipient: 接收负责人的代理名称。
        request_data: 包含以下键的字典：requestId, workerId, workerName,
            workerColor (可选), host。

    Returns:
        类型为 ``sandbox_permission_request`` 的 :class:`MailboxMessage`。
    """
    payload: dict[str, Any] = {
        "type": "sandbox_permission_request",
        "requestId": request_data.get("requestId", ""),
        "workerId": request_data.get("workerId", sender),
        "workerName": request_data.get("workerName", sender),
        "workerColor": request_data.get("workerColor"),
        "hostPattern": {"host": request_data.get("host", "")},
        "createdAt": int(time.time() * 1000),
    }
    return _make_message("sandbox_permission_request", sender, recipient, payload)


def create_sandbox_permission_response_message(
    sender: str,
    recipient: str,
    response_data: dict[str, Any],
) -> MailboxMessage:
    """从负责人到工作者创建 sandbox_permission_response 消息。

    Args:
        sender: 发送负责人的代理名称。
        recipient: 目标工作者的代理名称。
        response_data: 包含以下键的字典：requestId, host, allow。

    Returns:
        类型为 ``sandbox_permission_response`` 的 :class:`MailboxMessage`。
    """
    from datetime import datetime, timezone

    payload: dict[str, Any] = {
        "type": "sandbox_permission_response",
        "requestId": response_data.get("requestId", ""),
        "host": response_data.get("host", ""),
        "allow": bool(response_data.get("allow", False)),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    return _make_message("sandbox_permission_response", sender, recipient, payload)


# ---------------------------------------------------------------------------
# 类型守卫辅助函数（匹配 TS isPermissionRequest 等）
# ---------------------------------------------------------------------------


def is_permission_request(msg: MailboxMessage) -> dict[str, Any] | None:
    """如果 *msg* 是 permission_request 则返回权限请求载荷，否则返回 None。"""
    if msg.type == "permission_request":
        return msg.payload
    # 还检查文本字段以兼容文本信封消息
    text = msg.payload.get("text", "")
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("type") == "permission_request":
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def is_permission_response(msg: MailboxMessage) -> dict[str, Any] | None:
    """如果 *msg* 是 permission_response 则返回权限响应载荷，否则返回 None。"""
    if msg.type == "permission_response":
        return msg.payload
    text = msg.payload.get("text", "")
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("type") == "permission_response":
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def is_sandbox_permission_request(msg: MailboxMessage) -> dict[str, Any] | None:
    """如果 *msg* 是 sandbox_permission_request 则返回载荷，否则返回 None。"""
    if msg.type == "sandbox_permission_request":
        return msg.payload
    text = msg.payload.get("text", "")
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("type") == "sandbox_permission_request":
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def is_sandbox_permission_response(msg: MailboxMessage) -> dict[str, Any] | None:
    """如果 *msg* 是 sandbox_permission_response 则返回载荷，否则返回 None。"""
    if msg.type == "sandbox_permission_response":
        return msg.payload
    text = msg.payload.get("text", "")
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("type") == "sandbox_permission_response":
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


# ---------------------------------------------------------------------------
# 全局邮箱便捷函数（匹配 TS writeToMailbox 等）
# ---------------------------------------------------------------------------


async def write_to_mailbox(
    recipient_name: str,
    message: dict[str, Any],
    team_name: str | None = None,
) -> None:
    """将 TeammateMessage 格式的字典写入接收者的邮箱。

    这镜像了 TS ``writeToMailbox(recipientName, message, teamName)`` 函数。
    *message* 字典至少应具有 ``from`` 键和 ``text`` 键（序列化的消息内容），
    以及可选的 ``timestamp``、``color`` 和 ``summary``。

    Args:
        recipient_name: 接收者代理的名称/ID。
        message: 包含 ``from``、``text`` 和可选字段的字典。
        team_name: 可选的团队名称；默认为 ``CLAUDE_CODE_TEAM_NAME``
            环境变量，然后是 ``"default"``。
    """
    team = team_name or os.environ.get("CLAUDE_CODE_TEAM_NAME", "default")
    text = message.get("text", "")

    # 从序列化的文本内容检测消息类型，以便路由工作
    msg_type: MessageType = "user_message"
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "type" in parsed:
            t = parsed["type"]
            if t in (
                "permission_request",
                "permission_response",
                "sandbox_permission_request",
                "sandbox_permission_response",
                "shutdown",
                "idle_notification",
            ):
                msg_type = t  # type: ignore[assignment]
    except (json.JSONDecodeError, TypeError):
        pass

    msg = MailboxMessage(
        id=str(uuid.uuid4()),
        type=msg_type,
        sender=message.get("from", "unknown"),
        recipient=recipient_name,
        payload={
            "text": text,
            "color": message.get("color"),
            "summary": message.get("summary"),
            "timestamp": message.get("timestamp"),
        },
        timestamp=time.time(),
    )
    mailbox = TeammateMailbox(team, recipient_name)
    await mailbox.write(msg)
