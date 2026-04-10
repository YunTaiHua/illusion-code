"""
钩子加载器模块
==============

本模块提供从设置和插件加载钩子注册表的功能。

主要功能：
    - HookRegistry: 按事件分组存储钩子
    - load_hook_registry: 从设置对象加载钩子注册表

使用示例：
    >>> from illusion.hooks.loader import HookRegistry, load_hook_registry
    >>> registry = load_hook_registry(settings, plugins)
"""

from __future__ import annotations

from collections import defaultdict
from illusion.hooks.events import HookEvent
from illusion.hooks.schemas import HookDefinition


class HookRegistry:
    """
    钩子注册表
    
    按事件类型分组存储钩子定义，支持注册、获取和摘要生成。
    
    Attributes:
        _hooks: 事件到钩子列表的映射字典
    
    使用示例：
        >>> registry = HookRegistry()
        >>> registry.register(HookEvent.PRE_TOOL_USE, hook_def)
        >>> hooks = registry.get(HookEvent.PRE_TOOL_USE)
    """

    def __init__(self) -> None:
        # 初始化钩子字典，使用 defaultdict 自动创建空列表
        self._hooks: dict[HookEvent, list[HookDefinition]] = defaultdict(list)

    def register(self, event: HookEvent, hook: HookDefinition) -> None:
        """
        注册一个钩子
        
        Args:
            event: 钩子触发事件
            hook: 钩子定义
        """
        # 将钩子添加到对应事件的列表中
        self._hooks[event].append(hook)

    def get(self, event: HookEvent) -> list[HookDefinition]:
        """
        获取指定事件的所有钩子
        
        Args:
            event: 钩子触发事件
        
        Returns:
            list[HookDefinition]: 钩子定义列表
        """
        # 返回事件对应的钩子列表的副本
        return list(self._hooks.get(event, []))

    def summary(self) -> str:
        """
        生成人类可读的钩子摘要
        
        Returns:
            str: 格式化的钩子摘要字符串
        """
        lines: list[str] = []  # 存储摘要行
        # 遍历所有事件类型
        for event in HookEvent:
            hooks = self.get(event)  # 获取事件对应的钩子
            if not hooks:
                continue  # 跳过没有钩子的事件
            lines.append(f"{event.value}:")  # 添加事件名称
            # 遍历每个钩子
            for hook in hooks:
                # 获取匹配器属性
                matcher = getattr(hook, "matcher", None)
                # 获取详情属性（command/prompt/url 之一）
                detail = getattr(hook, "command", None) or getattr(hook, "prompt", None) or getattr(hook, "url", None) or ""
                suffix = f" matcher={matcher}" if matcher else ""  # 匹配器后缀
                lines.append(f"  - {hook.type}{suffix}: {detail}")  # 添加钩子详情
        return "\n".join(lines)  # 拼接所有行


def load_hook_registry(settings, plugins=None) -> HookRegistry:
    """
    从设置对象加载钩子注册表
    
    从主设置和插件中收集钩子定义，构建完整的注册表。
    
    Args:
        settings: 包含 hooks 属性的设置对象
        plugins: 可选的插件列表
    
    Returns:
        HookRegistry: 加载完成的钩子注册表
    
    使用示例：
        >>> registry = load_hook_registry(settings, plugins)
    """
    registry = HookRegistry()  # 创建新的注册表实例
    
    # 遍历设置中的钩子配置
    for raw_event, hooks in settings.hooks.items():
        try:
            # 尝试将字符串转换为 HookEvent 枚举
            event = HookEvent(raw_event)
        except ValueError:
            continue  # 跳过无效的事件名称
        # 遍历事件中的钩子定义并注册
        for hook in hooks:
            registry.register(event, hook)
    
    # 遍历插件中的钩子配置
    for plugin in plugins or []:
        if not plugin.enabled:
            continue  # 跳过未启用的插件
        # 遍历插件的钩子配置
        for raw_event, hooks in plugin.hooks.items():
            try:
                event = HookEvent(raw_event)
            except ValueError:
                continue  # 跳过无效的事件名称
            for hook in hooks:
                registry.register(event, hook)
    
    return registry  # 返回加载完成的注册表