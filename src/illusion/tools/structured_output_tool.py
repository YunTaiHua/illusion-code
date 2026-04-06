"""Structured output tool for schema-validated final responses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class StructuredOutputToolInput(BaseModel):
    """Arbitrary structured payload from the model."""

    structured_output: dict[str, object] = Field(
        default_factory=dict,
        description="Structured output payload",
    )


class StructuredOutputTool(BaseTool):
    """Return final response in structured JSON form."""

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
