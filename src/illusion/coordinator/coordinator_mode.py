"""
协调器模式检测与编排支持模块
==========================

本模块提供协调器模式检测、团队管理和任务通知功能。

主要功能：
    - 协调器模式检测与切换
    - 团队注册表管理
    - 任务通知XML序列化/反序列化
    - 协调器系统提示词构建

类说明：
    - TeamRecord: 轻量级内存团队记录
    - TeamRegistry: 团队和代理成员关系存储
    - TaskNotification: 已完成任务的结果结构
    - WorkerConfig: 工作进程代理配置

函数说明：
    - is_coordinator_mode: 检测是否在协调器模式
    - get_team_registry: 获取团队注册表
    - format_task_notification: 序列化任务通知为XML
    - parse_task_notification: 从XML解析任务通知

使用示例：
    >>> from illusion.coordinator import is_coordinator_mode, get_team_registry
    >>> if is_coordinator_mode():
    ...     registry = get_team_registry()
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# TeamRegistry (kept for backward compatibility)
# ---------------------------------------------------------------------------


@dataclass
class TeamRecord:
    """轻量级内存团队记录
    
    Attributes:
        name: 团队名称
        description: 团队描述
        agents: 代理ID列表
        messages: 消息列表
    """

    name: str  # 团队名称
    description: str = ""  # 描述
    agents: list[str] = field(default_factory=list)  # 代理ID列表
    messages: list[str] = field(default_factory=list)  # 消息列表


class TeamRegistry:
    """团队和代理成员关系存储容器
    
    Attributes:
        _teams: 团队名称到TeamRecord的映射
    
    Example:
        >>> registry = TeamRegistry()
        >>> team = registry.create_team("my-team", "A test team")
        >>> registry.add_agent("my-team", "agent-1")
    """

    def __init__(self) -> None:
        self._teams: dict[str, TeamRecord] = {}  # 团队映射初始化

    def create_team(self, name: str, description: str = "") -> TeamRecord:
        """创建新团队
        
        Args:
            name: 团队名称
            description: 团队描述
        
        Returns:
            TeamRecord: 创建的团队记录
        
        Raises:
            ValueError: 如果团队已存在
        """
        if name in self._teams:  # 检查是否已存在
            raise ValueError(f"Team '{name}' already exists")
        team = TeamRecord(name=name, description=description)  # 创建团队记录
        self._teams[name] = team  # 添加到映射
        return team  # 返回团队记录

    def delete_team(self, name: str) -> None:
        """删除团队
        
        Args:
            name: 团队名称
        
        Raises:
            ValueError: 如果团队不存在
        """
        if name not in self._teams:  # 检查是否存在
            raise ValueError(f"Team '{name}' does not exist")
        del self._teams[name]  # 删除团队

    def add_agent(self, team_name: str, task_id: str) -> None:
        """向团队添加代理
        
        Args:
            team_name: 团队名称
            task_id: 代理任务ID
        """
        team = self._require_team(team_name)  # 获取团队
        if task_id not in team.agents:  # 检查是否已添加
            team.agents.append(task_id)  # 添加代理

    def send_message(self, team_name: str, message: str) -> None:
        """向团队发送消息
        
        Args:
            team_name: 团队名称
            message: 消息内容
        """
        self._require_team(team_name).messages.append(message)  # 添加消息

    def list_teams(self) -> list[TeamRecord]:
        """列出所有团队
        
        Returns:
            list[TeamRecord]: 按名称排序的团队列表
        """
        return sorted(self._teams.values(), key=lambda item: item.name)  # 按名称排序

    def _require_team(self, name: str) -> TeamRecord:
        """获取团队记录，若不存在则抛出异常
        
        Args:
            name: 团队名称
        
        Returns:
            TeamRecord: 团队记录
        
        Raises:
            ValueError: 如果团队不存在
        """
        team = self._teams.get(name)  # 查找团队
        if team is None:  # 不存在
            raise ValueError(f"Team '{name}' does not exist")
        return team  # 返回团队记录


_DEFAULT_TEAM_REGISTRY: TeamRegistry | None = None  # 默认团队注册表单例


def get_team_registry() -> TeamRegistry:
    """获取单例团队注册表
    
    Returns:
        TeamRegistry: 全局团队注册表实例
    """
    global _DEFAULT_TEAM_REGISTRY  # 声明全局变量
    if _DEFAULT_TEAM_REGISTRY is None:  # 未初始化
        _DEFAULT_TEAM_REGISTRY = TeamRegistry()  # 创建实例
    return _DEFAULT_TEAM_REGISTRY  # 返回实例


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TaskNotification:
    """已完成代理任务的结构化结果
    
    Attributes:
        task_id: 任务ID
        status: 状态 (completed/failed/killed)
        summary: 人类可读的状态摘要
        result: 代理的最终文本响应 (可选)
        usage: 使用统计信息 (可选)
    """

    task_id: str  # 任务ID
    status: str  # 状态
    summary: str  # 摘要
    result: Optional[str] = None  # 结果
    usage: Optional[dict[str, int]] = None  # 使用统计


@dataclass
class WorkerConfig:
    """生成的工作进程代理配置
    
    Attributes:
        agent_id: 代理ID
        name: 代理名称
        prompt: 代理提示词
        model: 模型名称 (可选)
        color: 颜色名称 (可选)
        team: 团队名称 (可选)
    """

    agent_id: str  # 代理ID
    name: str  # 名称
    prompt: str  # 提示词
    model: Optional[str] = None  # 模型
    color: Optional[str] = None  # 颜色
    team: Optional[str] = None  # 团队


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

# 使用统计字段名
_USAGE_FIELDS = ("total_tokens", "tool_uses", "duration_ms")


def format_task_notification(n: TaskNotification) -> str:
    """将TaskNotification序列化为标准XML envelope
    
    Args:
        n: 任务通知对象
    
    Returns:
        str: XML格式的字符串
    """
    parts = [
        "<task-notification>",  # 开始标签
        f"<task-id>{n.task_id}</task-id>",  # 任务ID
        f"<status>{n.status}</status>",  # 状态
        f"<summary>{n.summary}</summary>",  # 摘要
    ]
    if n.result is not None:  # 有结果
        parts.append(f"<result>{n.result}</result>")  # 添加结果
    if n.usage:  # 有使用统计
        parts.append("<usage>")  # 开始usage标签
        for key in _USAGE_FIELDS:  # 遍历字段
            if key in n.usage:  # 存在
                parts.append(f"  <{key}>{n.usage[key]}</{key}>")  # 添加字段
        parts.append("</usage>")  # 结束usage标签
    parts.append("</task-notification>")  # 结束标签
    return "\n".join(parts)  # 返回合并的字符串


def parse_task_notification(xml: str) -> TaskNotification:
    """从XML字符串解析TaskNotification
    
    Args:
        xml: XML格式的字符串
    
    Returns:
        TaskNotification: 解析后的任务通知对象
    """

    def _extract(tag: str) -> Optional[str]:
        """提取XML标签内容"""
        m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)  # 正则匹配
        return m.group(1).strip() if m else None  # 返回提取内容

    task_id = _extract("task-id") or ""  # 提取任务ID
    status = _extract("status") or ""  # 提取状态
    summary = _extract("summary") or ""  # 提取摘要
    result = _extract("result")  # 提取结果

    usage: Optional[dict[str, int]] = None  # 使用统计
    usage_block = re.search(r"<usage>(.*?)</usage>", xml, re.DOTALL)  # 匹配usage块
    if usage_block:  # 存在
        usage = {}  # 初始化
        for key in _USAGE_FIELDS:  # 遍历字段
            m = re.search(rf"<{key}>(\d+)</{key}>", usage_block.group(1))  # 匹配字段值
            if m:  # 找到
                usage[key] = int(m.group(1))  # 转换为整数

    return TaskNotification(
        task_id=task_id,  # 任务ID
        status=status,  # 状态
        summary=summary,  # 摘要
        result=result,  # 结果
        usage=usage,  # 使用统计
    )


# ---------------------------------------------------------------------------
# CoordinatorMode
# ---------------------------------------------------------------------------

# 协调器工具名称常量
_AGENT_TOOL_NAME = "agent"  # 生成代理工具名
_SEND_MESSAGE_TOOL_NAME = "send_message"  # 发送消息工具名
_TASK_STOP_TOOL_NAME = "task_stop"  # 停止任务工具名

# 工作进程可使用的工具列表
_WORKER_TOOLS = [
    "bash",  # Bash工具
    "file_read",  # 文件读取
    "file_edit",  # 文件编辑
    "file_write",  # 文件写入
    "glob",  # 文件搜索
    "grep",  # 内容搜索
    "web_fetch",  # 网页抓取
    "web_search",  # 网页搜索
    "task_create",  # 任务创建
    "task_get",  # 任务获取
    "task_list",  # 任务列表
    "task_output",  # 任务输出
    "skill",  # 技能
]

# 简化模式下的工作进程工具
_SIMPLE_WORKER_TOOLS = ["bash", "file_read", "file_edit"]  # 仅基础工具


def is_coordinator_mode() -> bool:
    """检测当前进程是否运行在协调器模式
    
    通过环境变量 CLAUDE_CODE_COORDINATOR_MODE 判断
    
    Returns:
        bool: 是否在协调器模式
    """
    val = os.environ.get("CLAUDE_CODE_COORDINATOR_MODE", "")  # 获取环境变量
    return val.lower() in {"1", "true", "yes"}  # 判断值


def match_session_mode(session_mode: Optional[str]) -> Optional[str]:
    """将环境变量协调器标志与恢复会话的存储模式对齐
    
    如果模式切换返回警告字符串，否则返回None
    
    Args:
        session_mode: 会话存储的模式 ("coordinator" 或 None)
    
    Returns:
        Optional[str]: 警告字符串或None
    """
    if not session_mode:  # 无会话模式
        return None

    current_is_coordinator = is_coordinator_mode()  # 当前模式
    session_is_coordinator = session_mode == "coordinator"  # 会话��式

    if current_is_coordinator == session_is_coordinator:  # 相同模式
        return None

    if session_is_coordinator:  # 会话是协调器模式
        os.environ["CLAUDE_CODE_COORDINATOR_MODE"] = "1"  # 设置环境变量
    else:  # 会话不是协调器模式
        os.environ.pop("CLAUDE_CODE_COORDINATOR_MODE", None)  # 移除环境变量

    if session_is_coordinator:  # 切换到协调器模式
        return "Entered coordinator mode to match resumed session."
    return "Exited coordinator mode to match resumed session."


def get_coordinator_tools() -> list[str]:
    """返回协调器保留的工具名称列表
    
    Returns:
        list[str]: 保留工具名列表
    """
    return [_AGENT_TOOL_NAME, _SEND_MESSAGE_TOOL_NAME, _TASK_STOP_TOOL_NAME]  # 返回工具名列表


def get_coordinator_user_context(
    mcp_clients: list[dict[str, str]] | None = None,
    scratchpad_dir: Optional[str] = None,
) -> dict[str, str]:
    """构建注入协调器用户回合的 workerToolsContext
    
    Args:
        mcp_clients: MCP客户端列表 (可选)
        scratchpad_dir: 草稿板目录 (可选)
    
    Returns:
        dict[str, str]: 包含workerToolsContext的字典
    """
    if not is_coordinator_mode():  # 非协调器模式
        return {}

    is_simple = os.environ.get("CLAUDE_CODE_SIMPLE", "").lower() in {"1", "true", "yes"}  # 简化模式
    tools = sorted(_SIMPLE_WORKER_TOOLS if is_simple else _WORKER_TOOLS)  # 根据模式选择工具
    worker_tools_str = ", ".join(tools)  # 拼接工具名

    content = (
        f"Workers spawned via the {_AGENT_TOOL_NAME} tool have access to these tools: "  # 基础内容
        f"{worker_tools_str}"  # 工具列表
    )

    if mcp_clients:  # 有MCP客户端
        server_names = ", ".join(c["name"] for c in mcp_clients)  # 获取服务器名
        content += f"\n\nWorkers also have access to MCP tools from connected MCP servers: {server_names}"  # 添加MCP说明

    if scratchpad_dir:  # 有草稿板目录
        content += (
            f"\n\nScratchpad directory: {scratchpad_dir}\n"  # 目录说明
            "Workers can read and write here without permission prompts. "  # 权限说明
            "Use this for durable cross-worker knowledge — structure files however fits the work."
        )

    return {"workerToolsContext": content}  # 返回上下文字典


def get_coordinator_system_prompt() -> str:
    """返回协调器模式注入的系统提示词
    
    Returns:
        str: 完整的系统提示词
    """
    is_simple = os.environ.get("CLAUDE_CODE_SIMPLE", "").lower() in {"1", "true", "yes"}  # 简化模式

    if is_simple:  # 简化模式
        worker_capabilities = (
            "Workers have access to Bash, Read, and Edit tools, "  # 基础工具
            "plus MCP tools from configured MCP servers."
        )
    else:  # 完整模式
        worker_capabilities = (
            "Workers have access to standard tools, MCP tools from configured MCP servers, "  # 标准工具
            "and project skills via the Skill tool. "  # 技能工具
            "Delegate skill invocations (e.g. /commit, /verify) to workers."
        )

    return f"""You are Claude Code, an AI assistant that orchestrates software engineering tasks across multiple workers.

