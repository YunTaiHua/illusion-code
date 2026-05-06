"""
React Launcher React 启动器模块
=========================

本模块实现默认的 React 终端前端启动器。

主要功能：
    - 解析前端目录路径
    - 构建后端启动命令
    - 启动 React 终端 UI

函数说明：
    - get_frontend_dir: 获取前端目录路径
    - build_backend_command: 构建后端启动命令
    - launch_react_tui: 启动 React 终端 UI

使用示例：
    >>> from illusion.ui.react_launcher import launch_react_tui, get_frontend_dir
    >>> 
    >>> # 启动 React TUI
    >>> exit_code = await launch_react_tui(prompt="帮我写一个程序")
    >>> 
    >>> # 获取前端目录
    >>> frontend_dir = get_frontend_dir()
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_npm() -> str:
    """解析 npm 可执行文件路径（在 Windows 上为 npm.cmd）。

    Returns:
        str: npm 可执行文件路径
    """
    return shutil.which("npm") or "npm"


def get_frontend_dir() -> Path:
    """返回 React 终端前端目录。

    按以下顺序检查：
    1. 已安装包内的打包文件（pip install）
    2. 开发仓库布局（source checkout）

    Returns:
        Path: 前端目录路径
    """
    # 1. 已安装包内的打包文件：illusion/_frontend/
    pkg_frontend = Path(__file__).resolve().parent.parent / "_frontend"
    if (pkg_frontend / "package.json").exists():
        return pkg_frontend

    # 2. 开发仓库：<repo>/frontend/terminal/
    repo_root = Path(__file__).resolve().parents[3]
    dev_frontend = repo_root / "frontend" / "terminal"
    if (dev_frontend / "package.json").exists():
        return dev_frontend

    # 回退到包路径（将显示清晰的错误消息）
    return pkg_frontend


def build_backend_command(
    *,
    cwd: str | None = None,
    model: str | None = None,
    max_turns: int | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
    api_key: str | None = None,
    api_format: str | None = None,
) -> list[str]:
    """返回 React 前端用于生成后端主机的命令。

    Args:
        cwd: 工作目录
        model: 模型名称
        max_turns: 最大对话轮次
        base_url: API 基础 URL
        system_prompt: 系统提示词
        api_key: API 密钥
        api_format: API 格式

    Returns:
        list[str]: 后端启动命令列表
    """
    command = [sys.executable, "-m", "illusion", "--backend-only"]
    if cwd:
        command.extend(["--cwd", cwd])
    if model:
        command.extend(["--mode", model])
    if max_turns is not None:
        command.extend(["--max-turns", str(max_turns)])
    if base_url:
        command.extend(["--base-url", base_url])
    if system_prompt:
        command.extend(["--system-prompt", system_prompt])
    if api_key:
        command.extend(["--api-key", api_key])
    if api_format:
        command.extend(["--api-format", api_format])
    return command


async def launch_react_tui(
    *,
    prompt: str | None = None,
    cwd: str | None = None,
    model: str | None = None,
    max_turns: int | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
    api_key: str | None = None,
    api_format: str | None = None,
) -> int:
    """启动 React 终端前端作为默认 UI。

    Args:
        prompt: 初始提示词
        cwd: 工作目录
        model: 模型名称
        max_turns: 最大对话轮次
        base_url: API 基础 URL
        system_prompt: 系统提示词
        api_key: API 密钥
        api_format: API 格式

    Returns:
        int: 退出代码
    """
    frontend_dir = get_frontend_dir()
    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        raise RuntimeError(f"React terminal frontend is missing: {package_json}")

    # 解析 npm 路径
    npm = _resolve_npm()

    # 检查并安装依赖
    if not (frontend_dir / "node_modules").exists():
        install_kwargs: dict = {}
        if sys.platform == "win32":
            install_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        install = await asyncio.create_subprocess_exec(
            npm,
            "install",
            "--no-fund",
            "--no-audit",
            cwd=str(frontend_dir),
            **install_kwargs,
        )
        if await install.wait() != 0:
            raise RuntimeError("Failed to install React terminal frontend dependencies")

    # 设置环境变量
    env = os.environ.copy()
    env["ILLUSION_FRONTEND_CONFIG"] = json.dumps(
        {
            "backend_command": build_backend_command(
                cwd=cwd or str(Path.cwd()),
                model=model,
                max_turns=max_turns,
                base_url=base_url,
                system_prompt=system_prompt,
                api_key=api_key,
                api_format=api_format,
            ),
            "initial_prompt": prompt,
        }
    )
    # 启动前端进程
    process = await asyncio.create_subprocess_exec(
        npm,
        "exec",
        "--",
        "tsx",
        "src/index.tsx",
        cwd=str(frontend_dir),
        env=env,
        stdin=None,
        stdout=None,
        stderr=None,
    )
    return await process.wait()


__all__ = ["build_backend_command", "get_frontend_dir", "launch_react_tui"]