"""
后台任务管理器模块
=================

本模块管理后台 shell 和 agent 子进程任务。

主要功能：
    - 创建待处理任务
    - 创建 Shell 任务
    - 创建 Agent 任务
    - 更新任务
    - 停止任务
    - 读写任务输出

类说明：
    - BackgroundTaskManager: 后台任务管理器类
    - create_pending_task: 创建待处理任务
    - create_shell_task: 创建 Shell 任务
    - create_agent_task: 创建 Agent 任务
    - update_task: 更新任务
    - stop_task: 停止任务

使用示例：
    >>> from illusion.tasks.manager import BackgroundTaskManager, get_task_manager
    >>> # 获取任务管理器
    >>> manager = get_task_manager()
    >>> # 创建 Shell 任务
    >>> record = await manager.create_shell_task(command="ls -la", description="列出文件", cwd=".")
"""

from __future__ import annotations

import asyncio
import os
import shlex
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from illusion.config.paths import get_tasks_dir
from illusion.tasks.types import TaskRecord, TaskStatus, TaskType
from illusion.utils.shell import create_shell_subprocess


class BackgroundTaskManager:
    """管理 shell 和 agent 子进程任务。"""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._waiters: dict[str, asyncio.Task[None]] = {}
        self._output_locks: dict[str, asyncio.Lock] = {}
        self._input_locks: dict[str, asyncio.Lock] = {}
        self._generations: dict[str, int] = {}

    def create_pending_task(
        self,
        *,
        subject: str,
        description: str,
        active_form: str | None = None,
    ) -> TaskRecord:
        """创建用于跟踪的待处理任务（非后台进程）。"""
        task_id = _task_id("in_process_teammate")
        output_path = get_tasks_dir() / f"{task_id}.log"
        record = TaskRecord(
            id=task_id,
            type="in_process_teammate",
            status="pending",
            description=description,
            subject=subject,
            active_form=active_form,
            cwd=str(Path.cwd().resolve()),
            output_file=output_path,
            created_at=time.time(),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        self._tasks[task_id] = record
        return record

    async def create_shell_task(
        self,
        *,
        command: str,
        description: str,
        cwd: str | Path,
        task_type: TaskType = "local_bash",
    ) -> TaskRecord:
        """启动后台 shell 命令。"""
        task_id = _task_id(task_type)
        output_path = get_tasks_dir() / f"{task_id}.log"
        record = TaskRecord(
            id=task_id,
            type=task_type,
            status="running",
            description=description,
            cwd=str(Path(cwd).resolve()),
            output_file=output_path,
            command=command,
            created_at=time.time(),
            started_at=time.time(),
        )
        output_path.write_text("", encoding="utf-8")
        self._tasks[task_id] = record
        self._output_locks[task_id] = asyncio.Lock()
        self._input_locks[task_id] = asyncio.Lock()
        await self._start_process(task_id)
        return record

    async def create_agent_task(
        self,
        *,
        prompt: str,
        description: str,
        cwd: str | Path,
        task_type: TaskType = "local_agent",
        model: str | None = None,
        api_key: str | None = None,
        command: str | None = None,
    ) -> TaskRecord:
        """作为子进程启动本地 agent 任务。"""
        if command is None:
            effective_api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not effective_api_key:
                raise ValueError(
                    "Local agent tasks require ANTHROPIC_API_KEY or an explicit command override"
                )
            cmd = ["python", "-m", "illusion", "--headless", "--api-key", effective_api_key]
            if model:
                cmd.extend(["--model", model])
            command = " ".join(shlex.quote(part) for part in cmd)

        record = await self.create_shell_task(
            command=command,
            description=description,
            cwd=cwd,
            task_type=task_type,
        )
        updated = replace(record, prompt=prompt)
        if task_type != "local_agent":
            updated.metadata["agent_mode"] = task_type
        self._tasks[record.id] = updated
        await self.write_to_task(record.id, prompt)
        return updated

    def get_task(self, task_id: str) -> TaskRecord | None:
        """返回一个任务记录。"""
        return self._tasks.get(task_id)

    def list_tasks(self, *, status: TaskStatus | None = None) -> list[TaskRecord]:
        """返回所有任务，可选按状态过滤。"""
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return sorted(tasks, key=lambda item: item.created_at, reverse=True)

    def update_task(
        self,
        task_id: str,
        *,
        subject: str | None = None,
        description: str | None = None,
        active_form: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        progress: int | None = None,
        status_note: str | None = None,
        metadata: dict | None = None,
        add_blocks: list[str] | None = None,
        add_blocked_by: list[str] | None = None,
    ) -> TaskRecord:
        """更新用于协调和 UI 显示的可变任务元数据。"""
        task = self._require_task(task_id)

        # 处理删除
        if status == "deleted":
            self._tasks.pop(task_id, None)
            return task

        if subject is not None:
            task.subject = subject
        if description is not None and description.strip():
            task.description = description.strip()
        if active_form is not None:
            task.active_form = active_form
        if status is not None:
            # 映射任务列表状态到任务管理器状态
            status_map = {
                "pending": "pending",
                "in_progress": "running",
                "completed": "completed",
            }
            task.status = status_map.get(status, status)
        if owner is not None:
            task.owner = owner
        if progress is not None:
            task.metadata["progress"] = str(progress)
        if status_note is not None:
            note = status_note.strip()
            if note:
                task.metadata["status_note"] = note
            else:
                task.metadata.pop("status_note", None)
        if metadata is not None:
            for key, value in metadata.items():
                if value is None:
                    task.metadata.pop(key, None)
                else:
                    task.metadata[key] = str(value)
        if add_blocks is not None:
            for block_id in add_blocks:
                if block_id not in task.blocks:
                    task.blocks.append(block_id)
        if add_blocked_by is not None:
            for blocker_id in add_blocked_by:
                if blocker_id not in task.blocked_by:
                    task.blocked_by.append(blocker_id)
        return task

    async def stop_task(self, task_id: str) -> TaskRecord:
        """终止运行中的任务。"""
        task = self._require_task(task_id)
        process = self._processes.get(task_id)
        if process is None:
            if task.status in {"completed", "failed", "killed"}:
                return task
            raise ValueError(f"Task {task_id} is not running")

        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=3)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

        task.status = "killed"
        task.ended_at = time.time()
        return task

    async def write_to_task(self, task_id: str, data: str) -> None:
        """向任务 stdin 写入一行，需要时自动恢复本地 agent。"""
        task = self._require_task(task_id)
        async with self._input_locks[task_id]:
            process = await self._ensure_writable_process(task)
            process.stdin.write((data.rstrip("\n") + "\n").encode("utf-8"))
            try:
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                if task.type not in {"local_agent", "remote_agent", "in_process_teammate"}:
                    raise ValueError(f"Task {task_id} does not accept input") from None
                process = await self._restart_agent_task(task)
                process.stdin.write((data.rstrip("\n") + "\n").encode("utf-8"))
                await process.stdin.drain()

    def read_task_output(self, task_id: str, *, max_bytes: int = 12000) -> str:
        """返回任务输出文件的尾部。"""
        task = self._require_task(task_id)
        content = task.output_file.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_bytes:
            return content[-max_bytes:]
        return content

    async def _watch_process(
        self,
        task_id: str,
        process: asyncio.subprocess.Process,
        generation: int,
    ) -> None:
        """监视子进程直到完成。"""
        reader = asyncio.create_task(self._copy_output(task_id, process))
        return_code = await process.wait()
        await reader

        current_generation = self._generations.get(task_id)
        if current_generation != generation:
            return

        task = self._tasks[task_id]
        task.return_code = return_code
        if task.status != "killed":
            task.status = "completed" if return_code == 0 else "failed"
        task.ended_at = time.time()
        self._processes.pop(task_id, None)
        self._waiters.pop(task_id, None)

    async def _copy_output(self, task_id: str, process: asyncio.subprocess.Process) -> None:
        """将进程输出复制到任务输出文件。"""
        if process.stdout is None:
            return
        while True:
            chunk = await process.stdout.read(4096)
            if not chunk:
                return
            async with self._output_locks[task_id]:
                with self._tasks[task_id].output_file.open("ab") as handle:
                    handle.write(chunk)

    def _require_task(self, task_id: str) -> TaskRecord:
        """返回任务记录，不存在则抛出异常。"""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"No task found with ID: {task_id}")
        return task

    async def _start_process(self, task_id: str) -> asyncio.subprocess.Process:
        """启动任务进程。"""
        task = self._require_task(task_id)
        if task.command is None:
            raise ValueError(f"Task {task_id} does not have a command to run")

        generation = self._generations.get(task_id, 0) + 1
        self._generations[task_id] = generation
        process = await create_shell_subprocess(
            task.command,
            cwd=task.cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._processes[task_id] = process
        self._waiters[task_id] = asyncio.create_task(
            self._watch_process(task_id, process, generation)
        )
        return process

    async def _ensure_writable_process(
        self,
        task: TaskRecord,
    ) -> asyncio.subprocess.Process:
        """确保任务可写入，必要时重启。"""
        process = self._processes.get(task.id)
        if process is not None and process.stdin is not None and process.returncode is None:
            return process
        if task.type not in {"local_agent", "remote_agent", "in_process_teammate"}:
            raise ValueError(f"Task {task.id} does not accept input")
        return await self._restart_agent_task(task)

    async def _restart_agent_task(self, task: TaskRecord) -> asyncio.subprocess.Process:
        """重启 agent 任务。"""
        if task.command is None:
            raise ValueError(f"Task {task.id} does not have a restart command")

        waiter = self._waiters.get(task.id)
        if waiter is not None and not waiter.done():
            await waiter

        restart_count = int(task.metadata.get("restart_count", "0")) + 1
        task.metadata["restart_count"] = str(restart_count)
        task.status = "running"
        task.started_at = time.time()
        task.ended_at = None
        task.return_code = None
        return await self._start_process(task.id)


# 默认任务管理器单例
_DEFAULT_MANAGER: BackgroundTaskManager | None = None
_DEFAULT_MANAGER_KEY: str | None = None


def get_task_manager() -> BackgroundTaskManager:
    """返回单例任务管理器。"""
    global _DEFAULT_MANAGER, _DEFAULT_MANAGER_KEY
    current_key = str(get_tasks_dir().resolve())
    if _DEFAULT_MANAGER is None or _DEFAULT_MANAGER_KEY != current_key:
        _DEFAULT_MANAGER = BackgroundTaskManager()
        _DEFAULT_MANAGER_KEY = current_key
    return _DEFAULT_MANAGER


def _task_id(task_type: TaskType) -> str:
    """生成任务 ID 前缀。"""
    prefixes = {
        "local_bash": "b",
        "local_agent": "a",
        "remote_agent": "r",
        "in_process_teammate": "t",
    }
    return f"{prefixes[task_type]}{uuid4().hex[:8]}"