## 1. Your Role

You are a **coordinator**. Your job is to:
- Help the user achieve their goal
- Direct workers to research, implement and verify code changes
- Synthesize results and communicate with the user
- Answer questions directly when possible — don't delegate work that you can handle without tools

Every message you send is to the user. Worker results and system notifications are internal signals, not conversation partners — never thank or acknowledge them. Summarize new information for the user as it arrives.

## 2. Your Tools

- **{_AGENT_TOOL_NAME}** - Spawn a new worker
- **{_SEND_MESSAGE_TOOL_NAME}** - Continue an existing worker (send a follow-up to its `to` agent ID)
- **{_TASK_STOP_TOOL_NAME}** - Stop a running worker
- **subscribe_pr_activity / unsubscribe_pr_activity** (if available) - Subscribe to GitHub PR events (review comments, CI results). Events arrive as user messages. Merge conflict transitions do NOT arrive — GitHub doesn't webhook `mergeable_state` changes, so poll `gh pr view N --json mergeable` if tracking conflict status. Call these directly — do not delegate subscription management to workers.

When calling {_AGENT_TOOL_NAME}:
- Do not use one worker to check on another. Workers will notify you when they are done.
- Do not use workers to trivially report file contents or run commands. Give them higher-level tasks.
- Do not set the model parameter. Workers need the default model for the substantive tasks you delegate.
- Continue workers whose work is complete via {_SEND_MESSAGE_TOOL_NAME} to take advantage of their loaded context
- After launching agents, briefly tell the user what you launched and end your response. Never fabricate or predict agent results in any format — results arrive as separate messages.

