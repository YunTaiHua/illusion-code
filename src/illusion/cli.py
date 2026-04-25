"""
IllusionCode CLI 入口模块
========================

本模块提供 IllusionCode 命令行界面，使用 typer 构建。

主要功能：
    - 交互式会话模式
    - 非交互式打印模式
    - MCP 服务器管理
    - 插件管理
    - 认证管理
    - Cron 任务调度管理

子命令说明：
    - mcp: MCP 服务器管理（list、add、remove）
    - plugin: 插件管理（list、install、uninstall）
    - auth: 认证管理（login、status、logout、switch、copilot-login）
    - cron: Cron 调度管理（start、stop、status、list、toggle、history、logs）

使用示例：
    >>> illusion                    # 启动交互式会话
    >>> illusion -p "你的提示词"     # 非交互式打印模式
    >>> illusion auth login         # 认证登录
    >>> illusion mcp list           # 列出 MCP 服务器
"""

from __future__ import annotations

import json  # JSON 解析和序列化
import sys  # 系统相关功能
from pathlib import Path  # 路径操作
from typing import Optional  # 可选类型注解

import typer  # CLI 框架

# 确保 Windows 上 stdout/stderr 使用 UTF-8，防止通过 tsx 继承 stdio 管道时的 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 应用程序版本
__version__ = "0.1.1"


def _version_callback(value: bool) -> None:
    """版本回调函数
    
    当用户使用 --version 选项时调用，打印版本号并退出程序。
    
    Args:
        value: 标志位，当前始终为 True
    """
    if value:
        print(f"illusion {__version__}")  # 打印版本信息
        raise typer.Exit()  # 退出程序


# 创建主应用程序
app = typer.Typer(
    name="illusion",
    help=(
        "Illusion Code - An AI-powered coding assistant.\n\n"
        "Starts an interactive session by default, use -p/--print for non-interactive output."
    ),
    add_completion=False,
    rich_markup_mode="rich",
    invoke_without_command=True,
)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

# 创建子命令应用（mcp、plugin、auth、cron）
mcp_app = typer.Typer(name="mcp", help="Manage MCP servers")
plugin_app = typer.Typer(name="plugin", help="Manage plugins")
auth_app = typer.Typer(name="auth", help="Manage authentication")
cron_app = typer.Typer(name="cron", help="Manage cron scheduler and jobs")

# 注册子命令到主应用
app.add_typer(mcp_app)
app.add_typer(plugin_app)
app.add_typer(auth_app)
app.add_typer(cron_app)


# ---- mcp 子命令 ----

@mcp_app.command("list")
def mcp_list() -> None:
    """列出已配置的 MCP 服务器
    
    加载当前设置和插件，列出所有已配置的 MCP 服务器及其传输类型。
    """
    from illusion.config import load_settings  # 加载设置
    from illusion.mcp.config import load_mcp_server_configs  # 加载 MCP 配置
    from illusion.plugins import load_plugins  # 加载插件

    settings = load_settings()  # 加载应用设置
    plugins = load_plugins(settings, str(Path.cwd()))  # 加载插件
    configs = load_mcp_server_configs(settings, plugins)  # 加载 MCP 服务器配置
    if not configs:  # 如果没有配置
        print("No MCP servers configured.")
        return
    for name, cfg in configs.items():  # 遍历所有配置
        transport = cfg.get("transport", cfg.get("command", "unknown"))  # 获取传输类型
        print(f"  {name}: {transport}")  # 打印服务器名称和传输类型


@mcp_app.command("add")
def mcp_add(
    name: str = typer.Argument(..., help="Server name"),
    config_json: str = typer.Argument(..., help="Server config as JSON string"),
) -> None:
    """添加 MCP 服务器配置
    
    Args:
        name: 服务器名称
        config_json: 服务器配置的 JSON 字符串
    """
    from illusion.config import load_settings, save_settings  # 加载和保存设置

    settings = load_settings()  # 加载当前设置
    try:
        cfg = json.loads(config_json)  # 解析 JSON 配置
    except json.JSONDecodeError as exc:  # JSON 解析错误
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        raise typer.Exit(1)
    if not isinstance(settings.mcp_servers, dict):  # 确保 mcp_servers 是字典
        settings.mcp_servers = {}
    settings.mcp_servers[name] = cfg  # 添加或更新服务器配置
    save_settings(settings)  # 保存设置
    print(f"Added MCP server: {name}")


