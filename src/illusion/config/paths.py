"""
IllusionCode 配置和数据目录路径解析模块
=======================================

遵循 XDG 类似约定，默认使用 ~/.illusion/ 作为基础目录。

本模块提供各种目录路径的获取函数，支持环境变量覆盖，
确保配置、数据、日志等文件存储在正确的位置。

函数说明：
    - get_config_dir: 获取配置目录
    - get_config_file_path: 获取配置文件路径
    - get_data_dir: 获取数据目录
    - get_logs_dir: 获取日志目录
    - get_sessions_dir: 获取会话存储目录
    - get_tasks_dir: 获取后台任务输出目录
    - get_feedback_dir: 获取反馈存储目录
    - get_project_config_dir: 获取项目级配置目录
    - get_project_issue_file: 获取项目级问题上下文文件
    - get_project_pr_comments_file: 获取项目级 PR 评论上下文文件
    - get_cron_registry_path: 获取 cron 注册表文件路径
    - get_feedback_log_path: 获取反馈日志文件路径

使用示例：
    >>> from illusion.config.paths import get_config_dir, get_data_dir
    >>> config = get_config_dir()
    >>> data = get_data_dir()
"""

from __future__ import annotations

import os  # 导入 os 模块用于环境变量和路径操作
from pathlib import Path  # 导入 Path 类用于路径处理

# 常量定义
_DEFAULT_BASE_DIR = ".illusion"  # 默认基础目录名称
_CONFIG_FILE_NAME = "settings.json"  # 配置文件名称


def get_config_dir() -> Path:
    """返回配置目录，必要时创建
    
    解析顺序：
    1. ILLUSION_CONFIG_DIR 环境变量（优先）
    2. ~/.illusion/（默认）
    
    Returns:
        Path: 配置目录路径
    """
    # 检查环境变量 ILLUSION_CONFIG_DIR 是否设置
    env_dir = os.environ.get("ILLUSION_CONFIG_DIR")
    if env_dir:
        # 使用环境变量指定的目录
        config_dir = Path(env_dir)
    else:
        # 使用默认目录 ~/.illusion/
        config_dir = Path.home() / _DEFAULT_BASE_DIR

    # 确保目录存在，不存在则创建
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file_path() -> Path:
    """返回主设置文件路径（~/.illusion/settings.json）
    
    Returns:
        Path: 配置文件路径
    """
    return get_config_dir() / _CONFIG_FILE_NAME


def get_data_dir() -> Path:
    """返回数据目录（用于缓存、历史等）
    
    解析顺序：
    1. ILLUSION_DATA_DIR 环境变量（优先）
    2. ~/.illusion/data/（默认）
    
    Returns:
        Path: 数据目录路径
    """
    # 检查环境变量 ILLUSION_DATA_DIR 是否设置
    env_dir = os.environ.get("ILLUSION_DATA_DIR")
    if env_dir:
        data_dir = Path(env_dir)
    else:
        # 默认使用配置目录下的 data 子目录
        data_dir = get_config_dir() / "data"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_logs_dir() -> Path:
    """返回日志目录
    
    解析顺序：
    1. ILLUSION_LOGS_DIR 环境变量（优先）
    2. ~/.illusion/logs/（默认）
    
    Returns:
        Path: 日志目录路径
    """
    # 检查环境变量 ILLUSION_LOGS_DIR 是否设置
    env_dir = os.environ.get("ILLUSION_LOGS_DIR")
    if env_dir:
        logs_dir = Path(env_dir)
    else:
        # 默认使用配置目录下的 logs 子目录
        logs_dir = get_config_dir() / "logs"

    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_sessions_dir() -> Path:
    """返回会话存储目录
    
    用于存储对话会话相关的数据文件。
    
    Returns:
        Path: 会话目录路径
    """
    sessions_dir = get_data_dir() / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


def get_tasks_dir() -> Path:
    """返回后台任务输出目录
    
    用于存储后台任务执行结果和输出文件。
    
    Returns:
        Path: 任务目录路径
    """
    tasks_dir = get_data_dir() / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    return tasks_dir


def get_feedback_dir() -> Path:
    """返回反馈存储目录
    
    用于存储用户反馈相关的数据文件。
    
    Returns:
        Path: 反馈目录路径
    """
    feedback_dir = get_data_dir() / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    return feedback_dir


def get_feedback_log_path() -> Path:
    """返回反馈日志文件路径
    
    Returns:
        Path: 反馈日志文件路径
    """
    return get_feedback_dir() / "feedback.log"


def get_cron_registry_path() -> Path:
    """返回 cron 注册表文件路径
    
    用于存储定时任务配置信息。
    
    Returns:
        Path: cron 注册表文件路径
    """
    return get_data_dir() / "cron_jobs.json"


def get_project_config_dir(cwd: str | Path) -> Path:
    """返回项目级 .illusion 目录
    
    在当前工作目录下创建 .illusion 子目录，用于存储项目级配置。
    
    Args:
        cwd: 当前工作目录
    
    Returns:
        Path: 项目配置目录路径
    """
    # 解析为绝对路径并在末尾添加 .illusion 子目录
    project_dir = Path(cwd).resolve() / ".illusion"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def get_project_issue_file(cwd: str | Path) -> Path:
    """返回项目级问题上下文文件
    
    用于存储当前项目的问题上下文信息。
    
    Args:
        cwd: 当前工作目录
    
    Returns:
        Path: 问题文件路径
    """
    return get_project_config_dir(cwd) / "issue.md"


def get_project_pr_comments_file(cwd: str | Path) -> Path:
    """返回项目级 PR 评论上下文文件

    用于存储 Pull Request 的评论上下文信息。

    Args:
        cwd: 当前工作目录

    Returns:
        Path: PR 评论文件路径
    """
    return get_project_config_dir(cwd) / "pr_comments.md"


def get_project_mcp_dir(cwd: str | Path) -> Path:
    """返回项目级 MCP 配置目录（.illusion/mcp/）

    Args:
        cwd: 当前工作目录

    Returns:
        Path: 项目 MCP 配置目录路径
    """
    path = get_project_config_dir(cwd) / "mcp"
    path.mkdir(parents=True, exist_ok=True)
    return path