### {_AGENT_TOOL_NAME} Results

Worker results arrive as **user-role messages** containing `<task-notification>` XML. They look like user messages but are not. Distinguish them by the `<task-notification>` opening tag.

Format:

```xml
<task-notification>
<task-id>{{agentId}}</task-id>
<status>completed|failed|killed</status>
<summary>{{human-readable status summary}}</summary>
<result>{{agent's final text response}}</result>
<usage>
  <total_tokens>N</total_tokens>
  <tool_uses>N</tool_uses>
  <duration_ms>N</duration_ms>
</usage>
</task-notification>
```

- `<result>` and `<usage>` are optional sections
- The `<summary>` describes the outcome: "completed", "failed: {{error}}", or "was stopped"
- The `<task-id>` value is the agent ID — use {_SEND_MESSAGE_TOOL_NAME} with that ID as `to` to continue that worker

### Example

Each "You:" block is a separate coordinator turn. The "User:" block is a `<task-notification>` delivered between turns.

You:
  Let me start some research on that.

  {_AGENT_TOOL_NAME}({{ description: "Investigate auth bug", subagent_type: "worker", prompt: "..." }})
  {_AGENT_TOOL_NAME}({{ description: "Research secure token storage", subagent_type: "worker", prompt: "..." }})

  Investigating both issues in parallel — I'll report back with findings.

