"""
钩子执行引擎
============

本模块实现钩子的核心执行逻辑，支持多种钩子类型的异步执行。

支持的钩子类型：
    - CommandHookDefinition: 执行 Shell 命令
    - HttpHookDefinition: 发送 HTTP 请求
    - PromptHookDefinition: 使用模型验证
    - AgentHookDefinition: 使用 Agent 深度验证

主要组件：
    - HookExecutionContext: 钩子执行上下文
    - HookExecutor: 钩子执行器

使用示例：
    >>> from illusion.hooks.executor import HookExecutor, HookExecutionContext
    >>> executor = HookExecutor(registry, context)
    >>> result = await executor.execute(event, payload)
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from illusion.api.client import ApiMessageCompleteEvent, ApiMessageRequest, SupportsStreamingMessages
from illusion.engine.messages import ConversationMessage
from illusion.hooks.events import HookEvent
from illusion.hooks.loader import HookRegistry
from illusion.hooks.schemas import (
    AgentHookDefinition,
    CommandHookDefinition,
    HookDefinition,
    HttpHookDefinition,
    PromptHookDefinition,
)
from illusion.hooks.types import AggregatedHookResult, HookResult
from illusion.sandbox import SandboxUnavailableError
from illusion.utils.shell import create_shell_subprocess


@dataclass
class HookExecutionContext:
    """
    钩子执行上下文
    
    存储钩子执行所需的环境信息。
    
    Attributes:
        cwd: 当前工作目录
        api_client: API 客户端实例
        default_model: 默认模型名称
    """

    cwd: Path  # 当前工作目录
    api_client: SupportsStreamingMessages  # API 客户端
    default_model: str  # 默认模型名称


class HookExecutor:
    """
    钩子执行器
    
    管理钩子注册表和执行上下文，提供异步钩子执行能力。
    
    Attributes:
        _registry: 钩子注册表
        _context: 执行上下文
    
    使用示例：
        >>> executor = HookExecutor(registry, context)
        >>> result = await executor.execute(HookEvent.PRE_TOOL_USE, payload)
    """

    def __init__(self, registry: HookRegistry, context: HookExecutionContext) -> None:
        self._registry = registry  # 钩子注册表
        self._context = context  # 执行上下文

    def update_registry(self, registry: HookRegistry) -> None:
        """
        替换活动的钩子注册表
        
        Args:
            registry: 新的钩子注册表
        """
        self._registry = registry

    def update_context(
        self,
        *,
        api_client: SupportsStreamingMessages | None = None,
        default_model: str | None = None,
    ) -> None:
        """
        更新活动的钩子执行上下文
        
        Args:
            api_client: 新的 API 客户端（可选）
            default_model: 新的默认模型（可选）
        """
        if api_client is not None:
            self._context.api_client = api_client
        if default_model is not None:
            self._context.default_model = default_model

    async def execute(self, event: HookEvent, payload: dict[str, Any]) -> AggregatedHookResult:
        """
        执行事件对应的所有匹配钩子
        
        Args:
            event: 钩子事件类型
            payload: 事件载荷数据
        
        Returns:
            AggregatedHookResult: 聚合的钩子执行结果
        """
        results: list[HookResult] = []  # 存储执行结果
        # 遍历注册表中该事件的所有钩子
        for hook in self._registry.get(event):
            # 检查钩子是否与 payload 匹配
            if not _matches_hook(hook, payload):
                continue
            # 根据钩子类型执行相应的处理方法
            if isinstance(hook, CommandHookDefinition):
                results.append(await self._run_command_hook(hook, event, payload))
            elif isinstance(hook, HttpHookDefinition):
                results.append(await self._run_http_hook(hook, event, payload))
            elif isinstance(hook, PromptHookDefinition):
                results.append(await self._run_prompt_like_hook(hook, event, payload, agent_mode=False))
            elif isinstance(hook, AgentHookDefinition):
                results.append(await self._run_prompt_like_hook(hook, event, payload, agent_mode=True))
        return AggregatedHookResult(results=results)

    async def _run_command_hook(
        self,
        hook: CommandHookDefinition,
        event: HookEvent,
        payload: dict[str, Any],
    ) -> HookResult:
        """
        执行命令钩子
        
        Args:
            hook: 命令钩子定义
            event: 钩子事件
            payload: 事件载荷
        
        Returns:
            HookResult: 钩子执行结果
        """
        # 注入参数到命令中
        command = _inject_arguments(hook.command, payload, shell_escape=True)
        try:
            # 创建子进程执行命令
            process = await create_shell_subprocess(
                command,
                cwd=self._context.cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    **os.environ,
                    "illusion_HOOK_EVENT": event.value,  # 设置事件环境变量
                    "illusion_HOOK_PAYLOAD": json.dumps(payload),  # 设置载荷环境变量
                },
            )
        except SandboxUnavailableError as exc:
            # 沙箱不可用时返回失败结果
            return HookResult(
                hook_type=hook.type,
                success=False,
                blocked=hook.block_on_failure,
                reason=str(exc),
            )

        try:
            # 等待命令完成，设置超时
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=hook.timeout_seconds,
            )
        except asyncio.TimeoutError:
            # 超时杀死进程
            process.kill()
            await process.wait()
            return HookResult(
                hook_type=hook.type,
                success=False,
                blocked=hook.block_on_failure,
                reason=f"command hook timed out after {hook.timeout_seconds}s",
            )

        # 合并 stdout 和 stderr
        output = "\n".join(
            part for part in (
                stdout.decode("utf-8", errors="replace").strip(),
                stderr.decode("utf-8", errors="replace").strip(),
            ) if part
        )
        success = process.returncode == 0  # 检查退出码
        return HookResult(
            hook_type=hook.type,
            success=success,
            output=output,
            blocked=hook.block_on_failure and not success,
            reason=output or f"command hook failed with exit code {process.returncode}",
            metadata={"returncode": process.returncode},
        )

    async def _run_http_hook(
        self,
        hook: HttpHookDefinition,
        event: HookEvent,
        payload: dict[str, Any],
    ) -> HookResult:
        """
        执行 HTTP 钩子
        
        Args:
            hook: HTTP 钩子定义
            event: 钩子事件
            payload: 事件载荷
        
        Returns:
            HookResult: 钩子执行结果
        """
        try:
            # 创建异步 HTTP 客户端并发送请求
            async with httpx.AsyncClient(timeout=hook.timeout_seconds) as client:
                response = await client.post(
                    hook.url,
                    json={"event": event.value, "payload": payload},
                    headers=hook.headers,
                )
            success = response.is_success  # 检查响应状态
            output = response.text  # 响应内容
            return HookResult(
                hook_type=hook.type,
                success=success,
                output=output,
                blocked=hook.block_on_failure and not success,
                reason=output or f"http hook returned {response.status_code}",
                metadata={"status_code": response.status_code},
            )
        except Exception as exc:
            # 异常时返回失败结果
            return HookResult(
                hook_type=hook.type,
                success=False,
                blocked=hook.block_on_failure,
                reason=str(exc),
            )

    async def _run_prompt_like_hook(
        self,
        hook: PromptHookDefinition | AgentHookDefinition,
        event: HookEvent,
        payload: dict[str, Any],
        *,
        agent_mode: bool,
    ) -> HookResult:
        """
        执行提示词或 Agent 钩子
        
        Args:
            hook: 提示词或 Agent 钩子定义
            event: 钩子事件
            payload: 事件载荷
            agent_mode: 是否使用 Agent 模式
        
        Returns:
            HookResult: 钩子执行结果
        """
        # 注入参数到提示词中
        prompt = _inject_arguments(hook.prompt, payload)
        # 构建系统提示词前缀
        prefix = (
            "You are validating whether a hook condition passes in illusion. "
            "Return strict JSON: {\"ok\": true} or {\"ok\": false, \"reason\": \"...\"}."
        )
        if agent_mode:
            # Agent 模式需要更详细的推理
            prefix += " Be more thorough and reason over the payload before deciding."
        
        # 构建 API 请求
        request = ApiMessageRequest(
            model=hook.model or self._context.default_model,  # 使用指定模型或默认模型
            messages=[ConversationMessage.from_user_text(prompt)],
            system_prompt=prefix,
            max_tokens=512,
        )

        text_chunks: list[str] = []  # 存储文本块
        final_event: ApiMessageCompleteEvent | None = None  # 最终事件
        # 流式获取响应
        async for event_item in self._context.api_client.stream_message(request):
            if isinstance(event_item, ApiMessageCompleteEvent):
                final_event = event_item
            else:
                text_chunks.append(event_item.text)

        # 合并文本块
        text = "".join(text_chunks)
        # 如果有最终消息，使用最终消息的文本
        if final_event is not None and final_event.message.text:
            text = final_event.message.text

        # 解析钩子返回的 JSON
        parsed = _parse_hook_json(text)
        if parsed["ok"]:
            return HookResult(hook_type=hook.type, success=True, output=text)
        return HookResult(
            hook_type=hook.type,
            success=False,
            output=text,
            blocked=hook.block_on_failure,
            reason=parsed.get("reason", "hook rejected the event"),
        )


def _matches_hook(hook: HookDefinition, payload: dict[str, Any]) -> bool:
    """
    检查钩子是否与 payload 匹配
    
    Args:
        hook: 钩子定义
        payload: 事件载荷
    
    Returns:
        bool: 是否匹配
    """
    # 获取匹配器
    matcher = getattr(hook, "matcher", None)
    if not matcher:
        return True  # 没有匹配器则匹配所有
    # 从 payload 中提取匹配主题
    subject = str(payload.get("tool_name") or payload.get("prompt") or payload.get("event") or "")
    # 使用 fnmatch 进行模式匹配
    return fnmatch.fnmatch(subject, matcher)


def _inject_arguments(
    template: str, payload: dict[str, Any], *, shell_escape: bool = False
) -> str:
    """
    将 payload 注入到模板字符串中
    
    Args:
        template: 包含 $ARGUMENTS 占位符的模板
        payload: 要注入的数据
        shell_escape: 是否对 payload 进行 Shell 转义
    
    Returns:
        str: 注入后的字符串
    """
    # 序列化 payload 为 JSON 字符串
    serialized = json.dumps(payload, ensure_ascii=True)
    if shell_escape:
        # 对 Shell 命令进行转义
        serialized = shlex.quote(serialized)
    # 替换模板中的占位符
    return template.replace("$ARGUMENTS", serialized)


def _parse_hook_json(text: str) -> dict[str, Any]:
    """
    解析钩子返回的 JSON 响应
    
    Args:
        text: 钩子返回的文本
    
    Returns:
        dict: 解析后的结果字典
    """
    try:
        # 尝试解析 JSON
        parsed = json.loads(text)
        # 验证格式
        if isinstance(parsed, dict) and isinstance(parsed.get("ok"), bool):
            return parsed
    except json.JSONDecodeError:
        pass
    # 尝试简单文本匹配
    lowered = text.strip().lower()
    if lowered in {"ok", "true", "yes"}:
        return {"ok": True}
    # 返回失败结果
    return {"ok": False, "reason": text.strip() or "hook returned invalid JSON"}