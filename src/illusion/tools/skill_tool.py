"""
技能内容读取工具
================

本模块提供读取已加载技能内容的功能，用于执行斜杠命令和自定义技能。

主要组件：
    - SkillTool: 读取技能内容的工具

使用示例：
    >>> from illusion.tools import SkillTool
    >>> tool = SkillTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.skills import load_skill_registry
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class SkillToolInput(BaseModel):
    """技能查找参数。

    属性：
        name: 技能名称
        args: 技能的可选参数
    """

    name: str = Field(description="Skill name")
    args: str | None = Field(default=None, description="Optional arguments for the skill")


class SkillTool(BaseTool):
    """返回已加载技能的内容。

    用于执行斜杠命令（/command）或调用自定义技能。
    """

    name = "skill"
    description = """Execute a skill within the main conversation

When users ask you to perform tasks, check if any of the available skills match. Skills provide specialized capabilities and domain knowledge.

When users reference a "slash command" or "/<something>" (e.g., "/commit", "/review-pr"), they are referring to a skill. Use this tool to invoke it.

How to invoke:
- Use this tool with the skill name and optional arguments
- Examples:
  - `skill: "pdf"` - invoke the pdf skill
  - `skill: "commit", args: "-m 'Fix bug'"` - invoke with arguments
  - `skill: "review-pr", args: "123"` - invoke with arguments
  - `skill: "ms-office-suite:pdf"` - invoke using fully qualified name

Important:
- Available skills are listed in system-reminder messages in the conversation
- When a skill matches the user's request, this is a BLOCKING REQUIREMENT: invoke the relevant Skill tool BEFORE generating any other response about the task
- NEVER mention a skill without actually calling this tool
- Do not invoke a skill that is already running
- Do not use this tool for built-in CLI commands (like /help, /clear, etc.)
- If you see a <command-name> tag in the current conversation turn, the skill has ALREADY been loaded - follow the instructions directly instead of calling this tool again"""
    input_model = SkillToolInput

    def is_read_only(self, arguments: SkillToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: SkillToolInput, context: ToolExecutionContext) -> ToolResult:
        # 加载技能注册表
        registry = load_skill_registry(context.cwd)
        # 尝试多种名称格式匹配
        skill = registry.get(arguments.name) or registry.get(arguments.name.lower()) or registry.get(arguments.name.title())
        if skill is None:
            return ToolResult(output=f"Skill not found: {arguments.name}", is_error=True)

        # 获取技能内容
        content = skill.content
        # 如果提供了参数，替换 $ARGUMENTS 占位符
        if arguments.args and "$ARGUMENTS" in content:
            content = content.replace("$ARGUMENTS", arguments.args)

        return ToolResult(output=content)