@mcp_app.command("remove")
def mcp_remove(
    name: str = typer.Argument(..., help="Server name to remove"),
) -> None:
    """移除 MCP 服务器配置
    
    Args:
        name: 要移除的服务器名称
    """
    from illusion.config import load_settings, save_settings  # 加载和保存设置

    settings = load_settings()  # 加载当前设置
    if not isinstance(settings.mcp_servers, dict) or name not in settings.mcp_servers:  # 检查服务器是否存在
        print(f"MCP server not found: {name}", file=sys.stderr)
        raise typer.Exit(1)
    del settings.mcp_servers[name]  # 删除服务器配置
    save_settings(settings)  # 保存设置
    print(f"Removed MCP server: {name}")


# ---- plugin 子命令 ----

@plugin_app.command("list")
def plugin_list() -> None:
    """列出已安装的插件
    
    显示所有已安装插件的名称、状态和描述。
    """
    from illusion.config import load_settings  # 加载设置
    from illusion.plugins import load_plugins  # 加载插件

    settings = load_settings()  # 加载应用设置
    plugins = load_plugins(settings, str(Path.cwd()))  # 加载已安装的插件
    if not plugins:  # 如果没有插件
        print("No plugins installed.")
        return
    for plugin in plugins:  # 遍历所有插件
        status = "enabled" if plugin.enabled else "disabled"  # 获取插件状态
        print(f"  {plugin.name} [{status}] - {plugin.description or ''}")


@plugin_app.command("install")
def plugin_install(
    source: str = typer.Argument(..., help="Plugin source (path or URL)"),
) -> None:
    """从源路径安装插件
    
    Args:
        source: 插件源路径（本地路径或 URL）
    """
    from illusion.plugins.installer import install_plugin_from_path  # 插件安装器

    result = install_plugin_from_path(source)  # 从路径安装插件
    print(f"Installed plugin: {result}")


@plugin_app.command("uninstall")
def plugin_uninstall(
    name: str = typer.Argument(..., help="Plugin name to uninstall"),
) -> None:
    """卸载插件
    
    Args:
        name: 要卸载的插件名称
    """
    from illusion.plugins.installer import uninstall_plugin  # 插件卸载器

    uninstall_plugin(name)  # 卸载指定插件
    print(f"Uninstalled plugin: {name}")


# ---- cron 子命令 ----

@cron_app.command("start")
def cron_start() -> None:
    """启动 cron 调度器守护进程
    
    在后台启动 cron 调度器，用于定时执行已配置的任务。
    """
    from illusion.services.cron_scheduler import is_scheduler_running, start_daemon  # 调度器相关功能

    if is_scheduler_running():  # 检查调度器是否已运行
        print("Cron scheduler is already running.")
        return
    pid = start_daemon()  # 启动守护进程
    print(f"Cron scheduler started (pid={pid})")


@cron_app.command("stop")
def cron_stop() -> None:
    """停止 cron 调度器守护进程
    
    停止当前运行的 cron 调度器。
    """
    from illusion.services.cron_scheduler import stop_scheduler  # 停止调度器

    if stop_scheduler():  # 尝试停止调度器
        print("Cron scheduler stopped.")
    else:
        print("Cron scheduler is not running.")


@cron_app.command("status")
def cron_status_cmd() -> None:
    """显示 cron 调度器状态和任务摘要
    
    显示调度器的运行状态、已启用任务数和总任务数。
    """
    from illusion.services.cron_scheduler import scheduler_status  # 调度器状态

    status = scheduler_status()  # 获取调度器状态
    state = "running" if status["running"] else "stopped"  # 运行状态
    print(f"Scheduler: {state}" + (f" (pid={status['pid']})" if status["pid"] else ""))
    print(f"Jobs:      {status['enabled_jobs']} enabled / {status['total_jobs']} total")
    print(f"Log:       {status['log_file']}")