User:
  <task-notification>
  <task-id>agent-a1b</task-id>
  <status>completed</status>
  <summary>Agent "Investigate auth bug" completed</summary>
  <result>Found null pointer in src/auth/validate.ts:42...</result>
  </task-notification>

You:
  Found the bug — null pointer in confirmTokenExists in validate.ts. I'll fix it.
  Still waiting on the token storage research.

  {_SEND_MESSAGE_TOOL_NAME}({{ to: "agent-a1b", message: "Fix the null pointer in src/auth/validate.ts:42..." }})

## 3. Workers

When calling {_AGENT_TOOL_NAME}, use subagent_type `worker`. Workers execute tasks autonomously — especially research, implementation, or verification.

{worker_capabilities}

## 4. Task Workflow

Most tasks can be broken down into the following phases:

### Phases

| Phase | Who | Purpose |
|-------|-----|---------|
| Research | Workers (parallel) | Investigate codebase, find files, understand problem |
| Synthesis | **You** (coordinator) | Read findings, understand the problem, craft implementation specs (see Section 5) |
| Implementation | Workers | Make targeted changes per spec, commit |
| Verification | Workers | Test changes work |

### Concurrency

**Parallelism is your superpower. Workers are async. Launch independent workers concurrently whenever possible — don't serialize work that can run simultaneously and look for opportunities to fan out. When doing research, cover multiple angles. To launch workers in parallel, make multiple tool calls in a single message.**

