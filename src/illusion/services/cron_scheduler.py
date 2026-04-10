"""
后台 Cron 调度器守护进程
===================

本模块实现后台定时任务调度功能，支持独立进程运行（illusion cron start）或嵌入模式（run_scheduler_loop）。
每个调度周期会读取Cron任务注册表，检查到期任务，执行并记录结果到历史日志。

主要功能：
    - 定时执行 Cron 任务
    - 管理调度器进程（PID文件）
    - 任务执行历史记录
    - 守护进程启动/停止控制

类说明：
    - run_scheduler_loop: 调度器主循环
    - start_daemon: 守护进程启动入口
    - scheduler_status: 获取调度器状态

使用示例：
    >>> from illusion.services.cron_scheduler import start_daemon
    >>> # 启动守护进程
    >>> pid = start_daemon()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from illusion.config.paths import get_data_dir, get_logs_dir
from illusion.services.cron import (
    load_cron_jobs,
    mark_job_run,
    validate_cron_expression,
)
from illusion.sandbox import SandboxUnavailableError
from illusion.utils.shell import create_shell_subprocess

# 配置模块级日志记录器
logger = logging.getLogger(__name__)

# 调度周期间隔（秒）- 每30秒检查一次到期任务
TICK_INTERVAL_SECONDS = 30
"""调度器检查到期任务的频率（秒）。"""


# ---------------------------------------------------------------------------
# 历史记录辅助函数
# ---------------------------------------------------------------------------

def get_history_path() -> Path:
    """返回 Cron 执行历史记录文件路径。"""
    return get_data_dir() / "cron_history.jsonl"


def append_history(entry: dict[str, Any]) -> None:
    """向历史日志追加一条执行记录。"""
    path = get_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def load_history(*, limit: int = 50, job_name: str | None = None) -> list[dict[str, Any]]:
    """加载最近的执行历史记录。"""
    path = get_history_path()
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if job_name and entry.get("name") != job_name:
            continue
        entries.append(entry)
    return entries[-limit:]


# ---------------------------------------------------------------------------
# PID 文件辅助函数
# ---------------------------------------------------------------------------

def get_pid_path() -> Path:
    """返回调度器 PID 文件路径。"""
    return get_data_dir() / "cron_scheduler.pid"


def read_pid() -> int | None:
    """读取运行中的调度器 PID，如果不存在则返回 None。"""
    path = get_pid_path()
    if not path.exists():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    # 检查进程是否存活
    try:
        os.kill(pid, 0)
    except OSError:
        # 移除过期的 PID 文件
        logger.debug("Removed stale scheduler PID file (pid=%d)", pid)
        path.unlink(missing_ok=True)
        return None
    return pid


def write_pid() -> None:
    """写入当前进程 PID。"""
    path = get_pid_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(os.getpid()) + "\n", encoding="utf-8")


def remove_pid() -> None:
    """删除 PID 文件。"""
    get_pid_path().unlink(missing_ok=True)


def is_scheduler_running() -> bool:
    """返回是否存在运行的调度器进程。"""
    return read_pid() is not None


def stop_scheduler() -> bool:
    """向运行中的调度器发送 SIGTERM 信号。如果成功终止则返回 True。"""
    pid = read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        remove_pid()
        return False
    # 等待进程退出
    for _ in range(10):
        try:
            os.kill(pid, 0)
        except OSError:
            remove_pid()
            return True
        time.sleep(0.2)
    # 强制终止
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    remove_pid()
    return True


# ---------------------------------------------------------------------------
# 任务执行
# ---------------------------------------------------------------------------

async def execute_job(job: dict[str, Any]) -> dict[str, Any]:
    """执行单个 Cron 任务并返回历史记录条目。"""
    name = job["name"]
    command = job["command"]
    cwd = Path(job.get("cwd") or ".").expanduser()
    started_at = datetime.now(timezone.utc)

    logger.info("Executing cron job %r: %s", name, command)
    try:
        # 创建异步子进程执行命令
        process = await create_shell_subprocess(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=300,
        )
    except asyncio.TimeoutError:
        # 处理超时
        try:
            process.kill()
            await process.wait()
        except Exception:
            pass
        entry = {
            "name": name,
            "command": command,
            "started_at": started_at.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "returncode": -1,
            "status": "timeout",
            "stdout": "",
            "stderr": "Job timed out after 300s",
        }
        mark_job_run(name, success=False)
        append_history(entry)
        return entry
    except SandboxUnavailableError as exc:
        # 处理沙箱不可用错误
        entry = {
            "name": name,
            "command": command,
            "started_at": started_at.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "returncode": -1,
            "status": "error",
            "stdout": "",
            "stderr": str(exc),
        }
        mark_job_run(name, success=False)
        append_history(entry)
        return entry
    except Exception as exc:
        # 处理其他异常
        entry = {
            "name": name,
            "command": command,
            "started_at": started_at.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "returncode": -1,
            "status": "error",
            "stdout": "",
            "stderr": str(exc),
        }
        mark_job_run(name, success=False)
        append_history(entry)
        return entry

    # 任务成功完成
    success = process.returncode == 0
    entry = {
        "name": name,
        "command": command,
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "returncode": process.returncode,
        "status": "success" if success else "failed",
        "stdout": (stdout.decode("utf-8", errors="replace")[-2000:] if stdout else ""),
        "stderr": (stderr.decode("utf-8", errors="replace")[-2000:] if stderr else ""),
    }
    mark_job_run(name, success=success)
    append_history(entry)
    logger.info("Job %r finished: %s (rc=%s)", name, entry["status"], process.returncode)
    return entry


# ---------------------------------------------------------------------------
# 调度器主循环
# ---------------------------------------------------------------------------

def _jobs_due(jobs: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """返回 next_run 时间在当前时间或之前的任务列表。"""
    due: list[dict[str, Any]] = []
    for job in jobs:
        if not job.get("enabled", True):
            continue
        schedule = job.get("schedule", "")
        if not validate_cron_expression(schedule):
            continue
        next_run_str = job.get("next_run")
        if not next_run_str:
            continue
        try:
            next_run = datetime.fromisoformat(next_run_str)
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if next_run <= now:
            due.append(job)
    return due


async def run_scheduler_loop(*, once: bool = False) -> None:
    """主调度器循环。运行直到收到 SIGTERM 或 once 为 True（测试模式）。"""
    shutdown = asyncio.Event()

    def _on_signal() -> None:
        logger.info("Received shutdown signal")
        shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _on_signal)

    # 写入 PID 文件
    write_pid()
    logger.info("Cron scheduler started (pid=%d, tick=%ds)", os.getpid(), TICK_INTERVAL_SECONDS)

    try:
        while not shutdown.is_set():
            now = datetime.now(timezone.utc)
            jobs = load_cron_jobs()
            due = _jobs_due(jobs, now)

            if due:
                logger.info("Tick: %d job(s) due", len(due))
                # 并发执行到期任务
                results = await asyncio.gather(
                    *(execute_job(job) for job in due), return_exceptions=True
                )
                for result in results:
                    if isinstance(result, BaseException):
                        logger.error("Unexpected error executing cron job: %s", result)

            if once:
                break

            # 等待下一个调度周期
            try:
                await asyncio.wait_for(shutdown.wait(), timeout=TICK_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass
    finally:
        # 清理 PID 文件
        remove_pid()
        logger.info("Cron scheduler stopped")


# ---------------------------------------------------------------------------
# 守护进程入口点（由 illusion cron start 启动）
# ---------------------------------------------------------------------------

def _run_daemon() -> None:
    """调度器子进程入口点。"""
    log_file = get_logs_dir() / "cron_scheduler.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    asyncio.run(run_scheduler_loop())


def start_daemon() -> int:
    """Fork 并启动调度器守护进程。返回子进程 PID。"""
    existing = read_pid()
    if existing is not None:
        raise RuntimeError(f"Scheduler already running (pid={existing})")

    pid = os.fork()
    if pid > 0:
        # 父进程 - 等待子进程写入 PID 文件
        time.sleep(0.3)
        return pid

    # 子进程 - 脱离终端
    os.setsid()
    # 重定向标准输入输出到 /dev/null
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)

    _run_daemon()
    sys.exit(0)


def scheduler_status() -> dict[str, Any]:
    """返回调度器状态信息字典。"""
    pid = read_pid()
    log_path = get_logs_dir() / "cron_scheduler.log"
    jobs = load_cron_jobs()
    enabled = [j for j in jobs if j.get("enabled", True)]
    return {
        "running": pid is not None,
        "pid": pid,
        "total_jobs": len(jobs),
        "enabled_jobs": len(enabled),
        "log_file": str(log_path),
        "history_file": str(get_history_path()),
    }