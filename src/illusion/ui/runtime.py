"""
Runtime 运行时模块
================

本模块实现无 UI 和 Textual UI 共享的运行时程序集。

主要功能：
    - 运行时数据 bundle 管理
    - API 客户端初始化和配置
    - 工具注册和权限检查
    - 会话状态管理
    - 命令处理和执行
    - 会话快照保存

类说明：
    - RuntimeBundle: 共享运行时数据bundle
    - build_runtime: 构建运行时
    - start_runtime: 启动运行时（执行会话开始钩子）
    - close_runtime: 关闭运行时并清理资源
    - handle_line: 处理用户输入行
    - sync_app_state: 同步应用状态

使用示例：
    >>> from illusion.ui.runtime import build_runtime, handle_line, start_runtime, close_runtime
    >>> 
    >>> # 构建运行时
    >>> bundle = await build_runtime(model="claude-sonnet-4-20250514")
    >>> await start_runtime(bundle)
    >>> 
    >>> # 处理输入行
    >>> await handle_line(
    ...     bundle,
    ...     "帮我写一个 hello world 程序",
    ...     print_system=print_system,
    ...     render_event=render_event,
    ...     clear_output=clear_output,
    ... )
    >>> 
    >>> # 关闭运行时
    >>> await close_runtime(bundle)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import uuid4

from illusion.api.client import AnthropicApiClient, SupportsStreamingMessages
from illusion.api.copilot_client import CopilotClient
from illusion.api.openai_client import OpenAICompatibleClient
from illusion.api.provider import auth_status, detect_provider
from illusion.bridge import get_bridge_manager
from illusion.commands import CommandContext, CommandResult, create_default_command_registry
from illusion.config import get_config_file_path, load_settings
from illusion.engine import QueryEngine
from illusion.engine.messages import ConversationMessage, ToolResultBlock, ToolUseBlock
from illusion.engine.query import MaxTurnsExceeded
from illusion.engine.stream_events import StreamEvent
from illusion.hooks import HookEvent, HookExecutionContext, HookExecutor, load_hook_registry
from illusion.hooks.hot_reload import HookReloader
from illusion.mcp.client import McpClientManager
from illusion.mcp.config import load_mcp_server_configs
from illusion.permissions import PermissionChecker
from illusion.plugins import load_plugins
from illusion.prompts import build_runtime_system_prompt
from illusion.state import AppState, AppStateStore
from illusion.services.session_storage import save_session_snapshot
from illusion.tools import ToolRegistry, create_default_tool_registry

# 类型别名定义
PermissionPrompt = Callable[[str, str], Awaitable[bool]]  # 权限确认回调
AskUserPrompt = Callable[[str], Awaitable[str]]  # 用户问答回调
SystemPrinter = Callable[[str], Awaitable[None]]  # 系统消息打印回调
StreamRenderer = Callable[[StreamEvent], Awaitable[None]]  # 流式事件渲染回调
ClearHandler = Callable[[], Awaitable[None]]  # 清空输出回调
TranscriptItemSender = Callable[[dict], Awaitable[None]]  # 发送 transcript_item 的回调


@dataclass
class RuntimeBundle:
    """共享运行时数据bundle。

    用于存储一次交互式会话的所有运行时对象。
    包括 API 客户端、工具注册器、引擎、状态管理等。

    Attributes:
        api_client: 流式 API 客户端实例
        cwd: 当前工作目录
        mcp_manager: MCP 客户端管理器
        tool_registry: 工具注册器
        app_state: 应用状态存储
        hook_executor: 钩子执行器
        engine: 查询引擎
        commands: 命令注册表
        external_api_client: 是否使用外部 API 客户端
        session_id: 会话 ID
        settings_overrides: 设置覆盖字典
    """

    api_client: SupportsStreamingMessages
    cwd: str
    mcp_manager: McpClientManager
    tool_registry: ToolRegistry
    app_state: AppStateStore
    hook_executor: HookExecutor
    engine: QueryEngine
    commands: object
    external_api_client: bool
    session_id: str = ""
    settings_overrides: dict[str, Any] = field(default_factory=dict)

    def current_settings(self):
        """返回会话的有效设置。

        大多数设置持久化到磁盘（~/.illusion/settings.json），
        但 CLI 选项如 --model/--api-format 在进程生命周期内保持有效。
        没有此覆盖，发送任何斜杠命令（如 /fast）会从磁盘刷新 UI 状态，
        并将 model/provider " snap back" 到配置文件中的值。
        """
        return load_settings().merge_cli_overrides(**self.settings_overrides)

    def current_plugins(self):
        """返回当前工作树的可见插件。"""
        return load_plugins(self.current_settings(), self.cwd)

    def hook_summary(self) -> str:
        """返回当前钩子摘要。"""
        return load_hook_registry(self.current_settings(), self.current_plugins()).summary()

    def plugin_summary(self) -> str:
        """返回当前插件摘要。"""
        plugins = self.current_plugins()
        if not plugins:
            return "No plugins discovered."
        lines = ["Plugins:"]
        for plugin in plugins:
            state = "enabled" if plugin.enabled else "disabled"
            lines.append(f"- {plugin.manifest.name} [{state}] {plugin.manifest.description}")
        return "\n".join(lines)

    def mcp_summary(self) -> str:
        """返回当前 MCP 摘要。"""
        statuses = self.mcp_manager.list_statuses()
        if not statuses:
            return "No MCP servers configured."
        lines = ["MCP servers:"]
        for status in statuses:
            suffix = f" - {status.detail}" if status.detail else ""
            lines.append(f"- {status.name}: {status.state}{suffix}")
            if status.tools:
                lines.append(f"  tools: {', '.join(tool.name for tool in status.tools)}")
            if status.resources:
                lines.append(f"  resources: {', '.join(resource.uri for resource in status.resources)}")
        return "\n".join(lines)


async def build_runtime(
    *,
    prompt: str | None = None,
    model: str | None = None,
    max_turns: int | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
    api_key: str | None = None,
    api_format: str | None = None,
    api_client: SupportsStreamingMessages | None = None,
    permission_prompt: PermissionPrompt | None = None,
    ask_user_prompt: AskUserPrompt | None = None,
    restore_messages: list[dict] | None = None,
    restore_session_id: str | None = None,
) -> RuntimeBundle:
    """构建 IllusionCode 会话的共享运行时。

    初始化所有运行时对象，包括 API 客户端、插件、工具注册器、引擎等。

    Args:
        prompt: 初始用户提示词
        model: 使用的模型名称
        max_turns: 最大对话轮次
        base_url: API 基础 URL
        system_prompt: 系统提示词
        api_key: API 密钥
        api_format: API 格式（copilot/openai/anthropic）
        api_client: 流式 API 客户端实例
        permission_prompt: 权限确认回调函数
        ask_user_prompt: 用户问答回调函数
        restore_messages: 恢复的会话消息列表

    Returns:
        RuntimeBundle: 运行时数据 bundle
    """
    # 构建设置覆盖字典
    settings_overrides: dict[str, Any] = {
        "model": model,
        "max_turns": max_turns,
        "base_url": base_url,
        "system_prompt": system_prompt,
        "api_key": api_key,
        "api_format": api_format,
    }
    settings = load_settings().merge_cli_overrides(**settings_overrides)
    # 获取当前工作目录
    cwd = str(Path.cwd())
    # 加载插件
    plugins = load_plugins(settings, cwd)
    # 解析 API 客户端
    if api_client:
        resolved_api_client = api_client
    elif settings.api_format == "copilot":
        from illusion.api.copilot_client import COPILOT_DEFAULT_MODEL
        copilot_model = settings.model if settings.model != "claude-sonnet-4-20250514" else COPILOT_DEFAULT_MODEL
        resolved_api_client = CopilotClient(model=copilot_model)
    elif settings.api_format == "openai":
        resolved_api_client = OpenAICompatibleClient(
            api_key=settings.resolve_api_key(),
            base_url=settings.base_url,
        )
    else:
        resolved_api_client = AnthropicApiClient(
            api_key=settings.resolve_api_key(),
            base_url=settings.base_url,
        )
    # 创建 MCP 客户端管理器
    mcp_manager = McpClientManager(load_mcp_server_configs(settings, plugins, cwd))
    await mcp_manager.connect_all()
    # 创建工具注册器
    tool_registry = create_default_tool_registry(mcp_manager)
    # 检测提供者
    provider = detect_provider(settings)
    # 获取桥接管理器
    bridge_manager = get_bridge_manager()
    # 创建应用状态存储
    app_state = AppStateStore(
        AppState(
            model=settings.model,
            permission_mode=settings.permission.mode.value,
            theme=settings.theme,
            ui_language=settings.ui_language,
            cwd=cwd,
            provider=provider.name,
            auth_status=auth_status(settings),
            base_url=settings.base_url or "",
            fast_mode=settings.fast_mode,
            effort=settings.effort,
            passes=settings.passes,
            mcp_connected=sum(1 for status in mcp_manager.list_statuses() if status.state == "connected"),
            mcp_failed=sum(1 for status in mcp_manager.list_statuses() if status.state == "failed"),
            bridge_sessions=len(bridge_manager.list_sessions()),
            output_style=settings.output_style,
            phase="idle",
        )
    )
    # 创建钩子重载器和执行器
    hook_reloader = HookReloader(get_config_file_path())
    hook_executor = HookExecutor(
        hook_reloader.current_registry() if api_client is None else load_hook_registry(settings, plugins),
        HookExecutionContext(
            cwd=Path(cwd).resolve(),
            api_client=resolved_api_client,
            default_model=settings.model,
        ),
    )
    # 创建查询引擎
    engine = QueryEngine(
        api_client=resolved_api_client,
        tool_registry=tool_registry,
        permission_checker=PermissionChecker(settings.permission),
        cwd=cwd,
        model=settings.model,
        system_prompt=build_runtime_system_prompt(settings, cwd=cwd, latest_user_prompt=prompt),
        max_tokens=settings.max_tokens,
        max_turns=settings.max_turns,
        permission_prompt=permission_prompt,
        ask_user_prompt=ask_user_prompt,
        hook_executor=hook_executor,
        tool_metadata={"mcp_manager": mcp_manager, "bridge_manager": bridge_manager},
    )
    # 从保存的会话恢复消息（如果提供）
    if restore_messages:
        restored = [
            ConversationMessage.model_validate(m) for m in restore_messages
        ]
        engine.load_messages(restored)

    return RuntimeBundle(
        api_client=resolved_api_client,
        cwd=cwd,
        mcp_manager=mcp_manager,
        tool_registry=tool_registry,
        app_state=app_state,
        hook_executor=hook_executor,
        engine=engine,
        commands=create_default_command_registry(),
        external_api_client=api_client is not None,
        session_id=restore_session_id or uuid4().hex[:12],
        settings_overrides=settings_overrides,
    )


async def start_runtime(bundle: RuntimeBundle) -> None:
    """运行会话开始钩子。

    执行 SESSION_START 钩子事件。

    Args:
        bundle: 运行时数据 bundle
    """
    await bundle.hook_executor.execute(
        HookEvent.SESSION_START,
        {"cwd": bundle.cwd, "event": HookEvent.SESSION_START.value},
    )


async def close_runtime(bundle: RuntimeBundle) -> None:
    """关闭运行时拥有的资源。

    关闭 MCP 管理器并执行 SESSION_END 钩子。

    Args:
        bundle: 运行时数据 bundle
    """
    # 关闭 MCP 管理器
    await bundle.mcp_manager.close()
    # 执行会话结束钩子
    await bundle.hook_executor.execute(
        HookEvent.SESSION_END,
        {"cwd": bundle.cwd, "event": HookEvent.SESSION_END.value},
    )


def _last_user_text(messages: list[ConversationMessage]) -> str:
    """获取最后一条用户消息的文本。

    Args:
        messages: 会话消息列表

    Returns:
        str: 最后一条用户消息文本（如果不存在则返回空字符串）
    """
    for msg in reversed(messages):
        if msg.role == "user" and msg.text.strip():
            return msg.text.strip()
    return ""


def _truncate(text: str, limit: int) -> str:
    """截断文本到指定长度。

    Args:
        text: 要截断的文本
        limit: 最大长度

    Returns:
        str: 截断后的文本
    """
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _format_pending_tool_results(messages: list[ConversationMessage]) -> str | None:
    """在工具执行后停止时呈现紧凑摘要。

    在模型有机会响应之前呈现待处理结果的摘要。

    Args:
        messages: 会话消息列表

    Returns:
        str | None: 摘要文本（如果没有待处理结果则返回 None）
    """
    if not messages:
        return None

    last = messages[-1]
    if last.role != "user":
        return None
    tool_results = [block for block in last.content if isinstance(block, ToolResultBlock)]
    if not tool_results:
        return None

    # 构建工具使用 ID 到工具使用的映射
    tool_uses_by_id: dict[str, ToolUseBlock] = {}
    assistant_text = ""
    for msg in reversed(messages[:-1]):
        if msg.role != "assistant":
            continue
        if not msg.tool_uses:
            continue
        assistant_text = msg.text.strip()
        for tu in msg.tool_uses:
            tool_uses_by_id[tu.id] = tu
        break

    lines: list[str] = [
        "Pending continuation: tool results were produced, but the model did not get a chance to respond yet."
    ]
    if assistant_text:
        lines.append(f"Last assistant message: {_truncate(assistant_text, 400)}")

    max_results = 3
    for tr in tool_results[:max_results]:
        tu = tool_uses_by_id.get(tr.tool_use_id)
        if tu is not None:
            raw_input = json.dumps(tu.input, ensure_ascii=True, sort_keys=True)
            lines.append(
                f"- {tu.name} {_truncate(raw_input, 200)} -> {_truncate(tr.content.strip(), 400)}"
            )
        else:
            lines.append(
                f"- tool_result[{tr.tool_use_id}] -> {_truncate(tr.content.strip(), 400)}"
            )

    if len(tool_results) > max_results:
        lines.append(f"(+{len(tool_results) - max_results} more tool results)")

    lines.append("To continue from these results, run: /continue 32 (or any count).")
    return "\n".join(lines)


def sync_app_state(bundle: RuntimeBundle) -> None:
    """从当前设置和动态键绑定刷新 UI 状态。

    Args:
        bundle: 运行时数据 bundle
    """
    settings = bundle.current_settings()
    bundle.engine.set_max_turns(settings.max_turns)
    provider = detect_provider(settings)
    bundle.app_state.set(
        model=settings.model,
        permission_mode=settings.permission.mode.value,
        theme=settings.theme,
        ui_language=settings.ui_language,
        cwd=bundle.cwd,
        provider=provider.name,
        auth_status=auth_status(settings),
        base_url=settings.base_url or "",
        fast_mode=settings.fast_mode,
        effort=settings.effort,
        passes=settings.passes,
        mcp_connected=sum(1 for status in bundle.mcp_manager.list_statuses() if status.state == "connected"),
        mcp_failed=sum(1 for status in bundle.mcp_manager.list_statuses() if status.state == "failed"),
        bridge_sessions=len(get_bridge_manager().list_sessions()),
        output_style=settings.output_style,
        phase=bundle.app_state.get().phase,
    )


async def handle_line(
    bundle: RuntimeBundle,
    line: str,
    *,
    print_system: SystemPrinter,
    render_event: StreamRenderer,
    clear_output: ClearHandler,
    replay_transcript_item: TranscriptItemSender | None = None,
) -> bool:
    """处理提交的一行输入（用于无头或 TUI 渲染）。

    处理命令或用户消息，更新引擎，渲染事件，并保存会话快照。

    Args:
        bundle: 运行时数据 bundle
        line: 用户输入的行
        print_system: 系统消息打印回调
        render_event: 流式事件渲染回调
        clear_output: 清空输出回调
        replay_transcript_item: 重播 transcript_item 的回调（用于 /resume）

    Returns:
        bool: 是否继续会话
    """
    # 更新钩子注册表（如果不是外部 API 客户端）
    if not bundle.external_api_client:
        bundle.hook_executor.update_registry(
            load_hook_registry(bundle.current_settings(), bundle.current_plugins())
        )

    # 解析命令
    parsed = bundle.commands.lookup(line)
    if parsed is not None:
        command, args = parsed
        result = await command.handler(
            args,
            CommandContext(
                engine=bundle.engine,
                hooks_summary=bundle.hook_summary(),
                mcp_summary=bundle.mcp_summary(),
                plugin_summary=bundle.plugin_summary(),
                cwd=bundle.cwd,
                tool_registry=bundle.tool_registry,
                app_state=bundle.app_state,
            ),
        )
        if result.reset_session:
            bundle.session_id = uuid4().hex[:12]
            locale = str(bundle.app_state.get().ui_language or bundle.current_settings().ui_language)
            prefix = "新会话已开启，任务 ID：" if locale.lower().startswith("zh") else "Started new session. Task ID: "
            suffix = result.message or ""
            detail = f"\n{suffix}" if suffix else ""
            result.message = f"{prefix}{bundle.session_id}{detail}"
        await _render_command_result(result, print_system, clear_output, render_event, replay_transcript_item)
        if result.restored_session_id:
            bundle.session_id = result.restored_session_id
        # 处理待继续标志
        if result.continue_pending:
            settings = bundle.current_settings()
            bundle.engine.set_max_turns(settings.max_turns)
            system_prompt = build_runtime_system_prompt(
                settings,
                cwd=bundle.cwd,
                latest_user_prompt=_last_user_text(bundle.engine.messages),
            )
            bundle.engine.set_system_prompt(system_prompt)
            turns = result.continue_turns if result.continue_turns is not None else bundle.engine.max_turns
            try:
                async for event in bundle.engine.continue_pending(max_turns=turns):
                    await render_event(event)
            except MaxTurnsExceeded as exc:
                await print_system(f"Stopped after {exc.max_turns} turns (max_turns).")
                pending = _format_pending_tool_results(bundle.engine.messages)
                if pending:
                    await print_system(pending)
            # 保存会话快照
            save_session_snapshot(
                cwd=bundle.cwd,
                model=settings.model,
                system_prompt=system_prompt,
                messages=bundle.engine.messages,
                usage=bundle.engine.total_usage,
                session_id=bundle.session_id,
            )
        sync_app_state(bundle)
        return not result.should_exit

    # 处理普通用户消息
    settings = bundle.current_settings()
    bundle.engine.set_max_turns(settings.max_turns)
    system_prompt = build_runtime_system_prompt(settings, cwd=bundle.cwd, latest_user_prompt=line)
    bundle.engine.set_system_prompt(system_prompt)
    try:
        async for event in bundle.engine.submit_message(line):
            await render_event(event)
    except MaxTurnsExceeded as exc:
        await print_system(f"Stopped after {exc.max_turns} turns (max_turns).")
        pending = _format_pending_tool_results(bundle.engine.messages)
        if pending:
            await print_system(pending)
        save_session_snapshot(
            cwd=bundle.cwd,
            model=settings.model,
            system_prompt=system_prompt,
            messages=bundle.engine.messages,
            usage=bundle.engine.total_usage,
            session_id=bundle.session_id,
        )
        sync_app_state(bundle)
        return True
    # 保存会话快照
    save_session_snapshot(
        cwd=bundle.cwd,
        model=settings.model,
        system_prompt=system_prompt,
        messages=bundle.engine.messages,
        usage=bundle.engine.total_usage,
        session_id=bundle.session_id,
    )
    sync_app_state(bundle)
    return True


async def _render_command_result(
	result: CommandResult,
	print_system: SystemPrinter,
	clear_output: ClearHandler,
	render_event: StreamRenderer | None = None,
	replay_transcript_item: TranscriptItemSender | None = None,
) -> None:
	"""渲染命令执行结果。

	Args:
		result: 命令执行结果
		print_system: 系统消息打印回调
		clear_output: 清空输出回调
		render_event: 流式事件渲染回调
		replay_transcript_item: 重播 transcript_item 的回调
	"""
	if result.clear_screen:
		await clear_output()
	if result.replay_messages and render_event is not None:
		from illusion.engine.stream_events import AssistantTurnComplete
		from illusion.api.usage import UsageSnapshot
		from illusion.engine.messages import ToolUseBlock, ToolResultBlock

		await clear_output()
		tool_uses_by_id: dict[str, dict] = {}
		for msg in result.replay_messages:
			if msg.role == "user":
				if msg.text.strip():
					if replay_transcript_item is not None:
						await replay_transcript_item({"role": "user", "text": msg.text})
					else:
						await print_system(f"> {msg.text}")
				for block in msg.content:
					if isinstance(block, ToolResultBlock) and replay_transcript_item is not None:
						tool_info = tool_uses_by_id.get(block.tool_use_id, {})
						await replay_transcript_item({
							"role": "tool_result",
							"text": block.content,
							"tool_name": tool_info.get("name"),
							"is_error": block.is_error,
						})
			elif msg.role == "assistant":
				if msg.text.strip() and replay_transcript_item is not None:
					await replay_transcript_item({"role": "assistant", "text": msg.text.strip()})
				elif msg.text.strip():
					await render_event(AssistantTurnComplete(message=msg, usage=UsageSnapshot()))
				for block in msg.content:
					if isinstance(block, ToolUseBlock):
						tool_uses_by_id[block.id] = {"name": block.name, "input": block.input}
						if replay_transcript_item is not None:
							await replay_transcript_item({
								"role": "tool",
								"text": f"{block.name} {json.dumps(block.input, ensure_ascii=True)}",
								"tool_name": block.name,
								"tool_input": block.input,
							})
	if result.message and not result.replay_messages:
		await print_system(result.message)