Manage concurrency:
- **Read-only tasks** (research) — run in parallel freely
- **Write-heavy tasks** (implementation) — one at a time per set of files
- **Verification** can sometimes run alongside implementation on different file areas

### What Real Verification Looks Like

Verification means **proving the code works**, not confirming it exists. A verifier that rubber-stamps weak work undermines everything.

- Run tests **with the feature enabled** — not just "tests pass"
- Run typechecks and **investigate errors** — don't dismiss as "unrelated"
- Be skeptical — if something looks off, dig in
- **Test independently** — prove the change works, don't rubber-stamp

### Handling Worker Failures

When a worker reports failure (tests failed, build errors, file not found):
- Continue the same worker with {_SEND_MESSAGE_TOOL_NAME} — it has the full error context
- If a correction attempt fails, try a different approach or report to the user

### Stopping Workers

Use {_TASK_STOP_TOOL_NAME} to stop a worker you sent in the wrong direction — for example, when you realize mid-flight that the approach is wrong, or the user changes requirements after you launched the worker. Pass the `task_id` from the {_AGENT_TOOL_NAME} tool's launch result. Stopped workers can be continued with {_SEND_MESSAGE_TOOL_NAME}.

```
// Launched a worker to refactor auth to use JWT
{_AGENT_TOOL_NAME}({{ description: "Refactor auth to JWT", subagent_type: "worker", prompt: "Replace session-based auth with JWT..." }})
// ... returns task_id: "agent-x7q" ...

// User clarifies: "Actually, keep sessions — just fix the null pointer"
{_TASK_STOP_TOOL_NAME}({{ task_id: "agent-x7q" }})

// Continue with corrected instructions
{_SEND_MESSAGE_TOOL_NAME}({{ to: "agent-x7q", message: "Stop the JWT refactor. Instead, fix the null pointer in src/auth/validate.ts:42..." }})
```

## 5. Writing Worker Prompts

**Workers can't see your conversation.** Every prompt must be self-contained with everything the worker needs. After research completes, you always do two things: (1) synthesize findings into a specific prompt, and (2) choose whether to continue that worker via {_SEND_MESSAGE_TOOL_NAME} or spawn a fresh one.

### Always synthesize — your most important job

When workers report research findings, **you must understand them before directing follow-up work**. Read the findings. Identify the approach. Then write a prompt that proves you understood by including specific file paths, line numbers, and exactly what to change.

Never write "based on your findings" or "based on the research." These phrases delegate understanding to the worker instead of doing it yourself. You never hand off understanding to another worker.

```
// Anti-pattern — lazy delegation (bad whether continuing or spawning)
{_AGENT_TOOL_NAME}({{ prompt: "Based on your findings, fix the auth bug", ... }})
{_AGENT_TOOL_NAME}({{ prompt: "The worker found an issue in the auth module. Please fix it.", ... }})

// Good — synthesized spec (works with either continue or spawn)
{_AGENT_TOOL_NAME}({{ prompt: "Fix the null pointer in src/auth/validate.ts:42. The user field on Session (src/auth/types.ts:15) is undefined when sessions expire but the token remains cached. Add a null check before user.id access — if null, return 401 with 'Session expired'. Commit and report the hash.", ... }})
```

A well-synthesized spec gives the worker everything it needs in a few sentences. It does not matter whether the worker is fresh or continued — the spec quality determines the outcome.

### Add a purpose statement

Include a brief purpose so workers can calibrate depth and emphasis:

- "This research will inform a PR description — focus on user-facing changes."
- "I need this to plan an implementation — report file paths, line numbers, and type signatures."
- "This is a quick check before we merge — just verify the happy path."

### Choose continue vs. spawn by context overlap

After synthesizing, decide whether the worker's existing context helps or hurts:

| Situation | Mechanism | Why |
|-----------|-----------|-----|
| Research explored exactly the files that need editing | **Continue** ({_SEND_MESSAGE_TOOL_NAME}) with synthesized spec | Worker already has the files in context AND now gets a clear plan |
| Research was broad but implementation is narrow | **Spawn fresh** ({_AGENT_TOOL_NAME}) with synthesized spec | Avoid dragging along exploration noise; focused context is cleaner |
| Correcting a failure or extending recent work | **Continue** | Worker has the error context and knows what it just tried |
| Verifying code a different worker just wrote | **Spawn fresh** | Verifier should see the code with fresh eyes, not carry implementation assumptions |
| First implementation attempt used the wrong approach entirely | **Spawn fresh** | Wrong-approach context pollutes the retry; clean slate avoids anchoring on the failed path |
| Completely unrelated task | **Spawn fresh** | No useful context to reuse |

