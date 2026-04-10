"""
会话压缩模块 — 微压缩和基于 LLM 的完整摘要
==============================================

本模块实现会话压缩功能，忠实翻译自 Claude Code 的压缩系统：
- 微压缩（Microcompact）：清除旧工具结果内容以廉价方式减少 Token 数量
- 完整压缩（Full Compact）：调用 LLM 生成早期消息的结构化摘要
- 自动压缩（Auto-compact）：当 Token 数量超过阈值时自动触发压缩

主要功能：
    - 估算会话 Token 数量
    - 微压缩：清除旧工具结果
    - 完整压缩：LLM 生成摘要
    - 自动压缩：自动触发压缩

类说明：
    - AutoCompactState: 自动压缩状态数据类
    - estimate_message_tokens: 估算消息 Token 数
    - microcompact_messages: 执行微压缩
    - compact_conversation: 执行完整压缩
    - auto_compact_if_needed: 检查并执行自动压缩

使用示例：
    >>> from illusion.services.compact import microcompact_messages, estimate_message_tokens
    >>> # 估算 Token 数量
    >>> token_count = estimate_message_tokens(messages)
    >>> # 执行微压缩
    >>> messages, tokens_saved = microcompact_messages(messages, keep_recent=5)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from illusion.engine.messages import (
    ConversationMessage,
    ContentBlock,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from illusion.services.token_estimation import estimate_tokens

# 配置模块级日志记录器
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量（来自 Claude Code microCompact.ts / autoCompact.ts）
# ---------------------------------------------------------------------------

# 可压缩的工具列表
COMPACTABLE_TOOLS: frozenset[str] = frozenset({
    "read_file",
    "bash",
    "grep",
    "glob",
    "web_search",
    "web_fetch",
    "edit_file",
    "write_file",
})

# 微压缩清除后的占位符消息
TIME_BASED_MC_CLEARED_MESSAGE = "[Old tool result content cleared]"

# 自动压缩阈值
AUTOCOMPACT_BUFFER_TOKENS = 13_000  # 缓冲区 Token 数
MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000  # 摘要最大输出 Token 数
MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3  # 最大连续失败次数

# 微压缩默认值
DEFAULT_KEEP_RECENT = 5  # 保留最近工具结果数量
DEFAULT_GAP_THRESHOLD_MINUTES = 60  # 时间间隔阈值（分钟）

# Token 估算 padding（保守估计）
TOKEN_ESTIMATION_PADDING = 4 / 3

# 默认上下文窗口大小（按模型系列）
_DEFAULT_CONTEXT_WINDOW = 200_000


# ---------------------------------------------------------------------------
# Token 估算
# ---------------------------------------------------------------------------

def estimate_message_tokens(messages: list[ConversationMessage]) -> int:
    """估算会话消息的总 Token 数，包含 4/3 padding。"""
    total = 0
    for msg in messages:
        for block in msg.content:
            if isinstance(block, TextBlock):
                total += estimate_tokens(block.text)
            elif isinstance(block, ToolResultBlock):
                total += estimate_tokens(block.content)
            elif isinstance(block, ToolUseBlock):
                total += estimate_tokens(block.name)
                total += estimate_tokens(str(block.input))
    return int(total * TOKEN_ESTIMATION_PADDING)


def estimate_conversation_tokens(messages: list[ConversationMessage]) -> int:
    """保持向后兼容性的别名。"""
    return estimate_message_tokens(messages)


# ---------------------------------------------------------------------------
# 微压缩 — 清除旧工具结果以廉价方式减少 Token
# ---------------------------------------------------------------------------

def _collect_compactable_tool_ids(messages: list[ConversationMessage]) -> list[str]:
    """遍历消息并收集可压缩的工具使用 ID。"""
    ids: list[str] = []
    for msg in messages:
        if msg.role != "assistant":
            continue
        for block in msg.content:
            if isinstance(block, ToolUseBlock) and block.name in COMPACTABLE_TOOLS:
                ids.append(block.id)
    return ids


def microcompact_messages(
    messages: list[ConversationMessage],
    *,
    keep_recent: int = DEFAULT_KEEP_RECENT,
) -> tuple[list[ConversationMessage], int]:
    """清除旧的可压缩工具结果，保留最近的 keep_recent 个。

    这是廉价的第一轮压缩 — 无需调用 LLM。工具结果内容
    将被替换为 TIME_BASED_MC_CLEARED_MESSAGE。

    Returns:
        (messages, tokens_saved) — 消息在原地修改以提高效率。
    """
    keep_recent = max(1, keep_recent)  # 永远不清除所有结果
    all_ids = _collect_compactable_tool_ids(messages)

    if len(all_ids) <= keep_recent:
        return messages, 0

    # 计算需要保留和清除的 ID 集合
    keep_set = set(all_ids[-keep_recent:])
    clear_set = set(all_ids) - keep_set

    tokens_saved = 0
    for msg in messages:
        if msg.role != "user":
            continue
        new_content: list[ContentBlock] = []
        for block in msg.content:
            if (
                isinstance(block, ToolResultBlock)
                and block.tool_use_id in clear_set
                and block.content != TIME_BASED_MC_CLEARED_MESSAGE
            ):
                # 计算节省的 Token 数
                tokens_saved += estimate_tokens(block.content)
                new_content.append(
                    ToolResultBlock(
                        tool_use_id=block.tool_use_id,
                        content=TIME_BASED_MC_CLEARED_MESSAGE,
                        is_error=block.is_error,
                    )
                )
            else:
                new_content.append(block)
        msg.content = new_content

    if tokens_saved > 0:
        # 记录微压缩结果
        log.info("Microcompact cleared %d tool results, saved ~%d tokens", len(clear_set), tokens_saved)

    return messages, tokens_saved


# ---------------------------------------------------------------------------
# 完整压缩 — 基于 LLM 的摘要
# ---------------------------------------------------------------------------

# 不使用工具的前导文本
NO_TOOLS_PREAMBLE = """\
CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.

