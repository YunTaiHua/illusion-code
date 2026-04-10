"""
App 应用程序模块
=============

本模块实现 IllusionCode 交互式会话入口点。

主要功能：
    - REPL 交互模式（默认的 React 终端界面）
    - 打印模式（非交互式，适合脚本和自动化任务）
    - 后端单独运行模式

函数说明：
    - run_repl: 运行交互式 REPL
    - run_print_mode: 运行非交互式打印模式

使用示例：
    >>> from illusion.ui.app import run_repl, run_print_mode
    >>> 
    >>> # 启动交互式 REPL
    >>> await run_repl()
    >>> 
    >>> # 运行单次交互模式
    >>> await run_print_mode(prompt="帮我写一个 hello world 程序")
"""

from __future__ import annotations

import json
import sys

from illusion.api.client import SupportsStreamingMessages
from illusion.engine.stream_events import StreamEvent
from illusion.ui.backend_host import run_backend_host
from illusion.ui.react_launcher import launch_react_tui
from illusion.ui.runtime import build_runtime, close_runtime, handle_line, start_runtime


async def run_repl(
    *,
    prompt: str | None = None,
    cwd: str | None = None,
    model: str | None = None,
    max_turns: int | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
    api_key: str | None = None,
    api_format: str | None = None,
    api_client: SupportsStreamingMessages | None = None,
    backend_only: bool = False,
    restore_messages: list[dict] | None = None,
) -> None:
    """运行默认的 IllusionCode 交互式应用程序（React TUI）。

    Args:
        prompt: 初始提示词
        cwd: 工作目录
        model: 使用的模型名称
        max_turns: 最大对话轮次
        base_url: API 基础 URL
        system_prompt: 系统提示词
        api_key: API 密钥
        api_format: API 格式（copilot/openai/anthropic）
        api_client: 流式 API 客户端实例
        backend_only: 是否仅运行后端
        restore_messages: 恢复的会话消息列表
    """
    # 后端单独运行模式
    if backend_only:
        await run_backend_host(
            cwd=cwd,
            model=model,
            max_turns=max_turns,
            base_url=base_url,
            system_prompt=system_prompt,
            api_key=api_key,
            api_format=api_format,
            api_client=api_client,
            restore_messages=restore_messages,
            enforce_max_turns=max_turns is not None,
        )
        return

    # 启动 React TUI 前端
    exit_code = await launch_react_tui(
        prompt=prompt,
        cwd=cwd,
        model=model,
        max_turns=max_turns,
        base_url=base_url,
        system_prompt=system_prompt,
        api_key=api_key,
        api_format=api_format,
    )
    # 如果前端退出代码非零，抛出 SystemExit
    if exit_code != 0:
        raise SystemExit(exit_code)


async def run_print_mode(
    *,
    prompt: str,
    output_format: str = "text",
    cwd: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
    append_system_prompt: str | None = None,
    api_key: str | None = None,
    api_format: str | None = None,
    api_client: SupportsStreamingMessages | None = None,
    permission_mode: str | None = None,
    max_turns: int | None = None,
) -> None:
    """非交互式模式：提交提示词，流式输出，然后退出。

    Args:
        prompt: 用户提示词
        output_format: 输出格式（text/json/stream-json）
        cwd: 工作目录
        model: 使用的模型名称
        base_url: API 基础 URL
        system_prompt: 系统提示词
        append_system_prompt: 追加的系统提示词
        api_key: API 密钥
        api_format: API 格式
        api_client: 流式 API 客户端实例
        permission_mode: 权限模式
        max_turns: 最大对话轮次
    """
    from illusion.engine.stream_events import (
        AssistantTextDelta,
        AssistantTurnComplete,
        ErrorEvent,
        StatusEvent,
        ToolExecutionCompleted,
        ToolExecutionStarted,
    )

    # 空权限回调 - 自动允许所有操作
    async def _noop_permission(tool_name: str, reason: str) -> bool:
        return True

    # 空问答回调 - 返回空字符串
    async def _noop_ask(question: str) -> str:
        return ""

    # 构建运行时
    bundle = await build_runtime(
        prompt=prompt,
        model=model,
        max_turns=max_turns,
        base_url=base_url,
        system_prompt=system_prompt,
        api_key=api_key,
        api_format=api_format,
        enforce_max_turns=True,
        api_client=api_client,
        permission_prompt=_noop_permission,
        ask_user_prompt=_noop_ask,
    )
    await start_runtime(bundle)

    # 收集输出
    collected_text = ""
    events_list: list[dict] = []

    try:
        # 系统消息打印回调
        async def _print_system(message: str) -> None:
            nonlocal collected_text
            if output_format == "text":
                print(message, file=sys.stderr)
            elif output_format == "stream-json":
                obj = {"type": "system", "message": message}
                print(json.dumps(obj), flush=True)
                events_list.append(obj)

        # 流式事件渲染回调
        async def _render_event(event: StreamEvent) -> None:
            nonlocal collected_text
            # 助手文本增量
            if isinstance(event, AssistantTextDelta):
                collected_text += event.text
                if output_format == "text":
                    sys.stdout.write(event.text)
                    sys.stdout.flush()
                elif output_format == "stream-json":
                    obj = {"type": "assistant_delta", "text": event.text}
                    print(json.dumps(obj), flush=True)
                    events_list.append(obj)
            # 助手回合完成
            elif isinstance(event, AssistantTurnComplete):
                if output_format == "text":
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                elif output_format == "stream-json":
                    obj = {"type": "assistant_complete", "text": event.message.text.strip()}
                    print(json.dumps(obj), flush=True)
                    events_list.append(obj)
            # 工具开始执行
            elif isinstance(event, ToolExecutionStarted):
                if output_format == "stream-json":
                    obj = {"type": "tool_started", "tool_name": event.tool_name, "tool_input": event.tool_input}
                    print(json.dumps(obj), flush=True)
                    events_list.append(obj)
            # 工具执行完成
            elif isinstance(event, ToolExecutionCompleted):
                if output_format == "stream-json":
                    obj = {"type": "tool_completed", "tool_name": event.tool_name, "output": event.output, "is_error": event.is_error}
                    print(json.dumps(obj), flush=True)
                    events_list.append(obj)
            # 错误事件
            elif isinstance(event, ErrorEvent):
                if output_format == "text":
                    print(event.message, file=sys.stderr)
                elif output_format == "stream-json":
                    obj = {"type": "error", "message": event.message, "recoverable": event.recoverable}
                    print(json.dumps(obj), flush=True)
                    events_list.append(obj)
            # 状态事件
            elif isinstance(event, StatusEvent):
                if output_format == "text":
                    print(event.message, file=sys.stderr)
                elif output_format == "stream-json":
                    obj = {"type": "status", "message": event.message}
                    print(json.dumps(obj), flush=True)
                    events_list.append(obj)

        # 空清空输出回调
        async def _clear_output() -> None:
            pass

        # 处理输入行
        await handle_line(
            bundle,
            prompt,
            print_system=_print_system,
            render_event=_render_event,
            clear_output=_clear_output,
        )

        # JSON 格式输出最终结果
        if output_format == "json":
            result = {"type": "result", "text": collected_text.strip()}
            print(json.dumps(result))
    finally:
        # 关闭运行时
        await close_runtime(bundle)