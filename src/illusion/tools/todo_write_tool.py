"""
TODO写入工具模块
================

本模块提供项目TODO文件维护功能。

主要功能：
    - 创建和管理结构化任务列表
    - 跟踪当前编码会话的进度
    - 展示任务的整体进度给用户

类说明：
    - TodoWriteToolInput: TODO写入工具输入参数
    - TodoWriteTool: TODO写入工具类

使用示例：
    >>> # 创建一个新的TODO项
    >>> item = "实现用户认证功能"
    >>> # 工具自动在当前目录创建TODO.md文件
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class TodoItem(BaseModel):
    """TODO项数据模型
    
    Attributes:
        content: 任务描述（祈使形式）
        status: 任务状态（pending/in_progress/completed）
        activeForm: 执行时显示的进行时形式
    """

    content: str = Field(min_length=1)
    status: str = Field(pattern=r"^(pending|in_progress|completed)$")
    activeForm: str = Field(min_length=1)


class TodoWriteToolInput(BaseModel):
    """TODO写入工具的参数模型
    
    Attributes:
        todos: TODO项列表，每项包含content/status/activeForm
    """

    todos: list[TodoItem] = Field(description="List of todo items to update")


class TodoWriteTool(BaseTool):
    """向TODO markdown文件追加条目
    
    使用此工具创建和管理当前编码会话的结构化任务列表。
    这有助于您跟踪进度、组织复杂任务，并展示给用户您的周到性。
    它还帮助用户了解任务进度和整体请求进度。

    何时使用此工具：
    在以下场景中主动使用此工具：

    1. 复杂的多步骤任务 - 当任务需要3个或更多不同步骤或操作时
    2. 非平凡和复杂的任务 - 需要仔细规划或多个操作的任务
    3. 用户明确请求TODO列表 - 当用户直接要求您使用TODO列表时
    4. 用户提供多个任务 - 当用户提供要做的事情列表时（用数字或逗号分隔）
    5. 收到新指令后 - 立即将用户需求捕获为TODO
    6. 开始任务时 - 在开始工作之前将其标记为in_progress。理想情况下，您应该一次只有一个TODO为in_progress
    7. 完成任务后 - 立即将其标记为completed，并在实施过程中添加发现的新后续任务

    何时不使用此工具：

    仅对简单任务跳过使用此工具：
    - 只有单一、直接的任务
    - 任务 trivial，跟踪它没有组织好处
    - 任务可以在3个简单步骤内完成
    - 任务纯粹是对话式或信息性的

    注意：如果只有一个简单的任务要处理，您不应该使用此工具。
    在这种情况下，您最好直接完成任务。

    任务状态和管理：

    1. **任务状态**：使用这些状态跟踪进度：
       - pending: 任务尚未开始
       - in_progress: 当前正在处理（一次限制为一个任务）
       - completed: 任务成功完成

       **重要**：任务描述必须有两种形式：
       - content: 描述需要做什么的祈使形式（例如，"运行测试"、"构建项目"）
       - activeForm: 执行期间显示的现在进行时形式（例如，"正在运行测试"、"正在构建项目"）

    2. **任务管理**：
       - 工作时实时更新任务状态
       - 完成后立即标记任务（不要批量完成）
       - 任何时候必须恰好有一个任务为in_progress（不少于，也不多于）
       - 在开始新任务之前完成当前任务
       - 从列表中完全删除不再相关的任务

    3. **任务完成要求**：
       - 仅在完全完成时才将任务标记为completed
       - 如果遇到错误、阻塞或无法完成，请保持任务为in_progress
       - 被阻塞时，创建描述需要解决的新任务
       - 永远不要将任务标记为completed如果：
         - 测试失败
         - 实现不完整
         - 遇到未解决的错误
         - 找不到必要的文件或依赖

    4. **任务分解**：
       - 创建具体、可操作的项目
       - 将复杂任务分解为更小、可管理的步骤
       - 使用清晰、描述性的任务名称
       - 始终提供两种形式：
         - content: "修复认证bug"
         - activeForm: "正在修复认证bug"

    如有疑问，请使用此工具。主动的任务管理展示 attentive 并确保您成功完成所有要求。
    """

    name = "todo_write"
    description = """Use this tool to create and manage a structured task list for your current coding session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
It also helps the user understand the progress of the task and overall progress of their requests.

## When to Use This Tool
Use this tool proactively in these scenarios:

1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
3. User explicitly requests todo list - When the user directly asks you to use the todo list
4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
5. After receiving new instructions - Immediately capture user requirements as todos
6. When you start working on a task - Mark it as in_progress BEFORE beginning work. Ideally you should only have one todo as in_progress at a time
7. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation

## When NOT to Use This Tool

Skip using this tool when:
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no organizational benefit
3. The task can be completed in less than 3 trivial steps
4. The task is purely conversational or informational

NOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly.

## Task States and Management

1. **Task States**: Use these states to track progress:
   - pending: Task not yet started
   - in_progress: Currently working on (limit to ONE task at a time)
   - completed: Task finished successfully

   **IMPORTANT**: Task descriptions must have two forms:
   - content: The imperative form describing what needs to be done (e.g., "Run tests", "Build the project")
   - activeForm: The present continuous form shown during execution (e.g., "Running tests", "Building the project")

2. **Task Management**:
   - Update task status in real-time as you work
   - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
   - Exactly ONE task must be in_progress at any time (not less, not more)
   - Complete current tasks before starting new ones
   - Remove tasks that are no longer relevant from the list entirely

3. **Task Completion Requirements**:
   - ONLY mark a task as completed when you have FULLY accomplished it
   - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
   - When blocked, create a new task describing what needs to be resolved
   - Never mark a task as completed if:
     - Tests are failing
     - Implementation is partial
     - You encountered unresolved errors
     - You couldn't find necessary files or dependencies

4. **Task Breakdown**:
   - Create specific, actionable items
   - Break complex tasks into smaller, manageable steps
   - Use clear, descriptive task names
   - Always provide both forms:
     - content: "Fix authentication bug"
     - activeForm: "Fixing authentication bug"

When in doubt, use this tool. Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully."""
    input_model = TodoWriteToolInput

    async def execute(self, arguments: TodoWriteToolInput, context: ToolExecutionContext) -> ToolResult:
        """执行TODO写入操作
        
        Args:
            arguments: 工具输入参数
            context: 工具执行上下文
        
        Returns:
            ToolResult: 执行结果
        """
        todos_data = [item.model_dump() for item in arguments.todos]
        all_done = all(item.status == "completed" for item in arguments.todos)
        if all_done and len(arguments.todos) >= 1:
            todos_data = []
        return ToolResult(output="Todos updated", metadata={"todos": todos_data})