"""Events yielded by the query engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from illusion.api.usage import UsageSnapshot
from illusion.engine.messages import ConversationMessage


class SessionPhase(Enum):
    """Phase of the agent session."""

    IDLE = "idle"
    THINKING = "thinking"
    TOOL_EXECUTING = "tool_executing"


@dataclass(frozen=True)
class AssistantTextDelta:
    """Incremental assistant text."""

    text: str


@dataclass(frozen=True)
class AssistantTurnComplete:
    """Completed assistant turn."""

    message: ConversationMessage
    usage: UsageSnapshot


@dataclass(frozen=True)
class ToolExecutionStarted:
    """The engine is about to execute a tool."""

    tool_name: str
    tool_input: dict[str, Any]


@dataclass(frozen=True)
class ToolExecutionCompleted:
    """A tool has finished executing."""

    tool_name: str
    output: str
    is_error: bool = False


@dataclass(frozen=True)
class ErrorEvent:
    """An error that should be surfaced to the user."""

    message: str
    recoverable: bool = True


@dataclass(frozen=True)
class StatusEvent:
    """A transient system status message shown to the user."""

    message: str


@dataclass(frozen=True)
class ToolChainStarted:
    """A batch of tool executions is about to begin."""

    tool_count: int


@dataclass(frozen=True)
class ToolChainCompleted:
    """All tools in a batch have finished executing."""

    results_summary: list[dict[str, Any]]


StreamEvent = (
    AssistantTextDelta
    | AssistantTurnComplete
    | ToolExecutionStarted
    | ToolExecutionCompleted
    | ErrorEvent
    | StatusEvent
    | ToolChainStarted
    | ToolChainCompleted
)
