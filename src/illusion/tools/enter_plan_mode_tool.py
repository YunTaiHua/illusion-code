"""
进入计划模式工具模块
====================

本模块提供进入计划权限模式的工具。

主要功能：
    - 切换设置权限模式为计划模式
    - 允许在编写代码前探索代码库并设计实现方案

类说明：
    - EnterPlanModeToolInput: 工具输入模型（无操作）
    - EnterPlanModeTool: 进入计划模式工具

使用示例：
    >>> # 工具自动由系统调用，用户批准后进入计划模式
"""

from __future__ import annotations

from pydantic import BaseModel

from illusion.config.settings import load_settings, save_settings
from illusion.permissions import PermissionMode
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class EnterPlanModeToolInput(BaseModel):
    """无操作输入模型
    
    此工具不需要任何输入参数。
    """


class EnterPlanModeTool(BaseTool):
    """切换设置权限模式为计划模式
    
    此工具用于在开始非平凡的实现任务之前主动使用。
    获得用户对方法的批准可以防止浪费精力并确保一致性。
    此工具将您转换到计划模式，在那里您可以探索代码库并设计实现方案以供用户批准。

    何时使用此工具：
    - 新功能实现时
    - 有多种有效方法时
    - 需要修改代码时
    - 需要架构决策时
    - 可能涉及多个文件时
    - 需求不清晰时
    - 用户偏好很重要时
    """

    name = "enter_plan_mode"
    description = """Use this tool proactively when you're about to start a non-trivial implementation task. Getting user sign-off on your approach before writing code prevents wasted effort and ensures alignment. This tool transitions you into plan mode where you can explore the codebase and design an implementation approach for user approval.

## When to Use This Tool

**Prefer using EnterPlanMode** for implementation tasks unless they're simple. Use it when ANY of these conditions apply:

1. **New Feature Implementation**: Adding meaningful new functionality
   - Example: "Add a logout button" - where should it go? What should happen on click?
   - Example: "Add form validation" - what rules? What error messages?

2. **Multiple Valid Approaches**: The task can be solved in several different ways
   - Example: "Add caching to the API" - could use Redis, in-memory, file-based, etc.
   - Example: "Improve performance" - many optimization strategies possible

3. **Code Modifications**: Changes that affect existing behavior or structure
   - Example: "Update the login flow" - what exactly should change?
   - Example: "Refactor this component" - what's the target architecture?

4. **Architectural Decisions**: The task requires choosing between patterns or technologies
   - Example: "Add real-time updates" - WebSockets vs SSE vs polling
   - Example: "Implement state management" - Redux vs Context vs custom solution

5. **Multi-File Changes**: The task will likely touch more than 2-3 files
   - Example: "Refactor the authentication system"
   - Example: "Add a new API endpoint with tests"

6. **Unclear Requirements**: You need to explore before understanding the full scope
   - Example: "Make the app faster" - need to profile and identify bottlenecks
   - Example: "Fix the bug in checkout" - need to investigate root cause

7. **User Preferences Matter**: The implementation could reasonably go multiple ways
   - If you would use AskUserQuestion to clarify the approach, use EnterPlanMode instead
   - Plan mode lets you explore first, then present options with context

## When NOT to Use This Tool

Only skip EnterPlanMode for simple tasks:
- Single-line or few-line fixes (typos, obvious bugs, small tweaks)
- Adding a single function with clear requirements
- Tasks where the user has given very specific, detailed instructions
- Pure research/exploration tasks (use the Agent tool with explore agent instead)

## What Happens in Plan Mode

In plan mode, you'll:
1. Thoroughly explore the codebase using Glob, Grep, and Read tools
2. Understand existing patterns and architecture
3. Design an implementation approach
4. Present your plan to the user for approval
5. Use AskUserQuestion if you need to clarify approaches
6. Exit plan mode with ExitPlanMode when ready to implement

## Examples

### GOOD - Use EnterPlanMode:
User: "Add user authentication to the app"
- Requires architectural decisions (session vs JWT, where to store tokens, middleware structure)

User: "Optimize the database queries"
- Multiple approaches possible, need to profile first, significant impact

User: "Implement dark mode"
- Architectural decision on theme system, affects many components

User: "Add a delete button to the user profile"
- Seems simple but involves: where to place it, confirmation dialog, API call, error handling, state updates

User: "Update the error handling in the API"
- Affects multiple files, user should approve the approach

### BAD - Don't use EnterPlanMode:
User: "Fix the typo in the README"
- Straightforward, no planning needed

User: "Add a console.log to debug this function"
- Simple, obvious implementation

User: "What files handle routing?"
- Research task, not implementation planning

## Important Notes

- This tool REQUIRES user approval - they must consent to entering plan mode
- If unsure whether to use it, err on the side of planning - it's better to get alignment upfront than to redo work
- Users appreciate being consulted before significant changes are made to their codebase"""
    input_model = EnterPlanModeToolInput

    async def execute(self, arguments: EnterPlanModeToolInput, context: ToolExecutionContext) -> ToolResult:
        # 删除未使用的参数
        del arguments, context
        # 加载设置并将权限模式切换为计划模式
        settings = load_settings()
        settings.permission.mode = PermissionMode.PLAN
        save_settings(settings)
        return ToolResult(output="Permission mode set to plan")
