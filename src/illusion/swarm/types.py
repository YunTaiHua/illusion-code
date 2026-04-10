"""
Swarm 后端类型定义模块
=====================

本模块定义 Swarm 功能使用的所有类型和协议。
包括后端类型、Pane 后端类型、数据类等。

类型定义：
    - BackendType: 支持的后端类型
    - PaneBackendType: Pane 后端类型
    - PaneId: 终端 pane 标识符

数据类：
    - BackendDetectionResult: 后端检测结果
    - TeammateIdentity: 队友身份
    - TeammateSpawnConfig: 队友生成配置
    - SpawnResult: 生成结果
    - TeammateMessage: 队友消息
    - CreatePaneResult: 创建 Pane 结果

协议：
    - PaneBackend: Pane 管理后端协议
    - TeammateExecutor: 队友执行器协议

使用示例：
    >>> from illusion.swarm.types import BackendType, TeammateExecutor, SpawnResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# 后端类型字面量
# ---------------------------------------------------------------------------

BackendType = Literal["subprocess", "in_process", "tmux", "iterm2"]
"""所有支持的后端类型。"""

PaneBackendType = Literal["tmux", "iterm2"]
"""BackendType 的子集，仅用于基于 pane（可视化）的后端。"""

PaneId = str
"""后端管理的终端 pane 的不透明标识符。

