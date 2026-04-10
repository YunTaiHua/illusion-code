"""
队友进程生成工具模块
====================

本模块提供用于生成队友进程的共享工具函数。

主要功能：
    - 获取队友命令的可执行文件路径
    - 构建继承的 CLI 标志
    - 构建继承的环境变量
    - tmux 可用性检测

使用示例：
    >>> from illusion.swarm.spawn_utils import get_teammate_command, build_inherited_cli_flags
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys


# 环境变量：覆盖队友命令
TEAMMATE_COMMAND_ENV_VAR = "ILLUSION_TEAMMATE_COMMAND"


# ---------------------------------------------------------------------------
# 转发到生成队友的环境变量。
#
# Tmux 可能启动一个全新的登录 shell，不会继承父进程的环境，
# 因此我们转发所有设置了的这些变量。
# ---------------------------------------------------------------------------

_TEAMMATE_ENV_VARS = [
    # --- API provider selection -------------------------------------------
    # 没有这些，队友会默认到错误的端点提供商，导致所有 API 调用失败
    #（类似于 TS 源代码中的 GitHub issue #23561）。
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    # --- Config directory override ----------------------------------------
    # 允许操作员级配置在队友进程中可见。
    "CLAUDE_CONFIG_DIR",
    # --- Remote / CCR markers ---------------------------------------------
    # CCR 感知代码路径检查 CLAUDE_CODE_REMOTE。认证会自行找到路径；
    # FD 环境变量无论如何不会跨 tmux 边界帮助。
    "CLAUDE_CODE_REMOTE",
    # Auto-memory gate 检查 REMOTE && !MEMORY_DIR 来在临时 CCR 文件系统上禁用 memory。
    # 单独转发 REMOTE 会使队友在父进程开启 memory 时切换到 memory-off。
    "CLAUDE_CODE_REMOTE_MEMORY_DIR",
    # --- Upstream proxy settings ------------------------------------------
    # 父进程的 MITM 代理在同一容器网络中可被队友访问。
    # 转发代理变量以便队友通过代理路由客户配置的流量以进行凭据注入。
    # 没有这些，队友会完全绕过代理。
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "NO_PROXY",
    "no_proxy",
    # --- CA bundle overrides ----------------------------------------------
    # 自定义 CA 证书在使用 TLS 检查时必须对队友可见；
    # 缺少这些会导致 SSL 验证失败。
    "SSL_CERT_FILE",
    "NODE_EXTRA_CA_CERTS",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    # --- IllusionCode-native provider settings --------------------------------
    # 这些由 settings._apply_env_overrides() 读取，必须跨 tmux 边界保持，
    # 以便队友使用与负责人相同的提供商。
    "ILLUSION_API_FORMAT",
    "ILLUSION_BASE_URL",
    "ILLUSION_MODEL",
    "OPENAI_API_KEY",
]


def get_teammate_command() -> str:
    """返回用于生成队友进程的可执行文件。

    解析顺序：
    1. ``ILLUSION_TEAMMATE_COMMAND`` 环境变量 —— 允许操作员指向特定二进制或包装脚本。
    2. PATH 上的 ``illusion`` 入口点（已安装包模式）。
    3. 运行当前 ``illusion`` 模块的当前 Python 解释器
       （开发/可编辑安装回退）。
    """
    # 检查环境变量覆盖
    override = os.environ.get(TEAMMATE_COMMAND_ENV_VAR)
    if override:
        return override

    # 检查是否作为已安装包运行，具有入口点。
    entry_point = shutil.which("illusion")
    if entry_point:
        return entry_point

    # 回退到当前运行此代码的 Python 解释器。
    return sys.executable


def build_inherited_cli_flags(
    *,
    model: str | None = None,
    permission_mode: str | None = None,
    plan_mode_required: bool = False,
    settings_path: str | None = None,
    teammate_mode: str | None = None,
    plugin_dirs: list[str] | None = None,
    extra_flags: list[str] | None = None,
) -> list[str]:
    """构建从当前会话继承到生成队友的 CLI 标志。

    确保队友从其父进程继承重要设置，如权限模式、模型选择和插件配置。

    所有标志值都使用 :func:`shlex.quote` 进行 shell 引号处理，以防止
    命令注入，当结果列表稍后连接成 shell 命令字符串时。

    Args:
        model: 要转发的模型覆盖（例如 ``"claude-opus-4-6"``）。
        permission_mode: ``"bypassPermissions"``、``"acceptEdits`` 或 None 之一。
        plan_mode_required: 当为 True 时，bypass-permissions 标志被抑制
            （plan mode 为了安全优先于 bypass）。
        settings_path: 要通过 ``--settings`` 传播的 settings JSON 文件路径。
            为安全起见进行 shell 引号处理。
        teammate_mode: 队友执行模式（``"auto"``, ``"in_process"``,
            ``"tmux"``）。转发为 ``--teammate-mode`` 以便 tmux 队友
            使用与负责人相同的模式。
        plugin_dirs: 插件目录列表。每个都作为单独的
            ``--plugin-dir <path>`` 标志转发，以便内联插件在队友进程中可见。
        extra_flags: 要附加的额外预构建标志字符串。
            调用者负责对这些字符串中的值进行引号处理。

    Returns:
        准备传递给 :mod:`subprocess` 的 CLI 标志字符串列表。
    """
    # 初始化标志列表，包含 headless 模式
    flags: list[str] = ["--headless"]

    # --- Permission mode ---------------------------------------------------
    # Plan mode 优先于 bypass permissions 以确保安全。
    if not plan_mode_required:
        if permission_mode == "bypassPermissions":
            flags.append("--dangerously-skip-permissions")
        elif permission_mode == "acceptEdits":
            flags.extend(["--permission-mode", "acceptEdits"])

    # --- Model override ----------------------------------------------------
    if model:
        flags.extend(["--model", shlex.quote(model)])

    # --- Settings path propagation ----------------------------------------
    # 确保队友加载与负责人进程相同的 settings JSON。
    if settings_path:
        flags.extend(["--settings", shlex.quote(settings_path)])

    # --- Plugin directories -----------------------------------------------
    # 每个启用的插件目录单独转发，以便内联插件
    #（通过 --plugin-dir 加载）在队友中可用。
    for plugin_dir in plugin_dirs or []:
        flags.extend(["--plugin-dir", shlex.quote(plugin_dir)])

    # --- Teammate mode propagation ----------------------------------------
    # 转发会话级队友模式，以便 tmux 生成的队友
    # 不会独立重新检测模式并可能选择不同的模式。
    if teammate_mode:
        flags.extend(["--teammate-mode", shlex.quote(teammate_mode)])

    # 添加额外标志
    if extra_flags:
        flags.extend(extra_flags)

    return flags


def build_inherited_env_vars() -> dict[str, str]:
    """构建要转发到生成队友的环境变量。

    始终包含 ``ILLUSION_AGENT_TEAMS=1`` 加上当前进程中设置的任何提供商/代理变量。

    Returns:
        要合并到子进程环境的 env 变量名 → 值字典。
    """
    # 初始化基础环境变量
    env: dict[str, str] = {
        "ILLUSION_AGENT_TEAMS": "1",
    }

    # 遍历要转发的环境变量列表
    for key in _TEAMMATE_ENV_VARS:
        value = os.environ.get(key)
        if value:
            env[key] = value

    return env


def is_tmux_available() -> bool:
    """如果 ``tmux`` 二进制文件在 PATH 上则返回 True。"""
    return shutil.which("tmux") is not None


def is_inside_tmux() -> bool:
    """如果当前进程在 tmux 会话中运行则返回 True。"""
    return bool(os.environ.get("TMUX"))
