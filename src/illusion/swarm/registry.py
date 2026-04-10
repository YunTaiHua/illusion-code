"""
后端注册表模块
==============

本模块提供队友执行的后端注册功能。
实现了自动检测和选择最佳可用后端的逻辑。

主要组件：
    - BackendRegistry: 后端注册表类
    - get_backend_registry: 获取全局单例注册表

支持的后端类型：
    - subprocess: 子进程后端（始终可用）
    - in_process: 进程内后端
    - tmux: tmux 终端后端
    - iterm2: iTerm2 终端后端

使用示例：
    >>> from illusion.swarm.registry import get_backend_registry
    >>> 
    >>> # 获取注册表
    >>> registry = get_backend_registry()
    >>> 
    >>> # 自动检测最佳后端
    >>> executor = registry.get_executor()
    >>> 
    >>> # 指定后端
    >>> executor = registry.get_executor("in_process")
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import TYPE_CHECKING, Any

# 导入平台检测和类型定义
from illusion.platforms import get_platform, get_platform_capabilities
from illusion.swarm.spawn_utils import is_tmux_available
from illusion.swarm.types import BackendDetectionResult, BackendType, TeammateExecutor

if TYPE_CHECKING:
    pass

# 配置模块级日志记录器
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 检测辅助函数
# ---------------------------------------------------------------------------


def _detect_tmux() -> bool:
    """返回当前是否在活跃的 tmux 会话中运行。

    检查项：
    1. ``$TMUX`` 环境变量（tmux 为附加客户端设置）。
    2. PATH 上是否有 ``tmux`` 二进制文件。
    """
    if not os.environ.get("TMUX"):
        logger.debug("[BackendRegistry] _detect_tmux: $TMUX not set")
        return False
    if not shutil.which("tmux"):
        logger.debug("[BackendRegistry] _detect_tmux: tmux binary not found on PATH")
        return False
    logger.debug("[BackendRegistry] _detect_tmux: inside tmux session with binary available")
    return True


def _detect_iterm2() -> bool:
    """返回当前是否在 iTerm2 终端中运行。

    检查 ``$ITERM_SESSION_ID``，iTerm2 为每个终端会话设置此变量。
    """
    if os.environ.get("ITERM_SESSION_ID"):
        logger.debug("[BackendRegistry] _detect_iterm2: ITERM_SESSION_ID=%s", os.environ["ITERM_SESSION_ID"])
        return True
    logger.debug("[BackendRegistry] _detect_iterm2: ITERM_SESSION_ID not set")
    return False


def _is_it2_cli_available() -> bool:
    """如果 ``it2`` CLI 已安装（用于 iTerm2 pane 控制）则返回 True。"""
    available = shutil.which("it2") is not None
    logger.debug("[BackendRegistry] _is_it2_cli_available: %s", available)
    return available


def _get_tmux_install_instructions() -> str:
    """返回特定平台的 tmux 安装说明。"""
    system = get_platform()
    if system == "macos":
        return (
            "To use agent swarms, install tmux:\n"
            "  brew install tmux\n"
            "Then start a tmux session with: tmux new-session -s claude"
        )
    elif system in {"linux", "wsl"}:
        return (
            "To use agent swarms, install tmux:\n"
            "  sudo apt install tmux    # Ubuntu/Debian\n"
            "  sudo dnf install tmux    # Fedora/RHEL\n"
            "Then start a tmux session with: tmux new-session -s claude"
        )
    elif system == "windows":
        return (
            "To use agent swarms, you need tmux which requires WSL "
            "(Windows Subsystem for Linux).\n"
            "Install WSL first, then inside WSL run:\n"
            "  sudo apt install tmux\n"
            "Then start a tmux session with: tmux new-session -s claude"
        )
    else:
        return (
            "To use agent swarms, install tmux using your system's package manager.\n"
            "Then start a tmux session with: tmux new-session -s claude"
        )


# ---------------------------------------------------------------------------
# BackendRegistry
# ---------------------------------------------------------------------------


class BackendRegistry:
    """将 BackendType 名称映射到 TeammateExecutor 实例的注册表。

    检测优先级流程（匹配 ``registry.ts``）：
    1. ``in_process`` — 当明确请求或没有 pane 后端可用时。
    2. ``tmux`` — 当在 tmux 会话中且 tmux 二进制文件存在时。
    3. ``subprocess`` — 始终可用作为安全回退。

    使用示例：

        registry = BackendRegistry()
        executor = registry.get_executor()           # 自动检测最佳后端
        executor = registry.get_executor("in_process")  # 明确选择
    """

    def __init__(self) -> None:
        """初始化后端注册表。"""
        # 存储已注册的后端
        self._backends: dict[BackendType, TeammateExecutor] = {}
        # 缓存的检测结果
        self._detected: BackendType | None = None
        self._detection_result: BackendDetectionResult | None = None
        # in-process 回退是否已激活
        self._in_process_fallback_active: bool = False
        # 注册默认后端
        self._register_defaults()

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def register_backend(self, executor: TeammateExecutor) -> None:
        """注册在其声明的 ``type`` 键下的自定义执行器。"""
        self._backends[executor.type] = executor
        logger.debug("Registered backend: %s", executor.type)

    def detect_backend(self) -> BackendType:
        """检测并缓存最 capable 的可用后端。

        检测优先级：
        1. ``in_process`` — 如果之前激活了 in-process 回退。
        2. ``tmux`` — 如果在活跃的 tmux 会话中且 tmux 二进制文件存在。
        3. ``subprocess`` — 始终可用作为安全回退。

        Returns:
            检测到的 :data:`BackendType` 字符串。
        """
        if self._detected is not None:
            logger.debug(
                "[BackendRegistry] Using cached backend detection: %s", self._detected
            )
            return self._detected

        logger.debug("[BackendRegistry] Starting backend detection...")

        # 优先级 1: in-process 回退（之前失败的生成后激活）
        if self._in_process_fallback_active:
            logger.debug(
                "[BackendRegistry] in_process fallback active — selecting in_process"
            )
            self._detected = "in_process"
            self._detection_result = BackendDetectionResult(
                backend="in_process",
                is_native=True,
            )
            return self._detected

        # 优先级 2: tmux（会话内 + 二进制文件可用）
        inside_tmux = _detect_tmux()
        if inside_tmux:
            if "tmux" in self._backends:
                logger.debug("[BackendRegistry] Selected: tmux (running inside tmux session)")
                self._detected = "tmux"
                self._detection_result = BackendDetectionResult(
                    backend="tmux",
                    is_native=True,
                )
                return self._detected
            else:
                logger.debug(
                    "[BackendRegistry] Inside tmux but TmuxBackend not registered — "
                    "falling through to subprocess"
                )

        # 优先级 3: subprocess（始终可用）
        logger.debug("[BackendRegistry] Selected: subprocess (default fallback)")
        self._detected = "subprocess"
        self._detection_result = BackendDetectionResult(
            backend="subprocess",
            is_native=False,
        )
        return self._detected

    def detect_pane_backend(self) -> BackendDetectionResult:
        """检测应使用哪个 pane 后端（tmux / iTerm2）。

        实现与 TypeScript 源文件中 ``detectAndGetBackend()`` 相同的优先级流程：

        1. 如果在 tmux 内，始终使用 tmux。
        2. 如果在 iTerm2 中且 ``it2`` CLI 可用，使用 iTerm2。
        3. 如果在 iTerm2 中没有 ``it2`` 但 tmux 可用，使用 tmux。
        4. 如果在 iTerm2 中没有 tmux，抛出设置说明。
        5. 如果 tmux 二进制文件可用（外部会话），使用 tmux。
        6. 否则抛出平台特定安装说明。

        Returns:
            描述所选 pane 后端的 :class:`BackendDetectionResult`。

        Raises:
            RuntimeError: 当没有 pane 后端可用时。
        """
        logger.debug("[BackendRegistry] Starting pane backend detection...")

        in_tmux = _detect_tmux()
        in_iterm2 = _detect_iterm2()

        logger.debug(
            "[BackendRegistry] Environment: in_tmux=%s, in_iterm2=%s",
            in_tmux,
            in_iterm2,
        )

        # 优先级 1: 在 tmux 内 —— 始终使用 tmux
        if in_tmux:
            logger.debug("[BackendRegistry] Selected pane backend: tmux (inside tmux session)")
            return BackendDetectionResult(backend="tmux", is_native=True)

        # 优先级 2: 在 iTerm2 中，尝试原生 panes
        if in_iterm2:
            it2_available = _is_it2_cli_available()
            logger.debug(
                "[BackendRegistry] iTerm2 detected, it2 CLI available: %s", it2_available
            )

            if it2_available:
                logger.debug("[BackendRegistry] Selected pane backend: iterm2 (native with it2 CLI)")
                return BackendDetectionResult(backend="iterm2", is_native=True)

            # it2 不可用 —— 能回退到 tmux 吗？
            tmux_bin = is_tmux_available()
            logger.debug(
                "[BackendRegistry] it2 not available, tmux binary available: %s", tmux_bin
            )

            if tmux_bin:
                logger.debug(
                    "[BackendRegistry] Selected pane backend: tmux (fallback in iTerm2, "
                    "it2 setup recommended)"
                )
                return BackendDetectionResult(
                    backend="tmux",
                    is_native=False,
                    needs_setup=True,
                )

            logger.debug(
                "[BackendRegistry] ERROR: in iTerm2 but no it2 CLI and no tmux"
            )
            raise RuntimeError(
                "iTerm2 detected but it2 CLI not installed.\n"
                "Install it2 with: pip install it2"
            )

        # 优先级 3: 不在 tmux 或 iTerm2 中 —— 如果 tmux 可用则使用 tmux 外部会话模式
        tmux_bin = is_tmux_available()
        logger.debug(
            "[BackendRegistry] Not in tmux or iTerm2, tmux binary available: %s", tmux_bin
        )

        if tmux_bin:
            logger.debug("[BackendRegistry] Selected pane backend: tmux (external session mode)")
            return BackendDetectionResult(backend="tmux", is_native=False)

        # 没有可用的 pane 后端
        logger.debug("[BackendRegistry] ERROR: No pane backend available")
        raise RuntimeError(_get_tmux_install_instructions())

    def get_executor(self, backend: BackendType | None = None) -> TeammateExecutor:
        """返回给定后端类型的 TeammateExecutor。

        Args:
            backend: 要使用的明确后端类型。当为 *None* 时注册表
                     自动检测最佳可用后端。

        Returns:
            已注册的 :class:`~illusion.swarm.types.TeammateExecutor`。

        Raises:
            KeyError: 如果请求的后端未注册。
        """
        resolved = backend or self.detect_backend()
        executor = self._backends.get(resolved)
        if executor is None:
            available = list(self._backends.keys())
            raise KeyError(
                f"Backend {resolved!r} is not registered. Available: {available}"
            )
        return executor

    def get_preferred_backend(self, config: dict | None = None) -> BackendType:
        """从设置/配置返回用户首选的后端。

        当没有明确偏好时回退到自动检测。

        Args:
            config: 可选的设置字典。如果存在，读取 ``teammate_mode`` 键
                    （值：``"auto"``, ``"in_process"``, ``"tmux"``）。

        Returns:
            解析的 :data:`BackendType`。
        """
        if config:
            mode = config.get("teammate_mode", "auto")
        else:
            mode = os.environ.get("ILLUSION_TEAMMATE_MODE", "auto")

        logger.debug("[BackendRegistry] get_preferred_backend: mode=%s", mode)

        if mode == "in_process":
            return "in_process"
        elif mode == "tmux":
            return "tmux"
        else:
            # "auto" — 继续进行检测
            return self.detect_backend()

    def mark_in_process_fallback(self) -> None:
        """记录生成回退到 in-process 模式。

        当没有 pane 后端可用时调用。在此之后，
        ``get_executor()`` 将在进程生命周期内继续返回 in-process 后端
        （环境不会在会话中间改变）。
        """
        logger.debug("[BackendRegistry] Marking in-process fallback as active")
        self._in_process_fallback_active = True
        # 使缓存的检测失效，以便下次调用重新检测
        self._detected = None
        self._detection_result = None

    def get_cached_detection_result(self) -> BackendDetectionResult | None:
        """返回缓存的 :class:`BackendDetectionResult`，如果尚未检测则返回 *None*。"""
        return self._detection_result

    def available_backends(self) -> list[BackendType]:
        """返回已注册的后端类型排序列表。"""
        return sorted(self._backends.keys())  # type: ignore[return-value]

    def health_check(self) -> dict[str, Any]:
        """检查所有已注册后端的健康状态。

        Returns:
            包含 backend_name -> {available: bool, type: str} 映射的字典，
            加上可用后端的 total_count。
        """
        results: dict[str, dict[str, Any]] = {}
        available_count = 0

        for backend_type, executor in self._backends.items():
            is_available = executor.is_available()
            results[backend_type] = {
                "available": is_available,
                "type": str(executor.type),
            }
            if is_available:
                available_count += 1

        return {
            "backends": results,
            "total_count": available_count,
        }

    def reset(self) -> None:
        """清除检测缓存并重新注册默认后端。

        旨在用于测试 —— 允许在环境更改后重新检测。
        """
        self._detected = None
        self._detection_result = None
        self._in_process_fallback_active = False
        self._backends.clear()
        self._register_defaults()

    # ------------------------------------------------------------------
    # 内部辅助函数
    # ------------------------------------------------------------------

    def _register_defaults(self) -> None:
        """注册无条件可用的内置后端。"""
        # 导入子进程后端
        from illusion.swarm.subprocess_backend import SubprocessBackend

        # 注册子进程后端（始终可用）
        self._backends["subprocess"] = SubprocessBackend()
        # 如果支持 swarm mailbox，则注册 in-process 后端
        if get_platform_capabilities().supports_swarm_mailbox:
            from illusion.swarm.in_process import InProcessBackend

            self._backends["in_process"] = InProcessBackend()

        # Tmux 后端注册延迟到实现存在时。
        # 如果 TmuxBackend 可用，可以通过 register_backend() 注册。


# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

_registry: BackendRegistry | None = None


def get_backend_registry() -> BackendRegistry:
    """返回进程级单例 BackendRegistry。"""
    global _registry
    if _registry is None:
        _registry = BackendRegistry()
    return _registry


def mark_in_process_fallback() -> None:
    """模块级便捷函数：在单例注册表上标记 in-process 回退。"""
    get_backend_registry().mark_in_process_fallback()
