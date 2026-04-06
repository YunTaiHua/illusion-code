"""Built-in tool registration."""

from illusion.tools.ask_user_question_tool import AskUserQuestionTool
from illusion.tools.agent_tool import AgentTool
from illusion.tools.bash_tool import BashTool
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolRegistry, ToolResult
from illusion.tools.brief_tool import BriefTool
from illusion.tools.config_tool import ConfigTool
from illusion.tools.cron_create_tool import CronCreateTool
from illusion.tools.cron_delete_tool import CronDeleteTool
from illusion.tools.cron_list_tool import CronListTool
from illusion.tools.cron_toggle_tool import CronToggleTool
from illusion.tools.enter_plan_mode_tool import EnterPlanModeTool
from illusion.tools.enter_worktree_tool import EnterWorktreeTool
from illusion.tools.exit_plan_mode_tool import ExitPlanModeTool
from illusion.tools.exit_worktree_tool import ExitWorktreeTool
from illusion.tools.file_edit_tool import FileEditTool
from illusion.tools.file_read_tool import FileReadTool
from illusion.tools.file_write_tool import FileWriteTool
from illusion.tools.glob_tool import GlobTool
from illusion.tools.grep_tool import GrepTool
from illusion.tools.list_mcp_resources_tool import ListMcpResourcesTool
from illusion.tools.lsp_tool import LspTool
from illusion.tools.mcp_auth_tool import McpAuthTool
from illusion.tools.mcp_tool import McpToolAdapter
from illusion.tools.notebook_edit_tool import NotebookEditTool
from illusion.tools.read_mcp_resource_tool import ReadMcpResourceTool
from illusion.tools.remote_trigger_tool import RemoteTriggerTool
from illusion.tools.send_message_tool import SendMessageTool
from illusion.tools.skill_tool import SkillTool
from illusion.tools.sleep_tool import SleepTool
from illusion.tools.task_create_tool import TaskCreateTool
from illusion.tools.task_get_tool import TaskGetTool
from illusion.tools.task_list_tool import TaskListTool
from illusion.tools.task_output_tool import TaskOutputTool
from illusion.tools.task_stop_tool import TaskStopTool
from illusion.tools.task_update_tool import TaskUpdateTool
from illusion.tools.team_create_tool import TeamCreateTool
from illusion.tools.team_delete_tool import TeamDeleteTool
from illusion.tools.todo_write_tool import TodoWriteTool
from illusion.tools.tool_search_tool import ToolSearchTool
from illusion.tools.web_fetch_tool import WebFetchTool
from illusion.tools.web_search_tool import WebSearchTool


def create_default_tool_registry(mcp_manager=None) -> ToolRegistry:
    """Return the default built-in tool registry."""
    registry = ToolRegistry()
    for tool in (
        BashTool(),
        AskUserQuestionTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        NotebookEditTool(),
        LspTool(),
        McpAuthTool(),
        GlobTool(),
        GrepTool(),
        SkillTool(),
        ToolSearchTool(),
        WebFetchTool(),
        WebSearchTool(),
        ConfigTool(),
        BriefTool(),
        SleepTool(),
        EnterWorktreeTool(),
        ExitWorktreeTool(),
        TodoWriteTool(),
        EnterPlanModeTool(),
        ExitPlanModeTool(),
        CronCreateTool(),
        CronListTool(),
        CronDeleteTool(),
        CronToggleTool(),
        RemoteTriggerTool(),
        TaskCreateTool(),
        TaskGetTool(),
        TaskListTool(),
        TaskStopTool(),
        TaskOutputTool(),
        TaskUpdateTool(),
        AgentTool(),
        SendMessageTool(),
        TeamCreateTool(),
        TeamDeleteTool(),
    ):
        registry.register(tool)
    if mcp_manager is not None:
        registry.register(ListMcpResourcesTool(mcp_manager))
        registry.register(ReadMcpResourceTool(mcp_manager))
        for tool_info in mcp_manager.list_tools():
            registry.register(McpToolAdapter(mcp_manager, tool_info))
    return registry


__all__ = [
    "BaseTool",
    "ToolExecutionContext",
    "ToolRegistry",
    "ToolResult",
    "create_default_tool_registry",
]