- Do NOT use read_file, bash, grep, glob, edit_file, write_file, or ANY other tool.
- You already have all the context you need in the conversation above.
- Tool calls will be REJECTED and will waste your only turn — you will fail the task.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.

"""

# 基础压缩提示词
BASE_COMPACT_PROMPT = """\
Your task is to create a detailed summary of the conversation so far. This summary will replace the earlier messages, so it must capture all important information.

First, draft your analysis inside <analysis> tags. Walk through the conversation chronologically and extract:
- Every user request and intent (explicit and implicit)
- The approach taken and technical decisions made
- Specific code, files, and configurations discussed (with paths and line numbers where available)
- All errors encountered and how they were fixed
- Any user feedback or corrections

Then, produce a structured summary inside <summary> tags with these sections:

1. **Primary Request and Intent**: All user requests in full detail, including nuances and constraints.
2. **Key Technical Concepts**: Technologies, frameworks, patterns, and conventions discussed.
3. **Files and Code Sections**: Every file examined or modified, with specific code snippets and line numbers.
4. **Errors and Fixes**: Every error encountered, its cause, and how it was resolved.
5. **Problem Solving**: Problems solved and approaches that worked vs. didn't work.
6. **All User Messages**: Non-tool-result user messages (preserve exact wording for context).
7. **Pending Tasks**: Explicitly requested work that hasn't been completed yet.
8. **Current Work**: Detailed description of the last task being worked on before compaction.
9. **Optional Next Step**: The single most logical next step, directly aligned with the user's recent request.
"""

# 不使用工具的结尾文本
NO_TOOLS_TRAILER = """
REMINDER: Do NOT call any tools. Respond with plain text only — an <analysis> block followed by a <summary> block. Tool calls will be rejected and you will fail the task."""


def get_compact_prompt(custom_instructions: str | None = None) -> str:
    """构建发送给模型的完整压缩提示词。"""
    prompt = NO_TOOLS_PREAMBLE + BASE_COMPACT_PROMPT
    if custom_instructions and custom_instructions.strip():
        prompt += f"\n\nAdditional Instructions:\n{custom_instructions}"
    prompt += NO_TOOLS_TRAILER
    return prompt


def format_compact_summary(raw_summary: str) -> str:
    """移除 <analysis> 草稿并提取 <summary> 内容。"""
    text = re.sub(r"<analysis>[\s\S]*?</analysis>", "", raw_summary)
    m = re.search(r"<summary>([\s\S]*?)</summary>", text)
    if m:
        text = text.replace(m.group(0), f"Summary:\n{m.group(1).strip()}")
    # 清理多余空行
    text = re.sub(r"\n\n+", "\n\n", text)
    return text.strip()


def build_compact_summary_message(
    summary: str,
    *,
    suppress_follow_up: bool = False,
    recent_preserved: bool = False,
) -> str:
    """创建替换压缩历史的消息。"""
    formatted = format_compact_summary(summary)
    text = (
        "This session is being continued from a previous conversation that ran "
        "out of context. The summary below covers the earlier portion of the "
        "conversation.\n\n"
        f"{formatted}"
    )
    if recent_preserved:
        text += "\n\nRecent messages are preserved verbatim."
    if suppress_follow_up:
        text += (
            "\nContinue the conversation from where it left off without asking "
            "the user any further questions. Resume directly — do not acknowledge "
            "the summary, do not recap what was happening, do not preface with "
            '"I\'ll continue" or similar. Pick up the last task as if the break '
            "never happened."
        )
    return text


# ---------------------------------------------------------------------------
# 自动压缩跟踪
# ---------------------------------------------------------------------------

@dataclass
class AutoCompactState:
    """跨查询循环轮次持久的可变状态。"""

    compacted: bool = False
    turn_counter: int = 0
    consecutive_failures: int = 0


# ---------------------------------------------------------------------------
# 上下文窗口辅助函数
# ---------------------------------------------------------------------------

def get_context_window(model: str) -> int:
    """返回模型的上下文窗口大小（保守默认值）。"""
    m = model.lower()
    if "opus" in m:
        return 200_000
    if "sonnet" in m:
        return 200_000
    if "haiku" in m:
        return 200_000
    # Kimi / other providers — 保守估计
    return _DEFAULT_CONTEXT_WINDOW


def get_autocompact_threshold(model: str) -> int:
    """计算触发自动压缩的 Token 数量阈值。"""
    context_window = get_context_window(model)
    reserved = min(MAX_OUTPUT_TOKENS_FOR_SUMMARY, 20_000)
    effective = context_window - reserved
    return effective - AUTOCOMPACT_BUFFER_TOKENS


def should_autocompact(
    messages: list[ConversationMessage],
    model: str,
    state: AutoCompactState,
) -> bool:
    """返回是否应该自动压缩会话。"""
    if state.consecutive_failures >= MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES:
        return False
    token_count = estimate_message_tokens(messages)
    threshold = get_autocompact_threshold(model)
    return token_count >= threshold


# ---------------------------------------------------------------------------
# 完整压缩执行（调用 LLM）
# ---------------------------------------------------------------------------

async def compact_conversation(
    messages: list[ConversationMessage],
    *,
    api_client: Any,
    model: str,
    system_prompt: str = "",
    preserve_recent: int = 6,
    custom_instructions: str | None = None,
    suppress_follow_up: bool = True,
) -> list[ConversationMessage]:
    """通过调用 LLM 生成摘要来压缩消息。

    1. 先执行微压缩（廉价 Token 减少）。
    2. 分割为待摘要的旧消息和待保留的新消息。
    3. 调用 LLM 获取结构化摘要。
    4. 用摘要 + 保留的新消息替换旧消息。

    Args:
        messages: 完整的会话历史。
        api_client: 用于摘要调用的 ApiClient 或兼容客户端。
        model: 使用的模型 ID。
        system_prompt: 摘要调用的系统提示词。
        preserve_recent: 保留 verbatim 的最近消息数量。
        custom_instructions: 摘要提示词的可选额外指令。
        suppress_follow_up: 为 True 时指示模型不询问后续问题。

    Returns:
        压缩后的新消息列表。
    """
    from illusion.api.client import ApiMessageRequest, ApiMessageCompleteEvent

    if len(messages) <= preserve_recent:
        return list(messages)

    # 步骤 1：微压缩以廉价方式减少 Token
    messages, tokens_freed = microcompact_messages(messages, keep_recent=DEFAULT_KEEP_RECENT)

    pre_compact_tokens = estimate_message_tokens(messages)
    log.info("Compacting conversation: %d messages, ~%d tokens", len(messages), pre_compact_tokens)

    # 步骤 2：分割为待摘要和待保留部分
    older = messages[:-preserve_recent]
    newer = messages[-preserve_recent:]

    # 步骤 3：构建压缩请求 — 发送旧消息 + 压缩提示词
    compact_prompt = get_compact_prompt(custom_instructions)
    compact_messages = list(older) + [ConversationMessage.from_user_text(compact_prompt)]

    summary_text = ""
    async for event in api_client.stream_message(
        ApiMessageRequest(
            model=model,
            messages=compact_messages,
            system_prompt=system_prompt or "You are a conversation summarizer.",
            max_tokens=MAX_OUTPUT_TOKENS_FOR_SUMMARY,
            tools=[],  # 压缩调用不使用工具
        )
    ):
        if isinstance(event, ApiMessageCompleteEvent):
            summary_text = event.message.text

    if not summary_text:
        # 空摘要则返回原始消息
        log.warning("Compact summary was empty — returning original messages")
        return messages

    # 步骤 4：构建新消息列表
    summary_content = build_compact_summary_message(
        summary_text,
        suppress_follow_up=suppress_follow_up,
        recent_preserved=len(newer) > 0,
    )
    summary_msg = ConversationMessage.from_user_text(summary_content)

    result = [summary_msg, *newer]
    post_compact_tokens = estimate_message_tokens(result)
    log.info(
        "Compaction done: %d -> %d messages, ~%d -> ~%d tokens (saved ~%d)",
        len(messages), len(result),
        pre_compact_tokens, post_compact_tokens,
        pre_compact_tokens - post_compact_tokens,
    )
    return result


# ---------------------------------------------------------------------------
# 自动压缩集成（从查询循环调用）
# ---------------------------------------------------------------------------

async def auto_compact_if_needed(
    messages: list[ConversationMessage],
    *,
    api_client: Any,
    model: str,
    system_prompt: str = "",
    state: AutoCompactState,
    preserve_recent: int = 6,
) -> tuple[list[ConversationMessage], bool]:
    """检查是否应该自动压缩，如果是则执行压缩。

    在每个查询循环轮次开始时调用此函数。

    Returns:
        (messages, was_compacted) — 如果已压缩，messages 是新列表。
    """
    if not should_autocompact(messages, model, state):
        return messages, False

    log.info("Auto-compact triggered (failures=%d)", state.consecutive_failures)

    # 先尝试微压缩 — 可能已经足够
    messages, tokens_freed = microcompact_messages(messages)
    if tokens_freed > 0 and not should_autocompact(messages, model, state):
        log.info("Microcompact freed ~d tokens, auto-compact no longer needed", tokens_freed)
        return messages, True

    # 需要完整压缩
    try:
        result = await compact_conversation(
            messages,
            api_client=api_client,
            model=model,
            system_prompt=system_prompt,
            preserve_recent=preserve_recent,
            suppress_follow_up=True,
        )
        state.compacted = True
        state.turn_counter += 1
        state.consecutive_failures = 0
        return result, True
    except Exception as exc:
        state.consecutive_failures += 1
        log.error(
            "Auto-compact failed (attempt %d/%d): %s",
            state.consecutive_failures,
            MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES,
            exc,
        )
        return messages, False


# ---------------------------------------------------------------------------
# 向后兼容
# ---------------------------------------------------------------------------

def summarize_messages(
    messages: list[ConversationMessage],
    *,
    max_messages: int = 8,
) -> str:
    """生成最近消息的紧凑文本摘要（传统方法）。"""
    selected = messages[-max_messages:]
    lines: list[str] = []
    for message in selected:
        text = message.text.strip()
        if not text:
            continue
        lines.append(f"{message.role}: {text[:300]}")
    return "\n".join(lines)


def compact_messages(
    messages: list[ConversationMessage],
    *,
    preserve_recent: int = 6,
) -> list[ConversationMessage]:
    """用合成摘要替换旧的会话历史（传统方法）。"""
    if len(messages) <= preserve_recent:
        return list(messages)
    older = messages[:-preserve_recent]
    newer = messages[-preserve_recent:]
    summary = summarize_messages(older)
    if not summary:
        return list(newer)
    return [
        ConversationMessage(
            role="user",
            content=[TextBlock(text=f"[conversation summary]\n{summary}")],
        ),
        *newer,
    ]


__all__ = [
    "AUTO_COMPACT_BUFFER_TOKENS",
    "AutoCompactState",
    "COMPACTABLE_TOOLS",
    "TIME_BASED_MC_CLEARED_MESSAGE",
    "auto_compact_if_needed",
    "build_compact_summary_message",
    "compact_conversation",
    "compact_messages",
    "estimate_conversation_tokens",
    "estimate_message_tokens",
    "format_compact_summary",
    "get_autocompact_threshold",
    "get_compact_prompt",
    "microcompact_messages",
    "should_autocompact",
    "summarize_messages",
]