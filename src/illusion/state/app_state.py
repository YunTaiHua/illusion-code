"""
应用状态模块
===========

本模块定义 IllusionCode 应用状态数据模型。

主要功能：
    - 定义共享的UI/会话状态数据结构
    - 支持状态属性的不可变更新

类说明：
    - AppState: 应用状态数据类

使用示例：
    >>> from illusion.state import AppState
    >>> state = AppState(model="claude-3-5-sonnet-20241022", permission_mode="default")
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppState:
    """共享的可变UI/会话状态数据类
    
    Attributes:
        model: 当前使用的模型名称
        permission_mode: 权限模式 (default/plan/bypassPermissions 等)
        ui_language: UI语言 (默认 zh-CN)
        cwd: 当前工作目录
        provider: API提供者名称
        auth_status: 认证状态
        base_url: API基础URL
        fast_mode: 是否启用快速模式
        effort: 推理 Effort 级别 (low/medium/high)
        passes: 推理通过次数
        mcp_connected: 已连接的MCP服务器数量
        mcp_failed: 失败的MCP服务器数量
        bridge_sessions: 活跃的桥接会话数量
        output_style: 输出样式名称
        phase: 会话阶段 (idle/thinking/tool_executing)
    """

    model: str  # 模型名称
    permission_mode: str  # 权限模式
    ui_language: str = "zh-CN"  # UI语言
    cwd: str = "."  # 当前工作目录
    provider: str = "unknown"  # API提供者
    auth_status: str = "missing"  # 认证状态
    base_url: str = ""  # API基础URL
    fast_mode: bool = False  # 快速模式标志
    effort: str = "medium"  # 推理 Effort 级别
    passes: int = 1  # 推理通过次数
    mcp_connected: int = 0  # 已连接的MCP服务器数量
    mcp_failed: int = 0  # 失败的MCP服务器数量
    bridge_sessions: int = 0  # 活跃的桥接会话数量
    output_style: str = "default"  # 输出样式名称
    phase: str = "idle"  # 会话阶段: idle / thinking / tool_executing