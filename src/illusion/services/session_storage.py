"""
会话持久化辅助模块
================

本模块提供会话状态持久化功能，支持保存和加载会话快照。

主要功能：
    - 获取项目会话目录
    - 保存会话快照
    - 加载会话快照
    - 列出会话快照
    - 导出会话记录为 Markdown

类说明：
    - get_project_session_dir: 获取项目会话目录
    - save_session_snapshot: 保存会话快照
    - load_session_snapshot: 加载会话快照
    - list_session_snapshots: 列出会话快照
    - export_session_markdown: 导出为 Markdown

使用示例：
    >>> from illusion.services.session_storage import get_project_session_dir, save_session_snapshot
    >>> # 获取项目会话目录
    >>> session_dir = get_project_session_dir("/path/to/project")
    >>> # 保存会话快照
    >>> save_session_snapshot(cwd="/path/to/project", model="claude-3", messages=[...], usage=...)
"""

from __future__ import annotations

import json
import time
from hashlib import sha1
from pathlib import Path
from typing import Any
from uuid import uuid4

from illusion.api.usage import UsageSnapshot
from illusion.config.paths import get_sessions_dir
from illusion.engine.messages import ConversationMessage


def get_project_session_dir(cwd: str | Path) -> Path:
    """返回项目的会话目录。"""
    path = Path(cwd).resolve()
    # 使用路径的 SHA1 哈希前 12 位作为目录名的一部分
    digest = sha1(str(path).encode("utf-8")).hexdigest()[:12]
    session_dir = get_sessions_dir() / f"{path.name}-{digest}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def save_session_snapshot(
    *,
    cwd: str | Path,
    model: str,
    system_prompt: str,
    messages: list[ConversationMessage],
    usage: UsageSnapshot,
    session_id: str | None = None,
) -> Path:
    """持久化会话快照。同时按 ID 保存和保存为 latest。"""
    session_dir = get_project_session_dir(cwd)
    sid = session_id or uuid4().hex[:12]
    now = time.time()
    # 从第一个用户消息提取摘要
    summary = ""
    for msg in messages:
        if msg.role == "user" and msg.text.strip():
            summary = msg.text.strip()[:80]
            break

    payload = {
        "session_id": sid,
        "cwd": str(Path(cwd).resolve()),
        "model": model,
        "system_prompt": system_prompt,
        "messages": [message.model_dump(mode="json") for message in messages],
        "usage": usage.model_dump(),
        "created_at": now,
        "summary": summary,
        "message_count": len(messages),
    }
    data = json.dumps(payload, indent=2) + "\n"

    # 保存为 latest
    latest_path = session_dir / "latest.json"
    latest_path.write_text(data, encoding="utf-8")

    # 按会话 ID 保存
    session_path = session_dir / f"session-{sid}.json"
    session_path.write_text(data, encoding="utf-8")

    return latest_path


def load_session_snapshot(cwd: str | Path) -> dict[str, Any] | None:
    """加载项目的最新会话快照。"""
    path = get_project_session_dir(cwd) / "latest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_session_snapshots(cwd: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    """列出项目的已保存会话，按最新优先排序。"""
    session_dir = get_project_session_dir(cwd)
    sessions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # 命名会话文件
    for path in sorted(session_dir.glob("session-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sid = data.get("session_id", path.stem.replace("session-", ""))
            seen_ids.add(sid)
            summary = data.get("summary", "")
            if not summary:
                # 从消息中提取
                for msg in data.get("messages", []):
                    if msg.get("role") == "user":
                        texts = [b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text"]
                        summary = " ".join(texts).strip()[:80]
                        if summary:
                            break
            sessions.append({
                "session_id": sid,
                "summary": summary,
                "message_count": data.get("message_count", len(data.get("messages", []))),
                "model": data.get("model", ""),
                "created_at": data.get("created_at", path.stat().st_mtime),
            })
        except (json.JSONDecodeError, OSError):
            continue
        if len(sessions) >= limit:
            break

    # 也包含 latest.json（如果没有对应的会话文件）
    latest_path = session_dir / "latest.json"
    if latest_path.exists() and len(sessions) < limit:
        try:
            data = json.loads(latest_path.read_text(encoding="utf-8"))
            sid = data.get("session_id", "latest")
            if sid not in seen_ids:
                summary = data.get("summary", "")
                if not summary:
                    for msg in data.get("messages", []):
                        if msg.get("role") == "user":
                            texts = [b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text"]
                            summary = " ".join(texts).strip()[:80]
                            if summary:
                                break
                sessions.append({
                    "session_id": sid,
                    "summary": summary or "(latest session)",
                    "message_count": data.get("message_count", len(data.get("messages", []))),
                    "model": data.get("model", ""),
                    "created_at": data.get("created_at", latest_path.stat().st_mtime),
                })
        except (json.JSONDecodeError, OSError):
            pass

    # 按 created_at 降序排序
    sessions.sort(key=lambda s: s.get("created_at", 0), reverse=True)
    return sessions[:limit]


def load_session_by_id(cwd: str | Path, session_id: str) -> dict[str, Any] | None:
    """按 ID 加载特定会话。"""
    session_dir = get_project_session_dir(cwd)
    # 先尝试命名会话
    path = session_dir / f"session-{session_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # 回退到 latest.json（如果 session_id 匹配）
    latest = session_dir / "latest.json"
    if latest.exists():
        data = json.loads(latest.read_text(encoding="utf-8"))
        if data.get("session_id") == session_id or session_id == "latest":
            return data
    return None


def export_session_markdown(
    *,
    cwd: str | Path,
    messages: list[ConversationMessage],
) -> Path:
    """将会话记录导出为 Markdown。"""
    session_dir = get_project_session_dir(cwd)
    path = session_dir / "transcript.md"
    parts: list[str] = ["# IllusionCode Session Transcript"]
    for message in messages:
        parts.append(f"\n## {message.role.capitalize()}\n")
        text = message.text.strip()
        if text:
            parts.append(text)
        for block in message.tool_uses:
            parts.append(f"\n```tool\n{block.name} {json.dumps(block.input, ensure_ascii=True)}\n```")
        for block in message.content:
            if getattr(block, "type", "") == "tool_result":
                parts.append(f"\n```tool-result\n{block.content}\n```")
    path.write_text("\n".join(parts).strip() + "\n", encoding="utf-8")
    return path