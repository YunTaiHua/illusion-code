"""
任务数据模型模块
================

本模块定义任务相关的数据类型。

类型说明：
    - TaskType: 任务类型
    - TaskStatus: 任务状态
    - TaskUpdateStatus: 任务更新状态（含 deleted）

类说明：
    - TaskRecord: 后台任务的运行时表示
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


# 任务类型
TaskType = Literal["local_bash", "local_agent", "remote_agent", "in_process_teammate"]
# 任务状态
TaskStatus = Literal["pending", "running", "completed", "failed", "killed"]

# 扩展状态，包含任务更新操作的 deleted
TaskUpdateStatus = Literal["pending", "in_progress", "completed", "deleted"]


@dataclass
class TaskRecord:
    """后台任务的运行时表示。"""

    id: str
    type: TaskType
    status: TaskStatus
    description: str
    cwd: str
    output_file: Path
    command: str | None = None
    prompt: str | None = None
    subject: str | None = None
    active_form: str | None = None
    owner: str | None = None
    blocked_by: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    created_at: float = 0.0
    started_at: float | None = None
    ended_at: float | None = None
    return_code: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)