@cron_app.command("list")
def cron_list_cmd() -> None:
    """列出所有已注册的 cron 任务及其调度和时间
    
    显示所有已配置的任务名称、启用状态、上次运行时间和下次运行时间。
    """
    from illusion.services.cron import load_cron_jobs  # 加载 cron 任务

    jobs = load_cron_jobs()  # 加载所有任务
    if not jobs:  # 如果没有任务
        print("No cron jobs configured.")
        return
    for job in jobs:  # 遍历所有任务
        enabled = "on " if job.get("enabled", True) else "off"  # 启用状态
        last = job.get("last_run", "never")  # 上次运行时间
        if last != "never":
            last = last[:19]  # 修剪为可读日期时间
        last_status = job.get("last_status", "")  # 上次运行状态
        status_indicator = f" [{last_status}]" if last_status else ""  # 状态指示器
        print(f"  [{enabled}] {job['name']}  {job.get('schedule', '?')}")
        print(f"        cmd: {job['command']}")
        print(f"        last: {last}{status_indicator}  next: {job.get('next_run', 'n/a')[:19]}")


@cron_app.command("toggle")
def cron_toggle_cmd(
    name: str = typer.Argument(..., help="Cron job name"),
    enabled: bool = typer.Argument(..., help="true to enable, false to disable"),
) -> None:
    """启用或禁用 cron 任务
    
    Args:
        name: 任务名称
        enabled: True 启用，False 禁用
    """
    from illusion.services.cron import set_job_enabled  # 设置任务启用状态

    if not set_job_enabled(name, enabled):  # 设置启用状态
        print(f"Cron job not found: {name}")
        raise typer.Exit(1)
    state = "enabled" if enabled else "disabled"  # 状态描述
    print(f"Cron job '{name}' is now {state}")


