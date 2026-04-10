"""
工具抽象模块
============

本模块提供 IllusionCode 工具系统的抽象基类和注册表。

主要组件：
    - BaseTool: 所有工具的抽象基类
    - ToolExecutionContext: 工具执行的共享上下文
    - ToolResult: 标准化的工具执行结果
    - ToolRegistry: 工具名称到实现的映射

使用示例：
    >>> from illusion.tools.base import BaseTool, ToolRegistry, ToolResult
    >>> registry = ToolRegistry()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel


@dataclass
class ToolExecutionContext:
    """工具调用的共享执行上下文
    
    Attributes:
        cwd: 当前工作目录
        metadata: 元数据字典
    """

    cwd: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """标准化的工具执行结果
    
    Attributes:
        output: 输出内容
        is_error: 是否为错误
        metadata: 元数据字典
    """

    output: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """所有 IllusionCode 工具的基类
    
    Attributes:
        name: 工具名称
        description: 工具描述
        input_model: 输入模型类型
    """

    name: str
    description: str
    input_model: type[BaseModel]

    @abstractmethod
    async def execute(self, arguments: BaseModel, context: ToolExecutionContext) -> ToolResult:
        """执行工具
        
        Args:
            arguments: 输入参数模型
            context: 执行上下文
        
        Returns:
            ToolResult: 工具执行结果
        """

    def is_read_only(self, arguments: BaseModel) -> bool:
        """返回调用是否为只读
        
        Args:
            arguments: 输入参数模型
        
        Returns:
            bool: 是否只读
        """
        del arguments
        return False

    def to_api_schema(self) -> dict[str, Any]:
        """返回 Anthropic Messages API 期望的工具模式
        
        Returns:
            dict[str, Any]: API 工具模式
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }


class ToolRegistry:
    """工具名称到实现的映射
    
    Attributes:
        _tools: 工具字典
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具实例
        
        Args:
            tool: 工具实例
        """
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """按名称返回已注册的工具
        
        Args:
            name: 工具名称
        
        Returns:
            BaseTool | None: 工具或 None
        """
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """返回所有已注册的工具
        
        Returns:
            list[BaseTool]: 工具列表
        """
        return list(self._tools.values())

    def to_api_schema(self) -> list[dict[str, Any]]:
        """以 API 格式返回所有工具模式
        
        Returns:
            list[dict[str, Any]]: API 工具模式列表
        """
        return [tool.to_api_schema() for tool in self._tools.values()]
