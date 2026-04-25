"""
React 终端后端主机模块
====================

本模块实现 JSON-lines 协议的后端主机，用于与 React 终端前端通信。

主要功能：
    - 基于 stdin/stdout 的 JSON-lines 协议通信
    - 命令处理（/provider, /resume, /permissions, /theme 等）
    - 权限确认和工作流管理
    - 会话状态快照
    - 任务管理快照
    - MCP 服务器状态管理

类说明：
    - BackendHostConfig: 后端主机配置数据类
    - ReactBackendHost: 后端主机实现类

使用示例：
    >>> from illusion.ui.backend_host import run_backend_host
    >>> await run_backend_host(model="claude-sonnet-4-20250514")
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sys
from dataclasses import dataclass
from uuid import uuid4

from illusion.api.client import SupportsStreamingMessages
from illusion.auth.manager import AuthManager
from illusion.config.settings import CLAUDE_MODEL_ALIAS_OPTIONS, display_model_setting
from illusion.bridge import get_bridge_manager
from illusion.themes import list_themes
from illusion.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ErrorEvent,
    StatusEvent,
    StreamEvent,
    ToolChainCompleted,
    ToolChainStarted,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from illusion.output_styles import load_output_styles
from illusion.tasks import get_task_manager
from illusion.ui.protocol import BackendEvent, FrontendRequest, TranscriptItem
from illusion.ui.permission_store import add_always_allowed_tool, load_always_allowed_tools
from illusion.ui.runtime import build_runtime, close_runtime, handle_line, start_runtime

# 配置模块级日志记录器
log = logging.getLogger(__name__)

# 协议前缀 - 用于标识 JSON-lines 协议
_PROTOCOL_PREFIX = "OHJSON:"


@dataclass(frozen=True)
class BackendHostConfig:
    """后端主机配置数据类。

    Attributes:
        model: 使用的模型名称
        max_turns: 最大对话轮次
        base_url: API 基础 URL
        system_prompt: 系统提示词
        api_key: API 密钥
        api_format: API 格式（copilot/openai/anthropic）
        api_client: 流式 API 客户端实例
        restore_messages: 恢复的会话消息列表
        enforce_max_turns: 是否强制限制最大轮次
    """

    model: str | None = None
    max_turns: int | None = None
    base_url: str | None = None
    system_prompt: str | None = None
    api_key: str | None = None
    api_format: str | None = None
    api_client: SupportsStreamingMessages | None = None
    restore_messages: list[dict] | None = None
    restore_session_id: str | None = None
    enforce_max_turns: bool = True


class ReactBackendHost:
    """React 终端后端主机。

    通过 JSON-lines 协议与 React 前端通信，驱动 IllusionCode 运行时。
    处理所有前端请求并发送后端事件。

    Attributes:
        _config: 后端配置
        _bundle: 运行时数据bundle
        _write_lock: 异步写入锁
        _request_queue: 请求队列
        _permission_requests: 权限请求字典（request_id -> Future）
        _question_requests: 用户问答请求字典
        _always_allowed_tools: "总是允许"的工具集合
        _busy: 当前是否正在处理请求
        _running: 是否正在运行
        _active_line_task: 当前活动的行处理任务
        _last_tool_inputs: 每个工具名称的最后输入（用于富事件发射）
    """

    def __init__(self, config: BackendHostConfig) -> None:
        self._config = config
        self._bundle = None
        self._write_lock = asyncio.Lock()  # 异步写入锁
        self._request_queue: asyncio.Queue[FrontendRequest] = asyncio.Queue()
        self._permission_requests: dict[str, asyncio.Future[bool]] = {}  # 权限请求
        self._question_requests: dict[str, asyncio.Future[str]] = {}      # 用户问答
        self._always_allowed_tools: set[str] = set()                # 总是允许的工具
        self._busy = False            # 忙碌状态
        self._running = True           # 运行状态
        self._active_line_task: asyncio.Task[bool] | None = None    # 当前任务
        # 跟踪每个工具名称的最后输入，用于富事件发射
        self._last_tool_inputs: dict[str, dict] = {}

    async def run(self) -> int:
        """运行后端主机主循环。"""
        # 构建运行时环境
        self._bundle = await build_runtime(
            model=self._config.model,
            max_turns=self._config.max_turns,
            base_url=self._config.base_url,
            system_prompt=self._config.system_prompt,
            api_key=self._config.api_key,
            api_format=self._config.api_format,
            api_client=self._config.api_client,
            restore_messages=self._config.restore_messages,
            restore_session_id=self._config.restore_session_id,
            permission_prompt=self._ask_permission,
            ask_user_prompt=self._ask_question,
        )
        await start_runtime(self._bundle)
        # 加载总是允许的工具列表
        self._always_allowed_tools = load_always_allowed_tools(self._bundle.cwd)
        # 发送就绪事件
        await self._emit(
            BackendEvent.ready(
                self._bundle.app_state.get(),
                get_task_manager().list_tasks(),
                [f"/{command.name}" for command in self._bundle.commands.list_commands()],
            )
        )
        # 发送状态快照
        await self._emit(self._status_snapshot())

        # 创建请求读取任务
        reader = asyncio.create_task(self._read_requests())
        try:
            # 主循环：处理请求
            while self._running:
                request = await self._request_queue.get()
                # 关闭请求
                if request.type == "shutdown":
                    await self._emit(BackendEvent(type="shutdown"))
                    break
                # 停止当前任务
                if request.type == "stop":
                    await self._stop_active_line()
                    continue
                # 权限响应
                if request.type == "permission_response":
                    if request.request_id in self._permission_requests:
                        self._permission_requests[request.request_id].set_result(bool(request.allowed))
                    # 记住"总是允许"工具
                    if request.always_allow and request.tool_name:
                        self._always_allowed_tools.add(request.tool_name)
                        if self._bundle is not None:
                            self._always_allowed_tools = add_always_allowed_tool(
                                self._bundle.cwd,
                                request.tool_name,
                            )
                    await self._emit(BackendEvent(type="modal_request", modal=None))
                    continue
                # 用户问答响应
                if request.type == "question_response":
                    if request.request_id in self._question_requests:
                        self._question_requests[request.request_id].set_result(request.answer or "")
                    await self._emit(BackendEvent(type="modal_request", modal=None))
                    continue
                # 列出会话
                if request.type == "list_sessions":
                    await self._handle_list_sessions()
                    continue
                # 选择命令
                if request.type == "select_command":
                    await self._handle_select_command(request.command or "")
                    continue
                # 应用选择命令
                if request.type == "apply_select_command":
                    if self._busy:
                        await self._emit(BackendEvent(type="error", message="Session is busy"))
                        continue
                    self._busy = True
                    try:
                        self._active_line_task = asyncio.create_task(
                            self._apply_select_command(
                                request.command or "",
                                request.value or "",
                            )
                        )
                        should_continue = await self._active_line_task
                    except asyncio.CancelledError:
                        should_continue = True
                    finally:
                        self._active_line_task = None
                        self._busy = False
                    if not should_continue:
                        await self._emit(BackendEvent(type="shutdown"))
                        break
                    continue
                # 未知请求类型
                if request.type != "submit_line":
                    await self._emit(BackendEvent(type="error", message=f"Unknown request type: {request.type}"))
                    continue
                # 忙碌中
                if self._busy:
                    await self._emit(BackendEvent(type="error", message="Session is busy"))
                    continue
                # 处理提交的行
                line = (request.line or "").strip()
                if not line:
                    continue
                self._busy = True
                try:
                    self._active_line_task = asyncio.create_task(self._process_line(line))
                    should_continue = await self._active_line_task
                except asyncio.CancelledError:
                    should_continue = True
                finally:
                    self._active_line_task = None
                    self._busy = False
                if not should_continue:
                    await self._emit(BackendEvent(type="shutdown"))
                    break
        finally:
            # 清理资源
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader
            if self._bundle is not None:
                await close_runtime(self._bundle)
        return 0
    async def _read_requests(self) -> None:
        """从 stdin 读取请求。"""
        while True:
            raw = await asyncio.to_thread(sys.stdin.buffer.readline)
            if not raw:
                await self._request_queue.put(FrontendRequest(type="shutdown"))
                return
            payload = raw.decode("utf-8").strip()
            if not payload:
                continue
            try:
                request = FrontendRequest.model_validate_json(payload)
            except Exception as exc:  # 防御性协议处理
                await self._emit(BackendEvent(type="error", message=f"Invalid request: {exc}"))
                continue

            # 立即解析模态对话框交互以避免死锁
            # 主循环在 _process_line() 中等待用户输入
            if request.type == "permission_response":
                if request.request_id in self._permission_requests:
                    self._permission_requests[request.request_id].set_result(bool(request.allowed))
                if request.always_allow and request.tool_name:
                    self._always_allowed_tools.add(request.tool_name)
                    if self._bundle is not None:
                        self._always_allowed_tools = add_always_allowed_tool(
                            self._bundle.cwd,
                            request.tool_name,
                        )
                await self._emit(BackendEvent(type="modal_request", modal=None))
                continue
            if request.type == "stop":
                await self._stop_active_line()
                continue
            if request.type == "question_response":
                if request.request_id in self._question_requests:
                    self._question_requests[request.request_id].set_result(request.answer or "")
                await self._emit(BackendEvent(type="modal_request", modal=None))
                continue

            await self._request_queue.put(request)

    async def _process_line(self, line: str, *, transcript_line: str | None = None) -> bool:
        """处理用户输入的行内容。"""
        assert self._bundle is not None
        # 更新会话阶段为思考中
        await self._update_phase("thinking")
        # 发送用户消息
        await self._emit(
            BackendEvent(type="transcript_item", item=TranscriptItem(role="user", text=transcript_line or line))
        )

        async def _print_system(message: str) -> None:
            """打印系统消息。"""
            await self._emit(
                BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text=message))
            )

        async def _render_event(event: StreamEvent) -> None:
            """渲染流式事件。"""
            # 助手文本增量
            if isinstance(event, AssistantTextDelta):
                reasoning = getattr(event, "reasoning", None)
                await self._emit(BackendEvent(
                    type="assistant_delta",
                    message=event.text,
                    reasoning=reasoning if reasoning else None,
                ))
                return
            # 助手回合完成
            if isinstance(event, AssistantTurnComplete):
                reasoning = getattr(event.message, "_reasoning", None)
                await self._emit(
                    BackendEvent(
                        type="assistant_complete",
                        message=event.message.text.strip(),
                        reasoning=reasoning if reasoning else None,
                        item=TranscriptItem(role="assistant", text=event.message.text.strip()),
                    )
                )
                await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
                return
            # 工具链开始
            if isinstance(event, ToolChainStarted):
                await self._update_phase("tool_executing")
                await self._emit(
                    BackendEvent(
                        type="tool_chain_started",
                        tool_count=event.tool_count,
                    )
                )
                return
            # 工具链完成
            if isinstance(event, ToolChainCompleted):
                await self._update_phase("thinking")
                await self._emit(
                    BackendEvent(
                        type="tool_chain_completed",
                        phase="thinking",
                    )
                )
                return
            # 工具开始执行
            if isinstance(event, ToolExecutionStarted):
                self._last_tool_inputs[event.tool_name] = event.tool_input or {}
                await self._emit(
                    BackendEvent(
                        type="tool_started",
                        tool_name=event.tool_name,
                        tool_input=event.tool_input,
                        item=TranscriptItem(
                            role="tool",
                            text=f"{event.tool_name} {json.dumps(event.tool_input, ensure_ascii=True)}",
                            tool_name=event.tool_name,
                            tool_input=event.tool_input,
                        ),
                    )
                )
                return
            # 工具执行完成
            if isinstance(event, ToolExecutionCompleted):
                await self._emit(
                    BackendEvent(
                        type="tool_completed",
                        tool_name=event.tool_name,
                        output=event.output,
                        is_error=event.is_error,
                        item=TranscriptItem(
                            role="tool_result",
                            text=event.output,
                            tool_name=event.tool_name,
                            is_error=event.is_error,
                        ),
                    )
                )
                await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
                await self._emit(self._status_snapshot())
                # TodoWrite 工具执行时发送 todo_update 事件
                if event.tool_name in ("TodoWrite", "todo_write"):
                    tool_input = self._last_tool_inputs.get(event.tool_name, {})
                    todos = tool_input.get("todos") or []
                    if isinstance(todos, list):
                        todo_items = []
                        for item in todos:
                            if isinstance(item, dict):
                                todo_items.append({
                                    "content": item.get("content", ""),
                                    "status": item.get("status", "pending"),
                                    "activeForm": item.get("activeForm", item.get("content", "")),
                                })
                        if all(t.get("status") == "completed" for t in todo_items) and len(todo_items) >= 1:
                            todo_items = []
                        await self._emit(BackendEvent(type="todo_update", todo_items=todo_items))
                # 计划相关工具完成时发送 plan_mode_change 事件
                if event.tool_name in ("set_permission_mode", "plan_mode"):
                    assert self._bundle is not None
                    new_mode = self._bundle.app_state.get().permission_mode
                    await self._emit(BackendEvent(type="plan_mode_change", plan_mode=new_mode))
                return
            # 错误事件
            if isinstance(event, ErrorEvent):
                await self._emit(BackendEvent(type="error", message=event.message))
                await self._emit(
                    BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text=event.message))
                )
                return
            # 状态事件
            if isinstance(event, StatusEvent):
                await self._emit(
                    BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text=event.message))
                )
                return

        async def _replay_transcript_item(item: dict) -> None:
            """重播 transcript_item。"""
            await self._emit(BackendEvent(type="transcript_item", item=TranscriptItem(**item)))

        async def _clear_output() -> None:
            """清空输出。"""
            await self._emit(BackendEvent(type="clear_transcript"))

        should_continue = await handle_line(
            self._bundle,
            line,
            print_system=_print_system,
            render_event=_render_event,
            clear_output=_clear_output,
            replay_transcript_item=_replay_transcript_item,
        )

        # 更新会话阶段为空闲
        await self._update_phase("idle")
        await self._emit(self._status_snapshot())
        await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
        await self._emit(BackendEvent(type="line_complete"))
        return should_continue

    async def _apply_select_command(self, command_name: str, value: str) -> bool:
        """应用选择的命令值。"""
        command = command_name.strip().lstrip("/").lower()
        selected = value.strip()
        line = self._build_select_command_line(command, selected)
        if line is None:
            await self._emit(BackendEvent(type="error", message=f"Unknown select command: {command_name}"))
            await self._emit(BackendEvent(type="line_complete"))
            return True
        return await self._process_line(line, transcript_line=f"/{command}")

    def _build_select_command_line(self, command: str, value: str) -> str | None:
        """构建选择命令的实际命令字符串。"""
        if command == "provider":
            return f"/provider {value}"
        if command == "resume":
            return f"/resume {value}" if value else "/resume"
        if command == "permissions":
            return f"/permissions {value}"
        if command == "theme":
            return f"/theme {value}"
        if command == "language":
            return f"/language {value}"
        if command == "output-style":
            return f"/output-style {value}"
        if command == "effort":
            return f"/effort {value}"
        if command == "passes":
            return f"/passes {value}"
        if command == "turns":
            return f"/turns {value}"
        if command == "fast":
            return f"/fast {value}"
        if command == "language":
            return f"/language {value}"
        if command == "model":
            return f"/model {value}"
        return None

    def _status_snapshot(self) -> BackendEvent:
        """生成状态快照事件。"""
        assert self._bundle is not None
        return BackendEvent.status_snapshot(
            state=self._bundle.app_state.get(),
            mcp_servers=self._bundle.mcp_manager.list_statuses(),
            bridge_sessions=get_bridge_manager().list_sessions(),
        )

    async def _emit_todo_update_from_output(self, output: str) -> None:
        """从工具输出中提取 markdown 复选框并发送 todo_update 事件。"""
        # TodoWrite 工具通常会回显写入的内容
        # 我们查找 markdown 复选框模式
        lines = output.splitlines()
        checklist_lines = [line for line in lines if line.strip().startswith("- [")]
        if checklist_lines:
            markdown = "\n".join(checklist_lines)
            await self._emit(BackendEvent(type="todo_update", todo_markdown=markdown))

    def _emit_swarm_status(self, teammates: list[dict], notifications: list[dict] | None = None) -> None:
        """同步发送 swarm_status 事件（调度为协程）。"""
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(
            self._emit(BackendEvent(type="swarm_status", swarm_teammates=teammates, swarm_notifications=notifications))
        )

    async def _handle_list_sessions(self) -> None:
        """处理列出会话请求。"""
        from illusion.services.session_storage import list_session_snapshots
        import time as _time

        assert self._bundle is not None
        locale = str(self._bundle.app_state.get().ui_language or self._bundle.current_settings().ui_language)
        zh = locale.lower().startswith("zh")
        sessions = list_session_snapshots(self._bundle.cwd, limit=10)
        options = []
        for s in sessions:
            ts = _time.strftime("%m/%d %H:%M", _time.localtime(s["created_at"]))
            summary = s.get("summary", "")[:50] or ("（无摘要）" if zh else "(no summary)")
            options.append({
                "value": s["session_id"],
                "label": f"{ts}  {s['message_count']}msg  {summary}",
            })
        await self._emit(
            BackendEvent(
                type="select_request",
                modal={"kind": "select", "title": "恢复会话" if zh else "Resume Session", "command": "resume"},
                select_options=options,
            )
        )

    async def _handle_select_command(self, command_name: str) -> None:
        """处理选择命令请求。"""
        assert self._bundle is not None
        command = command_name.strip().lstrip("/").lower()
        if command == "resume":
            await self._handle_list_sessions()
            return

        settings = self._bundle.current_settings()
        state = self._bundle.app_state.get()
        locale = str(state.ui_language or settings.ui_language)
        zh = locale.lower().startswith("zh")
        _, active_profile = settings.resolve_profile()
        current_model = display_model_setting(active_profile)

        if command == "provider":
            statuses = AuthManager(settings).get_profile_statuses()
            options = [
                {
                    "value": name,
                    "label": info["label"],
                    "description": f"{info['provider']} / {info['auth_source']}" + (" [missing auth]" if not info["configured"] else ""),
                    "active": info["active"],
                }
                for name, info in statuses.items()
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "提供商配置" if zh else "Provider Profile", "command": "provider"},
                    select_options=options,
                )
            )
            return

        if command == "permissions":
            options = [
                {
                    "value": "default",
                    "label": "默认" if zh else "Default",
                    "description": "写入/执行前询问" if zh else "Ask before write/execute operations",
                    "active": settings.permission.mode.value == "default",
                },
                {
                    "value": "full_auto",
                    "label": "自动" if zh else "Auto",
                    "description": "自动允许所有工具" if zh else "Allow all tools automatically",
                    "active": settings.permission.mode.value == "full_auto",
                },
                {
                    "value": "plan",
                    "label": "计划模式" if zh else "Plan Mode",
                    "description": "阻止所有写入操作" if zh else "Block all write operations",
                    "active": settings.permission.mode.value == "plan",
                },
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "权限模式" if zh else "Permission Mode", "command": "permissions"},
                    select_options=options,
                )
            )
            return

        if command == "theme":
            options = [
                {
                    "value": name,
                    "label": name,
                    "active": name == settings.theme,
                }
                for name in list_themes()
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "主题" if zh else "Theme", "command": "theme"},
                    select_options=options,
                )
            )
            return

        if command == "output-style":
            options = [
                {
                    "value": style.name,
                    "label": style.name,
                    "description": style.source,
                    "active": style.name == settings.output_style,
                }
                for style in load_output_styles()
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "输出风格" if zh else "Output Style", "command": "output-style"},
                    select_options=options,
                )
            )
            return

        if command == "effort":
            options = [
                {"value": "low", "label": "低" if zh else "Low", "description": "最快响应" if zh else "Fastest responses", "active": settings.effort == "low"},
                {"value": "medium", "label": "中" if zh else "Medium", "description": "平衡推理" if zh else "Balanced reasoning", "active": settings.effort == "medium"},
                {"value": "high", "label": "高" if zh else "High", "description": "最深推理" if zh else "Deepest reasoning", "active": settings.effort == "high"},
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "推理强度" if zh else "Reasoning Effort", "command": "effort"},
                    select_options=options,
                )
            )
            return

        if command == "passes":
            current = int(state.passes or settings.passes)
            options = [
                {"value": str(value), "label": (f"{value} 轮" if zh else f"{value} pass{'es' if value != 1 else ''}"), "active": value == current}
                for value in range(1, 9)
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "推理轮数" if zh else "Reasoning Passes", "command": "passes"},
                    select_options=options,
                )
            )
            return

        if command == "turns":
            current = self._bundle.engine.max_turns
            values = {32, 64, 128, 200, 256, 512}
            if isinstance(current, int):
                values.add(current)
            options = [{"value": "unlimited", "label": "无限" if zh else "Unlimited", "description": "不对本会话硬性停止" if zh else "Do not hard-stop this session", "active": current is None}]
            options.extend(
                {"value": str(value), "label": (f"{value} 轮" if zh else f"{value} turns"), "active": value == current}
                for value in sorted(values)
            )
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "最大轮数" if zh else "Max Turns", "command": "turns"},
                    select_options=options,
                )
            )
            return

        if command == "fast":
            current = bool(state.fast_mode)
            options = [
                {"value": "on", "label": "开" if zh else "On", "description": "偏向更短更快的响应" if zh else "Prefer shorter, faster responses", "active": current},
                {"value": "off", "label": "关" if zh else "Off", "description": "使用常规响应模式" if zh else "Use normal response mode", "active": not current},
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "快速模式" if zh else "Fast Mode", "command": "fast"},
                    select_options=options,
                )
            )
            return

        if command == "language":
            current = str(state.ui_language or "zh-CN")
            options = [
                {"value": "set zh-CN", "label": "简体中文", "description": "中文界面", "active": current == "zh-CN"},
                {"value": "set en", "label": "English", "description": "English UI", "active": current == "en"},
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "语言" if zh else "Language", "command": "language"},
                    select_options=options,
                )
            )
            return

        if command == "language":
            current = str(state.ui_language or "zh-CN")
            options = [
                {"value": "set zh-CN", "label": "简体中文", "description": "中文界面", "active": current == "zh-CN"},
                {"value": "set en", "label": "English", "description": "English UI", "active": current == "en"},
            ]
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "语言" if zh else "Language", "command": "language"},
                    select_options=options,
                )
            )
            return

        if command == "model":
            options = self._model_select_options(current_model, active_profile.provider)
            await self._emit(
                BackendEvent(
                    type="select_request",
                    modal={"kind": "select", "title": "模型" if zh else "Model", "command": "model"},
                    select_options=options,
                )
            )
            return

        await self._emit(BackendEvent(type="error", message=(f"/{command} 暂无可选项" if zh else f"No selector available for /{command}")))

    def _model_select_options(self, current_model: str, provider: str) -> list[dict[str, object]]:
        """生成模型选择选项列表。"""
        provider_name = provider.lower()
        if provider_name in {"anthropic", "anthropic_claude"}:
            return [
                {
                    "value": value,
                    "label": label,
                    "description": description,
                    "active": value == current_model,
                }
                for value, label, description in CLAUDE_MODEL_ALIAS_OPTIONS
            ]
        families: list[tuple[str, str]] = []
        if provider_name in {"openai-codex", "openai", "openai-compatible", "openrouter", "github_copilot"}:
            families.extend(
                [
                    ("gpt-5.4", "OpenAI flagship"),
                    ("gpt-5", "General GPT-5"),
                    ("gpt-4.1", "Stable GPT-4.1"),
                    ("o4-mini", "Fast reasoning"),
                ]
            )
        elif provider_name in {"moonshot", "moonshot-compatible"}:
            families.extend(
                [
                    ("kimi-k2.5", "Moonshot K2.5"),
                    ("kimi-k2-turbo-preview", "Faster Moonshot"),
                ]
            )
        elif provider_name == "dashscope":
            families.extend(
                [
                    ("qwen3.5-flash", "Fast Qwen"),
                    ("qwen3-max", "Strong Qwen"),
                    ("deepseek-r1", "Reasoning model"),
                ]
            )
        elif provider_name == "gemini":
            families.extend(
                [
                    ("gemini-2.5-pro", "Gemini Pro"),
                    ("gemini-2.5-flash", "Gemini Flash"),
                ]
            )

        seen: set[str] = set()
        options: list[dict[str, object]] = []
        for value, description in [(current_model, "Current model"), *families]:
            if not value or value in seen:
                continue
            seen.add(value)
            options.append(
                {
                    "value": value,
                    "label": value,
                    "description": description,
                    "active": value == current_model,
                }
            )
        return options

    async def _ask_permission(self, tool_name: str, reason: str) -> bool:
        # 如果工具在"总是允许"列表中，则直接允许
        if tool_name in self._always_allowed_tools:
            return True
        request_id = uuid4().hex
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._permission_requests[request_id] = future
        await self._emit(
            BackendEvent(
                type="modal_request",
                modal={
                    "kind": "permission",
                    "request_id": request_id,
                    "tool_name": tool_name,
                    "reason": reason,
                },
            )
        )
        try:
            return await asyncio.wait_for(future, timeout=300)
        except asyncio.TimeoutError:
            log.warning("Permission request %s timed out after 300s, denying", request_id)
            return False
        finally:
            self._permission_requests.pop(request_id, None)

    async def _ask_question(self, question: str) -> str:
        request_id = uuid4().hex
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._question_requests[request_id] = future
        tool_input = self._last_tool_inputs.get("ask_user_question", {})
        questions_data = tool_input.get("questions")
        modal_payload: dict = {
            "kind": "question",
            "request_id": request_id,
            "question": question,
        }
        if questions_data:
            modal_payload["questions"] = questions_data
        await self._emit(
            BackendEvent(
                type="modal_request",
                modal=modal_payload,
            )
        )
        try:
            return await future
        finally:
            self._question_requests.pop(request_id, None)

    async def _stop_active_line(self) -> None:
        task = self._active_line_task
        if task is None or task.done():
            await self._emit(BackendEvent(type="error", message="No active task to stop"))
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        self._busy = False
        await self._update_phase("idle")
        await self._emit(BackendEvent(type="modal_request", modal=None))
        await self._emit(BackendEvent(type="transcript_item", item=TranscriptItem(role="system", text="Current task stopped.")))
        await self._emit(self._status_snapshot())
        await self._emit(BackendEvent.tasks_snapshot(get_task_manager().list_tasks()))
        await self._emit(BackendEvent(type="line_complete"))

    async def _update_phase(self, phase: str) -> None:
        """更新会话阶段。"""
        assert self._bundle is not None
        self._bundle.app_state.set(phase=phase)

    async def _emit(self, event: BackendEvent) -> None:
        async with self._write_lock:
            payload = _PROTOCOL_PREFIX + event.model_dump_json() + "\n"
            buffer = getattr(sys.stdout, "buffer", None)
            if buffer is not None:
                buffer.write(payload.encode("utf-8"))
                buffer.flush()
                return
            sys.stdout.write(payload)
            sys.stdout.flush()


async def run_backend_host(
    *,
    model: str | None = None,
    max_turns: int | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
    api_key: str | None = None,
    api_format: str | None = None,
    cwd: str | None = None,
    api_client: SupportsStreamingMessages | None = None,
    restore_messages: list[dict] | None = None,
    restore_session_id: str | None = None,
    enforce_max_turns: bool = True,
) -> int:
    """Run the structured React backend host."""
    if cwd:
        os.chdir(cwd)
    host = ReactBackendHost(
        BackendHostConfig(
            model=model,
            max_turns=max_turns,
            base_url=base_url,
            system_prompt=system_prompt,
            api_key=api_key,
            api_format=api_format,
            api_client=api_client,
            restore_messages=restore_messages,
            restore_session_id=restore_session_id,
            enforce_max_turns=enforce_max_turns,
        )
    )
    return await host.run()


__all__ = ["run_backend_host", "ReactBackendHost", "BackendHostConfig"]