@cron_app.command("history")
def cron_history_cmd(
    name: str | None = typer.Argument(None, help="Filter by job name"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of entries"),
) -> None:
    """显示 cron 执行历史
    
    显示任务执行记录，包括时间、状态和返回码。
    
    Args:
        name: 可选的任务名称过滤
        limit: 显示的记录数，默认 20 条
    """
    from illusion.services.cron_scheduler import load_history  # 加载执行历史

    entries = load_history(limit=limit, job_name=name)  # 加载历史记录
    if not entries:  # 如果没有记录
        print("No execution history.")
        return
    for entry in entries:  # 遍历所有记录
        ts = entry.get("started_at", "?")[:19]  # 获取时间戳
        status = entry.get("status", "?")  # 获取状态
        rc = entry.get("returncode", "?")  # 获取返回码
        print(f"  {ts}  {entry.get('name', '?')}  {status} (rc={rc})")
        stderr = entry.get("stderr", "").strip()  # 获取错误输出
        if stderr and status != "success":  # 如果有错误输出且状态不是成功
            for line in stderr.splitlines()[:3]:  # 只显示前 3 行
                print(f"    stderr: {line}")


@cron_app.command("logs")
def cron_logs_cmd(
    lines: int = typer.Option(30, "--lines", "-n", help="Number of lines to show"),
) -> None:
    """显示最近的 cron 调度器日志输出
    
    Args:
        lines: 显示的行数，默认 30 行
    """
    from illusion.config.paths import get_logs_dir  # 获取日志目录

    log_path = get_logs_dir() / "cron_scheduler.log"  # 日志文件路径
    if not log_path.exists():  # 如果日志文件不存在
        print("No scheduler log found. Start the scheduler with: illusion cron start")
        return
    content = log_path.read_text(encoding="utf-8", errors="replace")  # 读取日志内容
    tail = content.splitlines()[-lines:]  # 获取最后 n 行
    for line in tail:  # 遍历每一行
        print(line)


# ---- auth 子命令 ----

# 提供商名称到人类可读标签的映射，用于交互式提示
_PROVIDER_LABELS: dict[str, str] = {
    "anthropic": "Anthropic (Claude API)",
    "openai": "OpenAI / compatible",
    "copilot": "GitHub Copilot",
    "dashscope": "Alibaba DashScope",
    "bedrock": "AWS Bedrock",
    "vertex": "Google Vertex AI",
}


@auth_app.command("login")
def auth_login(
    provider: Optional[str] = typer.Argument(None, help="Provider name (anthropic, openai, copilot, …)"),
) -> None:
    """交互式认证提供商
    
    无参数运行时从菜单选择提供商。
    支持的提供商：anthropic, openai, copilot, dashscope, bedrock, vertex。
    
    Args:
        provider: 可选的提供商名称
    """
    from illusion.auth.flows import ApiKeyFlow  # API 密钥流程
    from illusion.auth.manager import AuthManager  # 认证管理器
    from illusion.auth.storage import store_credential  # 凭证存储

    manager = AuthManager()  # 创建认证管理器实例

    if provider is None:  # 如果没有指定提供商
        print("Select a provider to authenticate:", flush=True)
        labels = list(_PROVIDER_LABELS.items())  # 获取提供商标签列表
        for i, (name, label) in enumerate(labels, 1):  # 遍历并显示选项
            print(f"  {i}. {label} [{name}]", flush=True)
        raw = typer.prompt("Enter number or provider name", default="1")  # 提示用户选择
        try:
            idx = int(raw.strip()) - 1  # 转换为索引
            if 0 <= idx < len(labels):  # 有效索引范围
                provider = labels[idx][0]  # 获取提供商名称
            else:
                print("Invalid selection.", file=sys.stderr)
                raise typer.Exit(1)
        except ValueError:  # 输入不是数字
            provider = raw.strip()  # 直接使用输入作为提供商名称

    provider = provider.lower()  # 转换为小写

    # Copilot 使用特殊登录流程
    if provider == "copilot":
        _run_copilot_login()  # 运行 Copilot 登录
        return

    # 基于 API 密钥的提供商
    if provider in ("anthropic", "openai", "dashscope", "bedrock", "vertex"):
        label = _PROVIDER_LABELS.get(provider, provider)  # 获取标签
        flow = ApiKeyFlow(provider=provider, prompt_text=f"Enter your {label} API key")  # 创建 API 密钥流程
        try:
            key = flow.run()  # 运行流程获取 API 密钥
        except ValueError as exc:  # 获取失败
            print(f"Error: {exc}", file=sys.stderr)
            raise typer.Exit(1)
        store_credential(provider, "api_key", key)  # 存储凭证
        # 保持 settings.api_key 与活动提供商同步
        try:
            manager.store_credential(provider, "api_key", key)  # 存储到管理器
        except Exception:
            pass
        print(f"{label} API key saved.", flush=True)
        return

    print(f"Unknown provider: {provider!r}. Known: {', '.join(_PROVIDER_LABELS)}", file=sys.stderr)
    raise typer.Exit(1)


@auth_app.command("status")
def auth_status_cmd() -> None:
    """以表格形式显示所有提供商的认证状态
    
    显示每个配置提供商的认证状态、来源和是否活动提供商。
    """
    from illusion.auth.manager import AuthManager  # 认证管理器

    manager = AuthManager()  # 创建认证管理器实例
    statuses = manager.get_auth_status()  # 获取所有提供商状态

    col_provider = 22  # 提供商列宽度
    col_status = 12  # 状态列宽度
    col_source = 10  # 来源列宽度
    header = f"{'Provider':<{col_provider}} {'Status':<{col_status}} {'Source':<{col_source}} Active"
    print(header)  # 打印表头
    print("-" * len(header))  # 打印分隔线

    for name, info in statuses.items():  # 遍历所有提供商
        label = _PROVIDER_LABELS.get(name, name)  # 获取标签
        status_str = "configured" if info["configured"] else "missing"  # 状态字符串
        source_str = info["source"]  # 来源字符串
        active_str = "<-- active" if info["active"] else ""  # 活动提供商指示
        print(f"{label:<{col_provider}} {status_str:<{col_status}} {source_str:<{col_source}} {active_str}")


@auth_app.command("logout")
def auth_logout(
    provider: Optional[str] = typer.Argument(None, help="Provider to log out (default: active provider)"),
) -> None:
    """清除提供商的已存储认证
    
    Args:
        provider: 要登出的提供商，默认登出活动提供商
    """
    from illusion.auth.manager import AuthManager  # 认证管理器

    manager = AuthManager()  # 创建认证管理器实例
    target = provider or manager.get_active_provider()  # 获取目标提供商
    manager.clear_credential(target)  # 清除凭证
    print(f"Authentication cleared for provider: {target}", flush=True)


@auth_app.command("switch")
def auth_switch(
    provider: str = typer.Argument(..., help="Provider to activate"),
) -> None:
    """切换活动提供商
    
    Args:
        provider: 要激活的提供商名称
    """
    from illusion.auth.manager import AuthManager  # 认证管理器

    manager = AuthManager()  # 创建认证管理器实例
    try:
        manager.switch_provider(provider)  # 切换提供商
    except ValueError as exc:  # 切换失败
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(1)
    print(f"Switched active provider to: {provider}", flush=True)


# ---------------------------------------------------------------------------
# Copilot 登录辅助函数（保留为命名函数以便重用和向后兼容）
# ---------------------------------------------------------------------------


def _run_copilot_login() -> None:
    """运行 GitHub Copilot 设备代码流并持久化结果
    
    通过 OAuth 设备代码流程认证 GitHub Copilot，支持 GitHub.com 和 GitHub Enterprise。
    """
    from illusion.api.copilot_auth import save_copilot_auth  # Copilot 认证保存
    from illusion.auth.flows import DeviceCodeFlow  # 设备代码流程

    print("Select GitHub deployment type:", flush=True)
    print("  1. GitHub.com (public)", flush=True)
    print("  2. GitHub Enterprise (data residency / self-hosted)", flush=True)
    choice = typer.prompt("Enter choice", default="1")  # 提示用户选择

    enterprise_url: str | None = None  # 企业版 URL
    github_domain = "github.com"  # GitHub 域名

    if choice.strip() == "2":  # 如果选择企业版
        raw_url = typer.prompt("Enter your GitHub Enterprise URL or domain (e.g. company.ghe.com)")
        domain = raw_url.replace("https://", "").replace("http://", "").rstrip("/")
        if not domain:  # 验证域名不为空
            print("Error: domain cannot be empty.", file=sys.stderr, flush=True)
            raise typer.Exit(1)
        enterprise_url = domain  # 设置企业版 URL
        github_domain = domain  # 设置 GitHub 域名

    print(flush=True)
    flow = DeviceCodeFlow(github_domain=github_domain, enterprise_url=enterprise_url)  # 创建设备代码流程
    try:
        token = flow.run()  # 运行流程获取令牌
    except RuntimeError as exc:  # 流程失败
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        raise typer.Exit(1)

    save_copilot_auth(token, enterprise_url=enterprise_url)  # 保存 Copilot 认证
    print("GitHub Copilot authenticated successfully.", flush=True)
    if enterprise_url:  # 如果是企业版
        print(f"  Enterprise domain: {enterprise_url}", flush=True)
    print(flush=True)
    print("To use Copilot as the provider, run:", flush=True)
    print("  illusion auth switch copilot", flush=True)
    print("  # or set ILLUSION_API_FORMAT=copilot", flush=True)


@auth_app.command("copilot-login")
def auth_copilot_login() -> None:
    """通过设备流认证 GitHub Copilot（'illusion auth login copilot' 的别名）
    
    使用 OAuth 设备代码流程进行 GitHub Copilot 认证。
    """
    _run_copilot_login()  # 调用辅助函数


@auth_app.command("copilot-logout")
def auth_copilot_logout() -> None:
    """删除已存储的 GitHub Copilot 认证
    
    清除所有已存储的 GitHub Copilot 令牌和配置。
    """
    from illusion.api.copilot_auth import clear_github_token  # 清除 GitHub 令牌

    clear_github_token()  # 清除令牌
    print("Copilot authentication cleared.")

# ---------------------------------------------------------------------------
# 主命令
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
    # --- Session ---
    continue_session: bool = typer.Option(
        False,
        "--continue",
        "-c",
        help="Continue the most recent conversation in the current directory",
        rich_help_panel="Session",
    ),
    resume: str | None = typer.Option(
        None,
        "--resume",
        "-r",
        help="Resume a conversation by session ID, or open picker",
        rich_help_panel="Session",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Set a display name for this session",
        rich_help_panel="Session",
    ),
    # --- Model & Effort ---
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Model alias (e.g. 'sonnet', 'opus') or full model ID",
        rich_help_panel="Model & Effort",
    ),
    effort: str | None = typer.Option(
        None,
        "--effort",
        help="Effort level for the session (low, medium, high, max)",
        rich_help_panel="Model & Effort",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Override verbose mode setting from config",
        rich_help_panel="Model & Effort",
    ),
    max_turns: int | None = typer.Option(
        None,
        "--max-turns",
        help="Maximum number of agentic turns (useful with --print)",
        rich_help_panel="Model & Effort",
    ),
    # --- Output ---
    print_mode: str | None = typer.Option(
        None,
        "--print",
        "-p",
        help="Print response and exit. Pass your prompt as the value: -p 'your prompt'",
        rich_help_panel="Output",
    ),
    output_format: str | None = typer.Option(
        None,
        "--output-format",
        help="Output format with --print: text (default), json, or stream-json",
        rich_help_panel="Output",
    ),
    # --- Permissions ---
    permission_mode: str | None = typer.Option(
        None,
        "--permission-mode",
        help="Permission mode: default, plan, or full_auto",
        rich_help_panel="Permissions",
    ),
    dangerously_skip_permissions: bool = typer.Option(
        False,
        "--dangerously-skip-permissions",
        help="Bypass all permission checks (only for sandboxed environments)",
        rich_help_panel="Permissions",
    ),
    allowed_tools: Optional[list[str]] = typer.Option(
        None,
        "--allowed-tools",
        help="Comma or space-separated list of tool names to allow",
        rich_help_panel="Permissions",
    ),
    disallowed_tools: Optional[list[str]] = typer.Option(
        None,
        "--disallowed-tools",
        help="Comma or space-separated list of tool names to deny",
        rich_help_panel="Permissions",
    ),
    # --- System & Context ---
    system_prompt: str | None = typer.Option(
        None,
        "--system-prompt",
        "-s",
        help="Override the default system prompt",
        rich_help_panel="System & Context",
    ),
    append_system_prompt: str | None = typer.Option(
        None,
        "--append-system-prompt",
        help="Append text to the default system prompt",
        rich_help_panel="System & Context",
    ),
    settings_file: str | None = typer.Option(
        None,
        "--settings",
        help="Path to a JSON settings file or inline JSON string",
        rich_help_panel="System & Context",
    ),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="Anthropic-compatible API base URL",
        rich_help_panel="System & Context",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="API key (overrides config and environment)",
        rich_help_panel="System & Context",
    ),
    bare: bool = typer.Option(
        False,
        "--bare",
        help="Minimal mode: skip hooks, plugins, MCP, and auto-discovery",
        rich_help_panel="System & Context",
    ),
    api_format: str | None = typer.Option(
        None,
        "--api-format",
        help="API format: 'anthropic' (default), 'openai' (DashScope, GitHub Models, etc.), or 'copilot' (GitHub Copilot)",
        rich_help_panel="System & Context",
    ),
    theme: str | None = typer.Option(
        None,
        "--theme",
        help="TUI theme: default, dark, minimal, cyberpunk, solarized, or custom name",
        rich_help_panel="System & Context",
    ),
    # --- Advanced ---
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable debug logging",
        rich_help_panel="Advanced",
    ),
    mcp_config: Optional[list[str]] = typer.Option(
        None,
        "--mcp-config",
        help="Load MCP servers from JSON files or strings",
        rich_help_panel="Advanced",
    ),
    cwd: str = typer.Option(
        str(Path.cwd()),
        "--cwd",
        help="Working directory for the session",
        hidden=True,
    ),
    backend_only: bool = typer.Option(
        False,
        "--backend-only",
        help="Run the structured backend host for the React terminal UI",
        hidden=True,
    ),
) -> None:
    """主入口函数：启动交互式会话或运行单个提示词
    
    支持多种运行模式：
    - 交互式会话模式（默认）
    - 非交互式打印模式（使用 -p/--print）
    - 继续会话（使用 --continue 或 --resume）
    
    Args:
        ctx: Typer 上下文对象
        version: 显示版本号选项
        continue_session: 继续最近会话选项
        resume: 通过会话 ID 恢复会话选项
        name: 会话显示名称
        model: 模型别名或完整模型 ID
        effort: 会话努力级别
        verbose: 覆盖详细输出模式设置
        max_turns: 最大代理轮次数
        print_mode: 打印模式提示词
        output_format: 输出格式
        permission_mode: 权限模式
        dangerously_skip_permissions: 跳过权限检查
        allowed_tools: 允许的工具列表
        disallowed_tools: 禁止的工具列表
        system_prompt: 覆盖默认系统提示词
        append_system_prompt: 追加到默认系统提示词
        settings_file: 设置文件路径
        base_url: Anthropic 兼容 API 基础 URL
        api_key: API 密钥
        bare: 最小模式
        api_format: API 格式
        theme: TUI 主题
        debug: 启用调试日志
        mcp_config: 从 JSON 文件或字符串加载 MCP 服务器
        cwd: 会话工作目录
        backend_only: 运行结构化后端主机
    """
    if ctx.invoked_subcommand is not None:  # 如果调用了子命令，直接返回
        return

    import asyncio  # 异步编程模块

    if dangerously_skip_permissions:  # 如果跳过权限检查
        permission_mode = "full_auto"  # 设置为完全自动模式

    # 应用 --theme 覆盖到设置
    if theme:
        from illusion.config.settings import load_settings, save_settings  # 导入设置模块

        settings = load_settings()  # 加载设置
        settings.theme = theme  # 设置主题
        save_settings(settings)  # 保存设置

    from illusion.ui.app import run_print_mode, run_repl  # 导入 UI 模块

    # 处理 --continue 和 --resume 标志
    if continue_session or resume is not None:
        from illusion.services.session_storage import (  # 导入会话存储模块
            list_session_snapshots,  # 列出会话快照
            load_session_by_id,  # 按 ID 加载会话
            load_session_snapshot,  # 加载会话快照
        )

        session_data = None  # 会话数据
        if continue_session:  # 继续最近会话
            session_data = load_session_snapshot(cwd)  # 加载会话快照
            if session_data is None:  # 如果没有找到会话
                print("No previous session found in this directory.", file=sys.stderr)
                raise typer.Exit(1)
            print(f"Continuing session: {session_data.get('summary', '(untitled)')[:60]}")
        elif resume == "" or resume is None:  # 显示会话选择器
            # --resume 无值：显示会话选择器
            sessions = list_session_snapshots(cwd, limit=10)  # 列出最近 10 个会话
            if not sessions:  # 如果没有保存的会话
                print("No saved sessions found.", file=sys.stderr)
                raise typer.Exit(1)
            print("Saved sessions:")
            for i, s in enumerate(sessions, 1):  # 遍历所有会话
                print(f"  {i}. [{s['session_id']}] {s.get('summary', '?')[:50]} ({s['message_count']} msgs)")
            choice = typer.prompt("Enter session number or ID")  # 提示用户选择
            try:
                idx = int(choice) - 1  # 转换为索引
                if 0 <= idx < len(sessions):  # 有效索引范围
                    session_data = load_session_by_id(cwd, sessions[idx]["session_id"])  # 加载会话
                else:
                    print("Invalid selection.", file=sys.stderr)
                    raise typer.Exit(1)
            except ValueError:  # 输入不是数字
                session_data = load_session_by_id(cwd, choice)  # 直接使用输入作为会话 ID
            if session_data is None:  # 如果会话不存在
                print(f"Session not found: {choice}", file=sys.stderr)
                raise typer.Exit(1)
        else:  # 按会话 ID 恢复
            session_data = load_session_by_id(cwd, resume)  # 加载指定会话
            if session_data is None:  # 如果会话不存在
                print(f"Session not found: {resume}", file=sys.stderr)
                raise typer.Exit(1)

        # 将会话传递给 REPL
        asyncio.run(
            run_repl(
                prompt=None,  # 无提示词，使用恢复的会话
                cwd=cwd,  # 工作目录
                model=session_data.get("model") or model,  # 模型
                backend_only=backend_only,  # 仅后端模式
                base_url=base_url,  # 基础 URL
                system_prompt=session_data.get("system_prompt") or system_prompt,  # 系统提示词
                api_key=api_key,  # API 密钥
                restore_messages=session_data.get("messages"),  # 恢复的消息
                restore_session_id=session_data.get("session_id"),
            )
        )
        return

    # 打印模式处理
    if print_mode is not None:
        prompt = print_mode.strip()
        if not prompt:  # 验证提示词不为空
            print("Error: -p/--print requires a prompt value, e.g. -p 'your prompt'", file=sys.stderr)
            raise typer.Exit(1)
        # 运行打印模式
        asyncio.run(
            run_print_mode(
                prompt=prompt,  # 提示词
                output_format=output_format or "text",  # 输出格式
                cwd=cwd,  # 工作目录
                model=model,  # 模型
                base_url=base_url,  # 基础 URL
                system_prompt=system_prompt,  # 系统提示词
                append_system_prompt=append_system_prompt,  # 追加系统提示词
                api_key=api_key,  # API 密钥
                api_format=api_format,  # API 格式
                permission_mode=permission_mode,  # 权限模式
                max_turns=max_turns,  # 最大轮次
            )
        )
        return

    # 启动交互式 REPL 会话
    asyncio.run(
        run_repl(
            prompt=None,  # 无初始提示词
            cwd=cwd,  # 工作目录
            model=model,  # 模型
            max_turns=max_turns,  # 最大轮次
            backend_only=backend_only,  # 仅后端模式
            base_url=base_url,  # 基础 URL
            system_prompt=system_prompt,  # 系统提示词
            api_key=api_key,  # API 密钥
            api_format=api_format,  # API 格式
        )
    )
