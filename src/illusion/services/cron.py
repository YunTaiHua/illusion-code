"""
本地 Cron 风格注册表辅助模块
==========================

本模块提供 Cron 任务注册表的加载、保存和管理功能。

主要功能：
    - 加载 Cron 任务列表
    - 保存 Cron 任务列表
    - 验证 cron 表达式
    - 计算下次运行时间
    - 插入或更新任务
    - 删除任务
    - 获取任务
    - 启用/禁用任务
    - 标记任务执行结果

类说明：
    - load_cron_jobs: 加载任务列表
    - save_cron_jobs: 保存任务列表
    - validate_cron_expression: 验证表达式
    - next_run_time: 计算下次运行时间
    - upsert_cron_job: 插入或更新任务
    - delete_cron_job: 删除任务
    - get_cron_job: 获取任务
    - set_job_enabled: 启用/禁用任务
    - mark_job_run: 标记执行结果

使用示例：
    >>> from illusion.services.cron import load_cron_jobs, save_cron_jobs
    >>> # 加载任务
    >>> jobs = load_cron_jobs()
    >>> # 验证表达式
    >>> is_valid = validate_cron_expression("*/5 * * * *")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from croniter import croniter

from illusion.config.paths import get_cron_registry_path


def load_cron_jobs() -> list[dict[str, Any]]:
    """加载已保存的 Cron 任务列表。"""
    path = get_cron_registry_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def save_cron_jobs(jobs: list[dict[str, Any]]) -> None:
    """将 Cron 任务列表持久化到磁盘。"""
    path = get_cron_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jobs, indent=2) + "\n", encoding="utf-8")


def validate_cron_expression(expression: str) -> bool:
    """如果表达式是有效的 cron 计划则返回 True。"""
    return croniter.is_valid(expression)


def next_run_time(expression: str, base: datetime | None = None) -> datetime:
    """返回 cron 表达式的下次运行时间。"""
    base = base or datetime.now(timezone.utc)
    return croniter(expression, base).get_next(datetime)


def upsert_cron_job(job: dict[str, Any]) -> None:
    """插入或替换一个 Cron 任务。

    自动将 enabled 设置为 True，并在计划是有效 cron 表达式时计算 next_run。
    """
    job.setdefault("enabled", True)
    job.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    schedule = job.get("schedule", "")
    if validate_cron_expression(schedule):
        job["next_run"] = next_run_time(schedule).isoformat()

    jobs = [existing for existing in load_cron_jobs() if existing.get("name") != job.get("name")]
    jobs.append(job)
    jobs.sort(key=lambda item: str(item.get("name", "")))
    save_cron_jobs(jobs)


def delete_cron_job(name: str) -> bool:
    """按名称删除一个 Cron 任务。"""
    jobs = load_cron_jobs()
    filtered = [job for job in jobs if job.get("name") != name]
    if len(filtered) == len(jobs):
        return False
    save_cron_jobs(filtered)
    return True


def get_cron_job(name: str) -> dict[str, Any] | None:
    """按名称返回一个 Cron 任务。"""
    for job in load_cron_jobs():
        if job.get("name") == name:
            return job
    return None


def set_job_enabled(name: str, enabled: bool) -> bool:
    """启用或禁用 Cron 任务。如果任务未找到则返回 False。"""
    jobs = load_cron_jobs()
    for job in jobs:
        if job.get("name") == name:
            job["enabled"] = enabled
            save_cron_jobs(jobs)
            return True
    return False


def mark_job_run(name: str, *, success: bool) -> None:
    """任务执行后更新 last_run 并重新计算 next_run。"""
    jobs = load_cron_jobs()
    now = datetime.now(timezone.utc)
    for job in jobs:
        if job.get("name") == name:
            job["last_run"] = now.isoformat()
            job["last_status"] = "success" if success else "failed"
            schedule = job.get("schedule", "")
            if validate_cron_expression(schedule):
                job["next_run"] = next_run_time(schedule, now).isoformat()
            save_cron_jobs(jobs)
            return