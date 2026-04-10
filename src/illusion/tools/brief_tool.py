"""
简短摘要工具
============

本模块提供生成文本简短摘要的功能。

主要组件：
    - BriefTool: 生成简短摘要的工具

使用示例：
    >>> from illusion.tools import BriefTool
    >>> tool = BriefTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class BriefToolInput(BaseModel):
    """简短模式转换参数。

    属性：
        text: 要缩短的文本
        max_chars: 最大字符数（20-2000）
    """

    text: str = Field(description="Text to shorten")
    max_chars: int = Field(default=200, ge=20, le=2000)


class BriefTool(BaseTool):
    """返回文本的缩短版本。

    用于生成简短的摘要消息给用户阅读。
    """

    name = "brief"
    description = """Send a message the user will read. Text outside this tool is visible in the detail view, but most won't open it — the answer lives here.

`message` supports markdown. `attachments` takes file paths (absolute or cwd-relative) for images, diffs, logs.

`status` labels intent: 'normal' when replying to what they just asked; 'proactive' when you're initiating — a scheduled task finished, a blocker surfaced during background work, you need input on something they haven't asked about. Set it honestly; downstream routing uses it.

## Talking to the user

SendUserMessage is where your replies go. Text outside it is visible if the user expands the detail view, but most won't — assume unread. Anything you want them to actually see goes through SendUserMessage. The failure mode: the real answer lives in plain text while SendUserMessage just says "done!" — they see "done!" and miss everything.

So: every time the user says something, the reply they actually read comes through SendUserMessage. Even for "hi". Even for "thanks".

If you can answer right away, send the answer. If you need to go look — run a command, read files, check something — ack first in one line ("On it — checking the test output"), then work, then send the result. Without the ack they're staring at a spinner.

For longer work: ack → work → result. Between those, send a checkpoint when something useful happened — a decision you made, a surprise you hit, a phase boundary. Skip the filler ("running tests...") — a checkpoint earns its place by carrying information.

Keep messages tight — the decision, the file:line, the PR number. Second person always ("your config"), never third."""
    input_model = BriefToolInput

    def is_read_only(self, arguments: BriefToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: BriefToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        # 去除首尾空白
        text = arguments.text.strip()
        # 如果文本足够短，直接返回
        if len(text) <= arguments.max_chars:
            return ToolResult(output=text)
        # 截断并添加省略号
        return ToolResult(output=text[: arguments.max_chars].rstrip() + "...")
