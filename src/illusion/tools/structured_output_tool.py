"""
结构化输出工具
=============

本模块提供以模式验证的 JSON 格式返回最终响应的功能。

主要组件：
    - StructuredOutputTool: 结构化输出工具

使用示例：
    >>> from illusion.tools import StructuredOutputTool
    >>> tool = StructuredOutputTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class StructuredOutputToolInput(BaseModel):
    """任意结构化 payload。

    属性：
        structured_output: 结构化输出 payload
    """

    structured_output: dict[str, object] = Field(
        default_factory=dict,
        description="Structured output payload",
    )


class StructuredOutputTool(BaseTool):
    """以结构化 JSON 形式返回最终响应。

    用于按照请求的格式返回结构化输出。
    """

    name = "structured_output"
    description = """Use this tool to return your final response in the requested structured format. You MUST call this tool exactly once at the end of your response to provide the structured output."""
    input_model = StructuredOutputToolInput

    def is_read_only(self, arguments: StructuredOutputToolInput) -> bool:
        del arguments
        return True

    async def execute(
        self,
        arguments: StructuredOutputToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        return ToolResult(output="Structured output provided successfully", metadata=arguments.model_dump(mode="json"))
