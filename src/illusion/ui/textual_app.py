"""
Textual 终端 UI 模块
==================

本模块实现基于 Textual 框架的默认终端用户界面。

主要功能：
    - 交互式对话界面（Transcript 显示对话历史）
    - 实时流式输出（Assistant 输出流式显示）
    - 工具执行状态显示
    - 侧边栏（状态、任务、MCP 服务器信息）
    - 权限确认对话框（PermissionScreen）
    - 用户问答对话框（QuestionScreen）

类说明：
    - AppConfig: 终端应用配置数据类
    - PermissionScreen: 权限确认模态对话框
    - QuestionScreen: 用户问答模态对话框
    - illusionTerminalApp: 主终端应用类

使用示例：
    >>> from illusion.ui.textual_app import illusionTerminalApp
    >>> app = illusionTerminalApp()
    >>> app.run()
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from rich.panel import Panel
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, RichLog, Static

from illusion.api.client import SupportsStreamingMessages
from illusion.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ErrorEvent,
    StatusEvent,
    StreamEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from illusion.tasks import get_task_manager
from illusion.ui.runtime import build_runtime, close_runtime, handle_line, start_runtime


@dataclass(frozen=True)
class AppConfig:
    """终端应用配置数据类。

    用于存储终端应用会话的配置参数。

    Attributes:
        prompt: 初始用户提示词
        model: 使用的模型名称
        base_url: API 基础 URL
        system_prompt: 系统提示词
        api_key: API 密钥
        api_client: 流式 API 客户端实例
    """

    prompt: str | None = None
    model: str | None = None
    base_url: str | None = None
    system_prompt: str | None = None
    api_key: str | None = None
    api_client: SupportsStreamingMessages | None = None


class PermissionScreen(ModalScreen[bool]):
    """权限确认模态对话框。

    当工具需要用户确认时显示此对话框，让用户决定是否允许执行该工具。
    支持快捷键：Y=允许，N=拒绝，Escape=拒绝。

    Attributes:
        _tool_name: 请求执行的工具名称
        _reason: 工具请求的原因说明
    """

    BINDINGS = [
        Binding("escape", "deny", "Deny"),
        Binding("y", "allow", "Allow"),
        Binding("n", "deny", "Deny"),
    ]

    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__()
        self._tool_name = tool_name  # 存储工具名称
        self._reason = reason    # 存储原因说明

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                Panel.fit(
                    f"Allow tool [bold]{self._tool_name}[/bold]?\n\n{self._reason}",
                    title="Permission Required",
                )
            ),
            Horizontal(
                Button("Allow", id="allow", variant="success"),
                Button("Deny", id="deny", variant="error"),
                classes="permission-actions",
            ),
            id="permission-dialog",
        )

    @on(Button.Pressed)
    def handle_button_press(self, event: Button.Pressed) -> None:
        # 根据按钮ID决定是否允许：allow=True, deny=False
        self.dismiss(event.button.id == "allow")

    def action_allow(self) -> None:
        self.dismiss(True)  # 允许执行

    def action_deny(self) -> None:
        self.dismiss(False)  # 拒绝执行


class QuestionScreen(ModalScreen[str]):
    """用户问答模态对话框。

    在工具执行过程中提示用户输入简短答案。
    支持快捷键：Enter=提交，Escape=取消。

    Attributes:
        _question: 要询问用户的问题
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "submit", "Submit"),
    ]

    def __init__(self, question: str) -> None:
        super().__init__()
        self._question = question  # 存储问题内容

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                Panel.fit(
                    self._question,
                    title="Question",
                )
            ),
            Input(placeholder="Type your answer", id="question-input"),
            Horizontal(
                Button("Submit", id="submit", variant="primary"),
                Button("Cancel", id="cancel", variant="default"),
                classes="permission-actions",
            ),
            id="permission-dialog",
        )

    def on_mount(self) -> None:
        # 挂载时自动聚焦输入框
        self.query_one("#question-input", Input).focus()

    @on(Button.Pressed)
    def handle_button_press(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self.dismiss(self.query_one("#question-input", Input).value.strip())
            return
        self.dismiss("")  # 取消时返回空字符串

    @on(Input.Submitted, "#question-input")
    def handle_submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())

    def action_submit(self) -> None:
        self.dismiss(self.query_one("#question-input", Input).value.strip())

    def action_cancel(self) -> None:
        self.dismiss("")