对于 tmux，这是 pane ID（例如 ``"%1"``）。
对于 iTerm2，这是 ``it2`` 返回的会话 ID。
"""


# ---------------------------------------------------------------------------
# Pane 后端类型
# ---------------------------------------------------------------------------


@dataclass
class CreatePaneResult:
    """创建新队友 pane 的结果。"""

    pane_id: PaneId
    """新创建的 pane 的 pane ID。"""

    is_first_teammate: bool
    """这是否是第一个队友 pane（影响布局策略）。"""


@runtime_checkable
class PaneBackend(Protocol):
    """Pane 管理后端（tmux / iTerm2）的协议。

    抽象化用于 swarm 模式中队友可视化的终端 pane 创建和管理操作。
    """

    @property
    def type(self) -> BackendType:
        """此后端的类型标识符。"""
        ...

    @property
    def display_name(self) -> str:
        """此后端的人类可读显示名称。"""
        ...

    @property
    def supports_hide_show(self) -> bool:
        """此后端是否支持隐藏和显示 pane。"""
        ...

    async def is_available(self) -> bool:
        """如果此后端在系统上可用则返回 True。

        对于 tmux：检查 tmux 二进制文件是否存在。
        对于 iTerm2：检查 it2 CLI 是否已安装和配置。
        """
        ...

    async def is_running_inside(self) -> bool:
        """如果当前在此后端的环境中则返回 True。

        对于 tmux：检查我们是否在 tmux 会话中（``$TMUX`` 设置）。
        对于 iTerm2：检查我们是否在 iTerm2 中运行。
        """
        ...

    async def create_teammate_pane_in_swarm_view(
        self,
        name: str,
        color: str | None = None,
    ) -> CreatePaneResult:
        """在 swarm 视图中为队友创建新 pane。

        Args:
            name: 队友的显示名称。
            color: pane 边框/标题的可选颜色名称。

        Returns:
            包含 pane ID 和第一个队友标志的 :class:`CreatePaneResult`。
        """
        ...

    async def send_command_to_pane(
        self,
        pane_id: PaneId,
        command: str,
        *,
        use_external_session: bool = False,
    ) -> None:
        """发送要在 *pane_id* 中执行的 shell 命令。

        Args:
            pane_id: 目标 pane。
            command: 要执行的命令字符串。
            use_external_session: 如果为 True，使用外部会话 socket（仅 tmux）。
        """
        ...

    async def set_pane_border_color(
        self,
        pane_id: PaneId,
        color: str,
        *,
        use_external_session: bool = False,
    ) -> None:
        """为 *pane_id* 设置边框颜色。"""
        ...

    async def set_pane_title(
        self,
        pane_id: PaneId,
        name: str,
        color: str | None = None,
        *,
        use_external_session: bool = False,
    ) -> None:
        """设置显示在 *pane_id* 边框/标题中的标题。"""
        ...

    async def enable_pane_border_status(
        self,
        window_target: str | None = None,
        *,
        use_external_session: bool = False,
    ) -> None:
        """启用 pane 边框状态显示（显示边框中的标题）。"""
        ...

    async def rebalance_panes(
        self,
        window_target: str,
        has_leader: bool,
    ) -> None:
        """重新平衡 pane 以实现所需的布局。

        Args:
            window_target: 包含 pane 的窗口。
            has_leader: 是否有负责人 pane（影响策略）。
        """
        ...

    async def kill_pane(
        self,
        pane_id: PaneId,
        *,
        use_external_session: bool = False,
    ) -> bool:
        """杀死/关闭 *pane_id*。

        Returns:
            如果 pane 成功杀死返回 True。
        """
        ...

    async def hide_pane(
        self,
        pane_id: PaneId,
        *,
        use_external_session: bool = False,
    ) -> bool:
        """通过将其分解为隐藏窗口来隐藏 *pane_id*。

        pane 保持运行，但在主布局中不可见。

        Returns:
            如果 pane 成功隐藏返回 True。
        """
        ...

    async def show_pane(
        self,
        pane_id: PaneId,
        target_window_or_pane: str,
        *,
        use_external_session: bool = False,
    ) -> bool:
        """通过将其重新加入主窗口来显示先前隐藏的 pane。

        Returns:
            如果 pane 成功显示返回 True。
        """
        ...

    def list_panes(self) -> list[PaneId]:
        """返回此后端管理的所有已知 pane ID 列表。"""
        ...


# ---------------------------------------------------------------------------
# 后端检测结果
# ---------------------------------------------------------------------------


@dataclass
class BackendDetectionResult:
    """来自后端自动检测的结果。

    Attributes:
        backend: 应使用的后端。
        is_native: 我们是否在后端的本机环境中运行。
        needs_setup: 当检测到 iTerm2 但 ``it2`` 未安装时为 True。
    """

    backend: str
    """后端类型字符串（例如 ``"tmux"``, ``"in_process"``）。"""

    is_native: bool
    """如果在后端自己的环境中运行则为 True。"""

    needs_setup: bool = False
    """当需要额外设置时为 True（例如安装 ``it2``）。"""


# ---------------------------------------------------------------------------
# 队友身份和生成配置
# ---------------------------------------------------------------------------


@dataclass
class TeammateIdentity:
    """队友代理的身份字段。"""

    agent_id: str
    """唯一代理标识符（格式：agentName@teamName）。"""

    name: str
    """代理名称（例如 'researcher', 'tester'）。"""

    team: str
    """此队友所属的团队名称。"""

    color: str | None = None
    """用于 UI 区分的分配颜色。"""

    parent_session_id: str | None = None
    """用于上下文链接的父会话 ID。"""


@dataclass
class TeammateSpawnConfig:
    """生成队友的配置（任何执行模式）。"""

    name: str
    """人类可读的队友名称（例如 ``"researcher"``）。"""

    team: str
    """此队友所属的团队名称。"""

    prompt: str
    """队友的初始提示词/任务。"""

    cwd: str
    """队友的工作目录。"""

    parent_session_id: str
    """父会话 ID（用于转录关联）。"""

    model: str | None = None
    """此队友的模型覆盖。"""

    system_prompt: str | None = None
    """从工作流配置解析的系统提示词。"""

    system_prompt_mode: Literal["default", "replace", "append"] | None = None
    """如何应用系统提示词：替换或追加到默认。"""

    color: str | None = None
    """队友的可选 UI 颜色。"""

    color_override: str | None = None
    """明确的颜色覆盖（优先于 ``color``）。"""

    permissions: list[str] = field(default_factory=list)
    """授予此队友的工具权限。"""

    plan_mode_required: bool = False
    """此队友是否必须在实现前进入 plan 模式。"""

    allow_permission_prompts: bool = False
    """当为 False（默认）时，未列出的工具被自动拒绝。"""

    worktree_path: str | None = None
    """可选的 git worktree 路径，用于隔离的文件系统访问。"""

    session_id: str | None = None
    """明确的会话 ID（如果未提供则生成）。"""

    subscriptions: list[str] = field(default_factory=list)
    """此队友订阅的事件主题。"""


# ---------------------------------------------------------------------------
# 生成结果和消息
# ---------------------------------------------------------------------------


@dataclass
class SpawnResult:
    """生成队友的结果。"""

    task_id: str
    """任务管理器中的任务 ID。"""

    agent_id: str
    """唯一代理标识符（格式：agentName@teamName）。"""

    backend_type: BackendType
    """用于生成此代理的后端。"""

    success: bool = True
    error: str | None = None

    pane_id: PaneId | None = None
    """基于 pane 的后端（tmux / iTerm2）的 pane ID。"""


@dataclass
class TeammateMessage:
    """发送给队友的消息。"""

    text: str
    from_agent: str
    color: str | None = None
    timestamp: str | None = None
    summary: str | None = None


# ---------------------------------------------------------------------------
# TeammateExecutor 协议
# ---------------------------------------------------------------------------


@runtime_checkable
class TeammateExecutor(Protocol):
    """队友执行后端的协议。

    抽象化跨子进程、进程内和 tmux 后端的生成/消息/关闭操作。
    """

    type: BackendType

    def is_available(self) -> bool:
        """检查此后端在系统上是否可用。"""
        ...

    async def spawn(self, config: TeammateSpawnConfig) -> SpawnResult:
        """使用给定配置生成新队友。"""
        ...

    async def send_message(self, agent_id: str, message: TeammateMessage) -> None:
        """通过 stdin 向运行中的队友发送消息。"""
        ...

    async def shutdown(self, agent_id: str, *, force: bool = False) -> bool:
        """终止队友。

        Args:
            agent_id: 要终止的代理。
            force: 如果为 True，立即杀死。如果为 False，尝试优雅关闭。

        Returns:
            如果代理成功终止返回 True。
        """
        ...


# ---------------------------------------------------------------------------
# 类型守卫辅助函数
# ---------------------------------------------------------------------------


def is_pane_backend(backend_type: BackendType) -> bool:
    """如果 *backend_type* 是终端-pane 后端（tmux 或 iterm2）则返回 True。"""
    return backend_type in ("tmux", "iterm2")
