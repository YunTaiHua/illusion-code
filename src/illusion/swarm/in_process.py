"""
进程内队友执行后端模块
=====================

本模块实现进程内的队友执行后端。
使用 :mod:`contextvars` 在当前 Python 进程中将队友代理作为 asyncio Task 运行，
实现每个队友的上下文隔离（Python 等效于 Node 的 AsyncLocalStorage）。

架构概述
--------------------
* :class:`TeammateAbortController` – 提供优雅取消和强制终止双重信号的中止控制器。
* :class:`TeammateContext` – 保存身份 + 中止控制器 + 运行时统计的数据类
  （tool_use_count, total_tokens, status）。
* :func:`get_teammate_context` / :func:`set_teammate_context` – ContextVar
  访问器，使任何在队友任务内运行的代码可以发现自己的身份，
  无需显式参数传递。
* :func:`start_in_process_teammate` – 实际协程，设置上下文，
  驱动查询引擎，并在退出时清理。
* :class:`InProcessBackend` – 实现
  :class:`~illusion.swarm.types.TeammateExecutor` 并管理活跃 asyncio Task 的字典。

使用示例：
    >>> from illusion.swarm.in_process import InProcessBackend
    >>> backend = InProcessBackend()
    >>> result = await backend.spawn(config)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal

# 导入邮箱和类型定义
from illusion.swarm.mailbox import (
    TeammateMailbox,
    create_idle_notification,
)
from illusion.swarm.types import (
    BackendType,
    SpawnResult,
    TeammateMessage,
    TeammateSpawnConfig,
)

# 配置模块级日志记录器
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 中止控制器
# ---------------------------------------------------------------------------


class TeammateAbortController:
    """进程内队友的双重信号中止控制器。

    提供 *优雅* 取消（设置 ``cancel_event``；代理完成当前工具使用后退出）
    和 *强制* 终止（设置 ``force_cancel``；asyncio Task 立即取消）。

    镜像 TypeScript ``AbortController`` / linked-controller 模式，
    用于 ``spawnInProcess.ts`` 和 ``InProcessBackend.ts``。
    """

    def __init__(self) -> None:
        self.cancel_event: asyncio.Event = asyncio.Event()
        """设置为请求代理循环的优雅取消。"""

        self.force_cancel: asyncio.Event = asyncio.Event()
        """设置为请求立即（强制）终止。"""

        self._reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        """如果任一取消信号已设置则返回 True。"""
        return self.cancel_event.is_set() or self.force_cancel.is_set()

    def request_cancel(self, reason: str | None = None, *, force: bool = False) -> None:
        """请求取消队友。

        Args:
            reason: 取消的人类可读原因（用于日志记录）。
            force: 当为 True 时，设置 ``force_cancel`` 以立即终止。
                   当为 False 时，设置 ``cancel_event`` 以优雅关闭。
        """
        self._reason = reason
        if force:
            logger.debug(
                "[TeammateAbortController] Force-cancel requested: %s", reason or "(no reason)"
            )
            self.force_cancel.set()
            self.cancel_event.set()  # 也设置优雅，以便两个检查都触发
        else:
            logger.debug(
                "[TeammateAbortController] Graceful cancel requested: %s",
                reason or "(no reason)",
            )
            self.cancel_event.set()

    @property
    def reason(self) -> str | None:
        """最近一次 :meth:`request_cancel` 调用提供的原因。"""
        return self._reason


# ---------------------------------------------------------------------------
# 通过 ContextVar 的每个队友上下文隔离
# ---------------------------------------------------------------------------


# 队友状态类型字面量
TeammateStatus = Literal["starting", "running", "idle", "stopping", "stopped"]


@dataclass
class TeammateContext:
    """必须跨并发代理隔离的每个队友状态。

    存储在 :data:`ContextVar` 中，以便每个 asyncio Task 看到自己的副本，无需任何锁。
    """

    agent_id: str
    """唯一代理标识符（``agentName@teamName``）。"""

    agent_name: str
    """人类可读名称，例如 ``"researcher"``。"""

    team_name: str
    """此队友所属的团队。"""

    parent_session_id: str | None = None
    """生成负责人的会话 ID，用于转录关联。"""

    color: str | None = None
    """可选的 UI 颜色字符串。"""

    plan_mode_required: bool = False
    """此代理是否必须在做出更改前进入 plan 模式。"""

    abort_controller: TeammateAbortController = field(
        default_factory=TeammateAbortController
    )
    """双重信号中止控制器（优雅取消 + 强制终止）。"""

    message_queue: asyncio.Queue[TeammateMessage] = field(
        default_factory=asyncio.Queue
    )
    """回合之间传递的待处理消息队列。

    执行循环在查询迭代之间耗尽此队列，以便来自负责人的消息
    作为新的用户回合注入，而不是丢失。
    """

    status: TeammateStatus = "starting"
    """此队友的生命周期状态。"""

    started_at: float = field(default_factory=time.time)
    """此队友生成时的 Unix 时间戳。"""

    tool_use_count: int = 0
    """此队友生命周期内调用的工具数量。"""

    total_tokens: int = 0
    """所有查询回合的累计 token 计数（输入 + 输出）。"""

    # 向后兼容垫片，使读取 ``cancel_event`` 的现有代码
    # 无需修改即可继续工作。
    @property
    def cancel_event(self) -> asyncio.Event:
        """优雅取消事件（委托给 :attr:`abort_controller`）。"""
        return self.abort_controller.cancel_event


# 队友上下文变量
_teammate_context_var: ContextVar[TeammateContext | None] = ContextVar(
    "_teammate_context_var", default=None
)


def get_teammate_context() -> TeammateContext | None:
    """返回当前运行的队友任务的 :class:`TeammateContext`。

    在进程外队友之外调用时返回 ``None``。
    """
    return _teammate_context_var.get()


def set_teammate_context(ctx: TeammateContext) -> None:
    """将 *ctx* 绑定到当前异步上下文（任务本地）。"""
    _teammate_context_var.set(ctx)


# ---------------------------------------------------------------------------
# 代理执行循环
# ---------------------------------------------------------------------------


async def start_in_process_teammate(
    *,
    config: TeammateSpawnConfig,
    agent_id: str,
    abort_controller: TeammateAbortController,
    query_context: Any | None = None,
) -> None:
    """运行进程内队友的代理查询循环。

    此协程由 :class:`InProcessBackend` 作为 :class:`asyncio.Task` 启动。它：

    1. 将新的 :class:`TeammateContext` 绑定到当前异步上下文。
    2. 驱动查询引擎循环（重用
       :func:`~illusion.engine.query.run_query`）。
    3. 在回合之间轮询队友的邮箱以接收传入消息 /
       关闭请求。任何 ``user_message`` 项目被推入
       上下文的 :attr:`~TeammateContext.message_queue` 并作为额外的用户回合注入。
    4. 完成后向负责人写入空闲通知。
    5. 正常退出 *或* 取消时清理。

    参数
    ----------
    config:
        来自负责人的生成配置。
    agent_id:
        完全限定的代理标识符（``name@team``）。
    abort_controller:
        此队友的双重信号中止控制器。
    query_context:
        可选的预构建
        :class:`~illusion.engine.query.QueryContext`。当为 *None* 时
        此函数运行一个尊重取消信号的存根，以便测试和直接调用仍然有效。
    """
    # 创建并初始化队友上下文
    ctx = TeammateContext(
        agent_id=agent_id,
        agent_name=config.name,
        team_name=config.team,
        parent_session_id=config.parent_session_id,
        color=config.color,
        plan_mode_required=config.plan_mode_required,
        abort_controller=abort_controller,
        started_at=time.time(),
        status="starting",
    )
    set_teammate_context(ctx)

    # 创建邮箱
    mailbox = TeammateMailbox(team_name=config.team, agent_id=agent_id)

    logger.debug("[in_process] %s: starting", agent_id)

    try:
        ctx.status = "running"

        if query_context is not None:
            # 运行实际查询循环
            await _run_query_loop(query_context, config, ctx, mailbox)
        else:
            # 最小存根：记录我们收到提示词并尊重取消。
            # 一旦 harness 为进程内队友连接完整引擎，
            # 用真正的 QueryContext 构建器替换此分支。
            logger.info(
                "[in_process] %s: no query_context supplied — stub run for prompt: %.80s",
                agent_id,
                config.prompt,
            )
            ctx.status = "idle"
            for _ in range(10):
                if abort_controller.is_cancelled:
                    logger.debug("[in_process] %s: cancelled during stub run", agent_id)
                    return
                await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        logger.debug("[in_process] %s: task cancelled", agent_id)
        raise
    except Exception:
        logger.exception("[in_process] %s: unhandled exception in agent loop", agent_id)
    finally:
        ctx.status = "stopped"
        # 通知负责人此队友已空闲/完成。
        with contextlib.suppress(Exception):
            idle_msg = create_idle_notification(
                sender=agent_id,
                recipient="leader",
                summary=f"{config.name} finished (tools={ctx.tool_use_count}, tokens={ctx.total_tokens})",
            )
            leader_mailbox = TeammateMailbox(team_name=config.team, agent_id="leader")
            await leader_mailbox.write(idle_msg)

        logger.debug(
            "[in_process] %s: exiting (tools=%d, tokens=%d)",
            agent_id,
            ctx.tool_use_count,
            ctx.total_tokens,
        )


async def _drain_mailbox(
    mailbox: TeammateMailbox,
    ctx: TeammateContext,
) -> bool:
    """读取待处理邮箱消息并处理关闭/用户消息。

    Returns:
        如果收到关闭消息返回 True（调用者应停止循环）。
    """
    try:
        pending = await mailbox.read_all(unread_only=True)
    except Exception:
        pending = []

    for msg in pending:
        try:
            await mailbox.mark_read(msg.id)
        except Exception:
            pass

        if msg.type == "shutdown":
            logger.debug("[in_process] %s: received shutdown message", ctx.agent_id)
            ctx.abort_controller.request_cancel(reason="shutdown message received")
            return True

        elif msg.type == "user_message":
            # 将消息加入队列，以便查询循环可以将其作为新回合注入。
            logger.debug("[in_process] %s: queuing user_message from mailbox", ctx.agent_id)
            content = msg.payload.get("content", "") if isinstance(msg.payload, dict) else str(msg.payload)
            teammate_msg = TeammateMessage(
                text=content,
                from_agent=msg.sender,
                color=msg.payload.get("color") if isinstance(msg.payload, dict) else None,
                timestamp=str(msg.timestamp),
            )
            await ctx.message_queue.put(teammate_msg)

    return False


async def _run_query_loop(
    query_context: Any,
    config: TeammateSpawnConfig,
    ctx: TeammateContext,
    mailbox: TeammateMailbox,
) -> None:
    """驱动 :func:`~illusion.engine.query.run_query` 直到完成或取消。

    在回合之间我们：
    - 耗尽邮箱以获取关闭请求和用户消息。
    - 将排队的用户消息注入为额外回合。
    - 检查中止控制器。
    - 跟踪 tool_use_count 和 total_tokens。
    """
    # 延迟导入以避免模块加载时的循环依赖。
    from illusion.engine.query import run_query
    from illusion.engine.messages import ConversationMessage

    # 初始化消息列表，包含初始提示词
    messages: list[ConversationMessage] = [
        ConversationMessage.from_user_text(config.prompt)
    ]

    async for event, usage in run_query(query_context, messages):
        # 如果提供了 usage 信息则跟踪 token 使用
        if usage is not None:
            with contextlib.suppress(AttributeError, TypeError):
                ctx.total_tokens += getattr(usage, "input_tokens", 0)
                ctx.total_tokens += getattr(usage, "output_tokens", 0)

        # 跟踪工具使用事件
        with contextlib.suppress(AttributeError, TypeError):
            if getattr(event, "type", None) in ("tool_use", "tool_call"):
                ctx.tool_use_count += 1

        # 在事件之间检查取消或关闭
        if ctx.abort_controller.is_cancelled:
            logger.debug(
                "[in_process] %s: abort_controller cancelled, stopping query loop",
                ctx.agent_id,
            )
            return

        # 耗尽邮箱 — 立即处理关闭请求
        should_stop = await _drain_mailbox(mailbox, ctx)
        if should_stop:
            return

        # 耗尽消息队列并注入为新回合
        while not ctx.message_queue.empty():
            try:
                queued = ctx.message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            logger.debug(
                "[in_process] %s: injecting queued message from %s",
                ctx.agent_id,
                queued.from_agent,
            )
            messages.append(ConversationMessage(role="user", content=queued.text))

    ctx.status = "idle"


# ---------------------------------------------------------------------------
# InProcessBackend
# ---------------------------------------------------------------------------


@dataclass
class _TeammateEntry:
    """运行中进程内队友的内部注册表条目。"""

    task: asyncio.Task[None]
    abort_controller: TeammateAbortController
    task_id: str
    started_at: float = field(default_factory=time.time)


class InProcessBackend:
    """将代理作为当前进程中的 asyncio Task 运行的 TeammateExecutor。

    上下文隔离由 :mod:`contextvars` 提供：每个生成的
    :class:`asyncio.Task` 使用自己的上下文副本运行，因此
    :func:`get_teammate_context` 为每个并发代理返回正确的身份。
    """

    type: BackendType = "in_process"

    def __init__(self) -> None:
        # 映射 agent_id -> _TeammateEntry
        self._active: dict[str, _TeammateEntry] = {}

    # ------------------------------------------------------------------
    # TeammateExecutor 协议
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """进程内后端始终可用 —— 无外部依赖。"""
        return True

    async def spawn(self, config: TeammateSpawnConfig) -> SpawnResult:
        """将进程内队友生成为 asyncio Task。

        创建 :class:`TeammateAbortController`，通过
        :mod:`contextvars` 复制-on-create 语义将其绑定到新 Task，
        并在 :attr:`_active` 中注册任务。
        """
        agent_id = f"{config.name}@{config.team}"
        task_id = f"in_process_{uuid.uuid4().hex[:12]}"

        # 检查是否已存在活跃的同名代理
        if agent_id in self._active:
            entry = self._active[agent_id]
            if not entry.task.done():
                logger.warning(
                    "[InProcessBackend] spawn(): %s is already running", agent_id
                )
                return SpawnResult(
                    task_id=task_id,
                    agent_id=agent_id,
                    backend_type=self.type,
                    success=False,
                    error=f"Agent {agent_id!r} is already running",
                )

        # 创建中止控制器
        abort_controller = TeammateAbortController()

        # asyncio.create_task() 自动复制当前上下文，
        # 因此每个 Task 以独立的 ContextVar 状态开始。
        task = asyncio.create_task(
            start_in_process_teammate(
                config=config,
                agent_id=agent_id,
                abort_controller=abort_controller,
            ),
            name=f"teammate-{agent_id}",
        )

        entry = _TeammateEntry(
            task=task,
            abort_controller=abort_controller,
            task_id=task_id,
        )
        self._active[agent_id] = entry

        # 添加完成回调
        def _on_done(t: asyncio.Task[None]) -> None:
            self._active.pop(agent_id, None)
            if not t.cancelled() and t.exception() is not None:
                self._on_teammate_error(agent_id, t.exception())  # type: ignore[arg-type]

        task.add_done_callback(_on_done)

        logger.debug("[InProcessBackend] spawned %s (task_id=%s)", agent_id, task_id)
        return SpawnResult(
            task_id=task_id,
            agent_id=agent_id,
            backend_type=self.type,
        )

    async def send_message(self, agent_id: str, message: TeammateMessage) -> None:
        """将 *message* 写入队友的基于文件的邮箱。

        从 *agent_id*（``name@team`` 格式）推断代理名称和团队。
        这镜像了基于 pane 的后端的工作方式，以便 swarm 栈的其余部分
        与后端无关。

        如果队友正在进程内运行且其 :class:`TeammateContext` 可访问，
        消息也被直接推入 ``ctx.message_queue`` 以实现低延迟传递，
        无需文件系统往返。
        """
        if "@" not in agent_id:
            raise ValueError(
                f"Invalid agent_id {agent_id!r}: expected 'agentName@teamName'"
            )
        agent_name, team_name = agent_id.split("@", 1)

        from illusion.swarm.mailbox import MailboxMessage

        msg = MailboxMessage(
            id=str(uuid.uuid4()),
            type="user_message",
            sender=message.from_agent,
            recipient=agent_id,
            payload={
                "content": message.text,
                **({"color": message.color} if message.color else {}),
            },
            timestamp=message.timestamp and float(message.timestamp) or time.time(),
        )
        mailbox = TeammateMailbox(team_name=team_name, agent_id=agent_name)
        await mailbox.write(msg)
        logger.debug("[InProcessBackend] sent message to %s", agent_id)

    async def shutdown(
        self, agent_id: str, *, force: bool = False, timeout: float = 10.0
    ) -> bool:
        """终止运行中的进程内队友。

        参数
        ----------
        agent_id:
            要终止的代理。
        force:
            如果为 *True*，立即取消 asyncio Task，不等待优雅关闭。
        timeout:
            设置取消事件后等待任务完成的秒数，
            然后回退到 :meth:`asyncio.Task.cancel`。

        返回值
        -------
        bool
            如果找到代理并启动了终止返回 *True*。
        """
        entry = self._active.get(agent_id)
        if entry is None:
            logger.debug(
                "[InProcessBackend] shutdown(): %s not found in active tasks", agent_id
            )
            return False

        if entry.task.done():
            self._active.pop(agent_id, None)
            return True

        if force:
            # 强制：请求取消并立即取消任务
            entry.abort_controller.request_cancel(reason="force shutdown", force=True)
            entry.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(entry.task), timeout=timeout)
        else:
            # 优雅：请求取消并等待自行退出
            entry.abort_controller.request_cancel(reason="graceful shutdown")
            try:
                await asyncio.wait_for(asyncio.shield(entry.task), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "[InProcessBackend] %s did not exit within %.1fs — forcing cancel",
                    agent_id,
                    timeout,
                )
                entry.abort_controller.request_cancel(reason="timeout — forcing", force=True)
                entry.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await entry.task

        await self._cleanup_teammate(agent_id)
        logger.debug("[InProcessBackend] shut down %s", agent_id)
        return True

    # ------------------------------------------------------------------
    # 增强的生命周期管理
    # ------------------------------------------------------------------

    async def _cleanup_teammate(self, agent_id: str) -> None:
        """在任务完成后为 *agent_id* 执行完整清理。

        - 从 :attr:`_active` 中移除条目。
        - 取消中止控制器（以防尚未取消）。
        - 记录清理。

        此函数自动从任务的完成回调和 :meth:`shutdown` 调用。
        """
        entry = self._active.pop(agent_id, None)
        if entry is None:
            return

        # 确保中止控制器被触发，以便任何等待者解除阻塞
        if not entry.abort_controller.is_cancelled:
            entry.abort_controller.request_cancel(reason="cleanup")

        logger.debug(
            "[InProcessBackend] _cleanup_teammate: %s removed from registry", agent_id
        )

    def _on_teammate_error(self, agent_id: str, error: Exception) -> None:
        """处理来自队友 Task 的未处理异常。

        记录结构化错误报告并从注册表中移除条目。
        未来可以向负责人邮箱发出 TaskNotification。
        """
        duration = 0.0
        entry = self._active.get(agent_id)
        if entry is not None:
            duration = time.time() - entry.started_at
            self._active.pop(agent_id, None)

        logger.error(
            "[InProcessBackend] Teammate %s raised an unhandled exception "
            "(duration=%.1fs): %s: %s",
            agent_id,
            duration,
            type(error).__name__,
            error,
        )

    def get_teammate_status(self, agent_id: str) -> dict[str, Any] | None:
        """返回 *agent_id* 的状态字典，包含使用统计。

        如果代理不在活跃注册表中则返回 *None*。

        返回的字典包含::

            {
                "agent_id": str,
                "task_id": str,
                "is_done": bool,
                "duration_s": float,
            }
        """
        entry = self._active.get(agent_id)
        if entry is None:
            return None

        return {
            "agent_id": agent_id,
            "task_id": entry.task_id,
            "is_done": entry.task.done(),
            "duration_s": time.time() - entry.started_at,
        }

    def list_teammates(self) -> list[tuple[str, bool, float]]:
        """返回 ``(agent_id, is_running, duration_seconds)`` 元组列表。

        ``is_running`` 如果任务存活且未完成则为 True。
        ``duration_seconds`` 是生成以来的挂钟时间。
        """
        now = time.time()
        result = []
        for agent_id, entry in self._active.items():
            is_running = not entry.task.done()
            duration = now - entry.started_at
            result.append((agent_id, is_running, duration))
        return result

    # ------------------------------------------------------------------
    # 便捷辅助函数
    # ------------------------------------------------------------------

    def is_active(self, agent_id: str) -> bool:
        """如果队友有运行中（未完成）的 Task 则返回 *True*。"""
        entry = self._active.get(agent_id)
        if entry is None:
            return False
        return not entry.task.done()

    def active_agents(self) -> list[str]:
        """返回具有当前运行 Task 的 agent_ids 列表。"""
        return [aid for aid, entry in self._active.items() if not entry.task.done()]

    async def shutdown_all(self, *, force: bool = False, timeout: float = 10.0) -> None:
        """优雅地（或强制地）终止所有活跃队友。"""
        agent_ids = list(self._active.keys())
        await asyncio.gather(
            *(self.shutdown(aid, force=force, timeout=timeout) for aid in agent_ids),
            return_exceptions=True,
        )