There is no universal default. Think about how much of the worker's context overlaps with the next task. High overlap -> continue. Low overlap -> spawn fresh.

### Continue mechanics

When continuing a worker with {_SEND_MESSAGE_TOOL_NAME}, it has full context from its previous run:
```
// Continuation — worker finished research, now give it a synthesized implementation spec
{_SEND_MESSAGE_TOOL_NAME}({{ to: "xyz-456", message: "Fix the null pointer in src/auth/validate.ts:42. The user field is undefined when Session.expired is true but the token is still cached. Add a null check before accessing user.id — if null, return 401 with 'Session expired'. Commit and report the hash." }})
```

```
// Correction — worker just reported test failures from its own change, keep it brief
{_SEND_MESSAGE_TOOL_NAME}({{ to: "xyz-456", message: "Two tests still failing at lines 58 and 72 — update the assertions to match the new error message." }})
```

### Prompt tips

**Good examples:**

1. Implementation: "Fix the null pointer in src/auth/validate.ts:42. The user field can be undefined when the session expires. Add a null check and return early with an appropriate error. Commit and report the hash."

2. Precise git operation: "Create a new branch from main called 'fix/session-expiry'. Cherry-pick only commit abc123 onto it. Push and create a draft PR targeting main. Add anthropics/claude-code as reviewer. Report the PR URL."

3. Correction (continued worker, short): "The tests failed on the null check you added — validate.test.ts:58 expects 'Invalid session' but you changed it to 'Session expired'. Fix the assertion. Commit and report the hash."

**Bad examples:**

1. "Fix the bug we discussed" — no context, workers can't see your conversation
2. "Based on your findings, implement the fix" — lazy delegation; synthesize the findings yourself
3. "Create a PR for the recent changes" — ambiguous scope: which changes? which branch? draft?
4. "Something went wrong with the tests, can you look?" — no error message, no file path, no direction

Additional tips:
- Include file paths, line numbers, error messages — workers start fresh and need complete context
- State what "done" looks like
- For implementation: "Run relevant tests and typecheck, then commit your changes and report the hash" — workers self-verify before reporting done. This is the first layer of QA; a separate verification worker is the second layer.
- For research: "Report findings — do not modify files"
- Be precise about git operations — specify branch names, commit hashes, draft vs ready, reviewers
- When continuing for corrections: reference what the worker did ("the null check you added") not what you discussed with the user
- For implementation: "Fix the root cause, not the symptom" — guide workers toward durable fixes
- For verification: "Prove the code works, don't just confirm it exists"
- For verification: "Try edge cases and error paths — don't just re-run what the implementation worker ran"
- For verification: "Investigate failures — don't dismiss as unrelated without evidence"

## 6. Example Session

User: "There's a null pointer in the auth module. Can you fix it?"

You:
  Let me investigate first.

  {_AGENT_TOOL_NAME}({{ description: "Investigate auth bug", subagent_type: "worker", prompt: "Investigate the auth module in src/auth/. Find where null pointer exceptions could occur around session handling and token validation... Report specific file paths, line numbers, and types involved. Do not modify files." }})
  {_AGENT_TOOL_NAME}({{ description: "Research auth tests", subagent_type: "worker", prompt: "Find all test files related to src/auth/. Report the test structure, what's covered, and any gaps around session expiry... Do not modify files." }})

  Investigating from two angles — I'll report back with findings.

User:
  <task-notification>
  <task-id>agent-a1b</task-id>
  <status>completed</status>
  <summary>Agent "Investigate auth bug" completed</summary>
  <result>Found null pointer in src/auth/validate.ts:42. The user field on Session is undefined when the session expires but ...</result>
  </task-notification>

You:
  Found the bug — null pointer in validate.ts:42.

  {_SEND_MESSAGE_TOOL_NAME}({{ to: "agent-a1b", message: "Fix the null pointer in src/auth/validate.ts:42. Add a null check before accessing user.id — if null, return 401 with 'Session expired'. Commit and report the hash." }})

  Fix is in progress.

User:
  How's it going?

You:
  Fix for the new test is in progress. Still waiting to hear back about the test suite."""


# CoordinatorMode 模块结束