class illusionTerminalApp(App[None]):
    """Textual 终端应用程序主类。

    提供基于 Textual 框架的交互式终端用户界面。
    支持快捷键：Ctrl+L 清空对话，Ctrl+R 刷新侧边栏，Ctrl+D 退出。

    Attributes:
        _config: 应用配置参数
        _bundle: 运行时数据bundle
        _assistant_buffer: 助手输出缓冲区（用于流式输出）
        _busy: 当前是否正在处理请求
        transcript_lines: 对话历史记录列表
    """

    # CSS 样式定义 - 终端布局
    CSS = """
    Screen {
        layout: vertical;
    }

    #main-row {
        height: 1fr;
    }

    #transcript-column {
        width: 3fr;
        min-width: 60;
    }

    #side-column {
        width: 1fr;
        min-width: 28;
    }

    #transcript {
        height: 1fr;
        border: solid $accent;
    }

    #current-response {
        min-height: 3;
        max-height: 8;
        border: round $primary;
        padding: 0 1;
    }

    #composer {
        dock: bottom;
        height: 3;
        border: solid $accent;
    }

    #status-bar, #tasks-panel, #mcp-panel {
        border: round $surface;
        padding: 0 1;
        margin-bottom: 1;
    }

    #permission-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $panel;
        border: round $accent;
    }

    .permission-actions {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    """

    # 快捷键绑定
    BINDINGS = [
        Binding("ctrl+l", "clear_conversation", "Clear"),       # 清空对话
        Binding("ctrl+r", "refresh_sidebars", "Refresh"),         # 刷新侧边栏
        Binding("ctrl+d", "quit_session", "Exit"),                # 退出会话
    ]

    def __init__(
        self,
        *,
        prompt: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        system_prompt: str | None = None,
        api_key: str | None = None,
        api_client: SupportsStreamingMessages | None = None,
    ) -> None:
        super().__init__()
        # 初始化应用配置
        self._config = AppConfig(
            prompt=prompt,
            model=model,
            base_url=base_url,
            system_prompt=system_prompt,
            api_key=api_key,
            api_client=api_client,
        )
        self._bundle = None                   # 运行时数据bundle
        self._assistant_buffer = ""           # 助手输出缓冲区
        self._busy = False                  # 当前是否正在处理请求
        self.transcript_lines: list[str] = []  # 对话历史

    def compose(self) -> ComposeResult:
        """构建界面布局。"""
        yield Header(show_clock=True)  # 显示时钟的标题栏
        with Horizontal(id="main-row"):
            with Vertical(id="transcript-column"):
                # 对话历史显示区域
                yield RichLog(id="transcript", wrap=True, highlight=True, markup=True)
                # 当前响应显示区域
                yield Static("Ready.", id="current-response")
                # 用户输入框
                yield Input(placeholder="Ask illusion or enter a /command", id="composer")
            with Vertical(id="side-column"):
                # 状态栏
                yield Static("Starting...", id="status-bar")
                # 任务面板
                yield Static("No tasks yet.", id="tasks-panel")
                # MCP 服务器面板
                yield Static("No MCP servers configured.", id="mcp-panel")
        yield Footer()

    async def on_mount(self) -> None:
        """应用挂载时初始化运行时。"""
        # 构建运行时环境
        self._bundle = await build_runtime(
            prompt=self._config.prompt,
            model=self._config.model,
            base_url=self._config.base_url,
            system_prompt=self._config.system_prompt,
            api_key=self._config.api_key,
            api_client=self._config.api_client,
            permission_prompt=self._ask_permission,
            ask_user_prompt=self._ask_question,
        )
        await start_runtime(self._bundle)  # 启动运行时（执行会话开始钩子）
        # 聚焦输入框
        self.query_one("#composer", Input).focus()
        # 刷新侧边栏
        self._refresh_sidebars()
        # 设置定时刷新侧边栏（每秒）
        self.set_interval(1.0, self._refresh_sidebars)
        # 如果有初始提示词，自动执行
        if self._config.prompt:
            self.call_later(lambda: asyncio.create_task(self._process_line(self._config.prompt or "")))

    async def on_unmount(self) -> None:
        """应用卸载时清理资源。"""
        if self._bundle is not None:
            await close_runtime(self._bundle)

    async def _ask_permission(self, tool_name: str, reason: str) -> bool:
        """权限确认回调函数。"""
        return bool(await self._open_modal(PermissionScreen(tool_name, reason)))

    async def _ask_question(self, question: str) -> str:
        """用户问答回调函数。"""
        return str(await self._open_modal(QuestionScreen(question)) or "")

    async def _open_modal(self, screen: ModalScreen) -> object:
        """打开模态对话框并等待用户响应。"""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[object] = loop.create_future()

        def _done(result: object) -> None:
            if not future.done():
                future.set_result(result)

        self.push_screen(screen, callback=_done)
        return await future

    @on(Input.Submitted, "#composer")
    async def handle_submit(self, event: Input.Submitted) -> None:
        """处理用户提交输入事件。"""
        event.input.value = ""
        await self._process_line(event.value)

    async def _process_line(self, line: str) -> None:
        """处理用户输入的行内容。"""
        # 空行或无运行时则忽略
        if not line.strip() or self._bundle is None or self._busy:
            return
        self._busy = True  # 设置忙碌状态
        # 获取并禁用输入框
        composer = self.query_one("#composer", Input)
        composer.disabled = True
        # 添加用户输入到对话历史
        self._append_line(f"user> {line}")
        self._set_current_response("[dim]Working...[/dim]")
        try:
            # 处理输入行
            should_continue = await handle_line(
                self._bundle,
                line,
                print_system=self._print_system,
                render_event=self._render_event,
                clear_output=self._clear_transcript,
            )
            self._refresh_sidebars()
            # 如果会话结束则退出
            if not should_continue:
                self.exit()
        finally:
            self._busy = False
            composer.disabled = False
            composer.focus()

    async def _print_system(self, message: str) -> None:
        """打印系统消息。"""
        self._append_line(f"system> {message}")
        self._set_current_response("Ready.")

    async def _render_event(self, event: StreamEvent) -> None:
        """渲染流式事件。"""
        # 助手文本增量事件
        if isinstance(event, AssistantTextDelta):
            self._assistant_buffer += event.text
            self._set_current_response(f"[bold]assistant>[/bold] {self._assistant_buffer}")
            return

        # 助手回合完成事件
        if isinstance(event, AssistantTurnComplete):
            text = self._assistant_buffer or event.message.text or "(empty response)"
            self._append_line(f"assistant> {text}")
            self._assistant_buffer = ""
            self._set_current_response("Ready.")
            return

        # 工具开始执行事件
        if isinstance(event, ToolExecutionStarted):
            payload = json.dumps(event.tool_input, ensure_ascii=False)
            self._append_line(f"tool> {event.tool_name} {payload}")
            return

        # 工具执行完成事件
        if isinstance(event, ToolExecutionCompleted):
            prefix = "tool-error>" if event.is_error else "tool-result>"
            self._append_line(f"{prefix} {event.tool_name}: {event.output}")
            return

        # 错误事件
        if isinstance(event, ErrorEvent):
            self._append_line(f"error> {event.message}")
            self._assistant_buffer = ""
            self._set_current_response("Ready.")
            return
        # 状态事件
        if isinstance(event, StatusEvent):
            self._append_line(f"system> {event.message}")

    def action_clear_conversation(self) -> None:
        """清空对话历史。"""
        if self._bundle is None:
            return
        self._bundle.engine.clear()  # 清空引擎对话历史
        # 清空界面显示
        self.query_one("#transcript", RichLog).clear()
        self.transcript_lines.clear()
        self._set_current_response("Conversation cleared.")
        self._refresh_sidebars()

    def action_refresh_sidebars(self) -> None:
        """刷新侧边栏显示。"""
        self._refresh_sidebars()

    def action_quit_session(self) -> None:
        """退出当前会话。"""
        self.exit()

    def _append_line(self, message: str) -> None:
        """添加一行到对话历史。"""
        self.transcript_lines.append(message)
        self.query_one("#transcript", RichLog).write(message)

    async def _clear_transcript(self) -> None:
        """清空对话显示区域。"""
        self.query_one("#transcript", RichLog).clear()
        self.transcript_lines.clear()

    def _set_current_response(self, message: str) -> None:
        """设置当前响应显示。"""
        self.query_one("#current-response", Static).update(message)

    def _refresh_sidebars(self) -> None:
        """刷新侧边栏信息。"""
        if self._bundle is None:
            return
        # 获取状态信息
        state = self._bundle.app_state.get()
        usage = self._bundle.engine.total_usage
        # 状态栏信息
        status_lines = [
            "[b]Status[/b]",
            f"model: {state.model}",
            f"permissions: {state.permission_mode}",
            f"fast: {'on' if state.fast_mode else 'off'}",
            f"language: {state.ui_language}",
            f"style: {state.output_style}",
            f"tokens: {usage.total_tokens}",
            f"messages: {len(self._bundle.engine.messages)}",
        ]
        self.query_one("#status-bar", Static).update("\n".join(status_lines))

        # 获取任务列表
        tasks = get_task_manager().list_tasks()
        if tasks:
            task_lines = ["[b]Tasks[/b]"]
            for task in tasks[:10]:
                suffix: list[str] = []
                if task.metadata.get("progress"):
                    suffix.append(f"{task.metadata['progress']}%")
                if task.metadata.get("status_note"):
                    suffix.append(task.metadata["status_note"])
                detail = f" ({' | '.join(suffix)})" if suffix else ""
                task_lines.append(f"{task.id} {task.status} {task.description}{detail}")
        else:
            task_lines = ["[b]Tasks[/b]", "No background tasks."]
        self.query_one("#tasks-panel", Static).update("\n".join(task_lines))
        # 更新 MCP 服务器面板
        self.query_one("#mcp-panel", Static).update(self._bundle.mcp_summary())
