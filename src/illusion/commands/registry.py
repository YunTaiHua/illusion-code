"""
斜杠命令注册模块
==============

本模块提供 IllusionCode 斜杠命令的注册和管理功能。

主要功能：
    - 注册和管理斜杠命令 (/xxx)
    - 解析命令参数
    - 提供内置命令处理器

类说明：
    - CommandResult: 命令执行结果
    - CommandContext: 命令执行上下文
    - SlashCommand: 斜杠命令定义
    - CommandRegistry: 命令注册表

函数说明：
    - create_default_command_registry: 创建默认命令注册表

内置命令列表：
    - /help, /exit, /clear, /version, /status, /context, /summary
    - /compact, /cost, /usage, /stats, /memory, /hooks, /resume
    - /export, /share, /copy, /rewind, /files
    - /init, /bridge, /login, /logout, /feedback
    - /skills, /config, /mcp, /plugin, /reload-plugins
    - /permissions, /plan, /fast, /effort, /passes, /turns
    - /continue, /model, /language, /output-style
    - /doctor, /diff, /branch, /commit
    - /issue, /pr_comments, /privacy-settings
    - /agents, /tasks, /delete, /rules

使用示例：
    >>> from illusion.commands import create_default_command_registry
    >>> registry = create_default_command_registry()
    >>> result = registry.lookup("/version")
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, Literal, get_args

import pyperclip

from illusion.config.paths import (
    get_config_dir,
    get_data_dir,
    get_feedback_log_path,
    get_project_config_dir,
    get_project_issue_file,
    get_project_pr_comments_file,
)
from illusion.bridge import get_bridge_manager
from illusion.bridge.types import WorkSecret
from illusion.bridge.work_secret import build_sdk_url, decode_work_secret, encode_work_secret
from illusion.api.provider import auth_status, detect_provider
from illusion.config.settings import Settings, load_settings, save_settings
from illusion.engine.messages import ConversationMessage
from illusion.engine.query_engine import QueryEngine
from illusion.memory import (
    add_memory_entry,
    get_memory_entrypoint,
    get_project_memory_dir,
    list_memory_files,
    remove_memory_entry,
)
from illusion.output_styles import load_output_styles
from illusion.permissions import PermissionChecker, PermissionMode
from illusion.plugins import load_plugins
from illusion.prompts import build_runtime_system_prompt
from illusion.plugins.installer import install_plugin_from_path, uninstall_plugin
from illusion.services import (
    compact_messages,
    estimate_conversation_tokens,
    export_session_markdown,
    save_session_snapshot,
    summarize_messages,
)
from illusion.services.session_storage import get_project_session_dir, load_session_snapshot
from illusion.skills import load_skill_registry
from illusion.tasks import get_task_manager

if TYPE_CHECKING:
    from illusion.state import AppStateStore
    from illusion.tools.base import ToolRegistry


@dataclass
class CommandResult:
    """斜杠命令执行结果
    
    Attributes:
        message: 返回给用户的消息
        should_exit: 是否应该退出程序
        clear_screen: 是否应该清除屏幕
        replay_messages: 要在TUI中重放的消息列表
        continue_pending: 是否继续待处理的工具循环
        continue_turns: 继续的回合数
    """

    message: str | None = None  # 返回消息
    should_exit: bool = False  # 退出标志
    clear_screen: bool = False  # 清屏标志
    replay_messages: list | None = None  # ConversationMessage列表用于TUI重放
    continue_pending: bool = False  # 继续待处理标志
    continue_turns: int | None = None  # 继续回合数
    reset_session: bool = False  # 是否重置会话ID
    restored_session_id: str | None = None  # 恢复的会话ID


_COMMAND_DESCRIPTIONS_ZH: dict[str, str] = {
    "help": "显示可用命令",
    "exit": "退出 IllusionCode",
    "clear": "清空当前对话历史",
    "new": "开启新对话并重置任务 ID",
    "version": "显示已安装版本",
    "status": "显示会话状态",
    "context": "显示当前运行时系统提示词",
    "summary": "总结对话历史",
    "compact": "压缩较早对话历史",
    "cost": "显示 token 用量和预估费用",
    "usage": "显示用量与 token 估算",
    "stats": "显示会话统计",
    "memory": "查看和管理项目记忆",
    "hooks": "显示已配置 hooks",
    "resume": "恢复最近保存的会话",
    "export": "导出当前转录",
    "share": "创建可分享的转录快照",
    "copy": "复制最新回复或指定文本",
    "rewind": "移除最新对话轮次",
    "files": "列出当前工作区文件",
    "init": "初始化项目 IllusionCode 文件",
    "bridge": "查看 bridge 辅助信息并创建 bridge 会话",
    "login": "查看认证状态或保存 API Key",
    "logout": "清除已保存 API Key",
    "feedback": "保存 CLI 反馈到本地日志",
    "skills": "列出或显示可用技能",
    "config": "显示或更新配置",
    "mcp": "显示 MCP 状态",
    "plugin": "管理插件",
    "reload-plugins": "重新加载当前工作区插件发现结果",
    "permissions": "显示或更新权限模式",
    "plan": "切换计划权限模式",
    "fast": "显示或更新快速模式",
    "effort": "显示或更新推理强度",
    "passes": "显示或更新推理轮数",
    "turns": "显示或更新最大 agent 轮数",
    "continue": "在中断后继续上一轮工具循环",
    "model": "显示或更新默认模型",
    "language": "显示或更新界面语言",
    "output-style": "显示或更新输出风格",
    "doctor": "显示环境诊断信息",
    "diff": "显示 git diff 输出",
    "branch": "显示 git 分支信息",
    "commit": "显示状态或创建 git 提交",
    "issue": "显示或更新项目 issue 上下文",
    "pr_comments": "显示或更新项目 PR 评论上下文",
    "privacy-settings": "显示本地隐私与存储设置",
    "agents": "列出或查看 agent 与 teammate 任务",
    "tasks": "管理后台任务",
    "delete": "清理选定的会话",
    "rules": "查看选定的规则",
}


def _resolve_ui_language(context: "CommandContext | None") -> str:
    if context is not None and context.app_state is not None:
        value = str(context.app_state.get().ui_language or "")
        if value:
            return value
    return str(load_settings().ui_language)


def _is_zh(locale: str) -> bool:
    return locale.lower().startswith("zh")


def _translate_single_line(line: str, exact: dict[str, str], substitutions: list[tuple[re.Pattern[str], str]]) -> str:
    """翻译单行消息"""
    if line in exact:
        return exact[line]
    translated = line
    for pattern, replacement in substitutions:
        if callable(replacement):
            translated = pattern.sub(replacement, translated)
        else:
            translated = pattern.sub(replacement, translated)
    return translated


def _translate_command_message(message: str, *, locale: str) -> str:
    if not message or not _is_zh(locale):
        return message

    exact: dict[str, str] = {
        # 通用
        "Available commands:": "可用命令：",
        "(empty)": "（空）",
        "(no output)": "（无输出）",
        "(no directories)": "（无目录）",
        "(no matching files)": "（无匹配文件）",
        "(no diff)": "（无差异）",
        "(working tree clean)": "（工作区干净）",
        # 会话
        "Conversation cleared.": "对话已清空。",
        "Started a new conversation session.": "已开启新对话。",
        "No saved sessions found for this project.": "当前项目未找到已保存会话。",
        "Nothing to copy.": "没有可复制的内容。",
        # 记忆与 hooks
        "No memory files.": "没有记忆文件。",
        "No hooks configured.": "未配置 hooks。",
        # 插件与技能
        "No plugins discovered.": "未发现插件。",
        "No skills available.": "没有可用技能。",
        # Agent
        "No active or recorded agents.": "没有活跃或历史 agent。",
        # 项目初始化
        "Project already initialized for IllusionCode.": "项目已完成 IllusionCode 初始化。",
        # Bridge
        "No bridge sessions.": "没有 bridge 会话。",
        # 认证
        "Stored API key in ~/.illusion/settings.json": "API Key 已保存到 ~/.illusion/settings.json",
        "Cleared stored API key.": "已清除已保存 API Key。",
        # 反馈
        "Usage: /feedback TEXT": "用法：/feedback 文本",
        # 计划模式
        "Plan mode enabled.": "计划模式已开启。",
        "Plan mode disabled.": "计划模式已关闭。",
        # 模型
        "Usage: /model [show|set MODEL]": "用法：/model [show|set MODEL]",
        "Model set to": "模型已切换为",
        # 语言
        "Available UI languages: zh-CN, en": "可用界面语言：zh-CN, en",
        "Usage: /language [show|list|set zh-CN|set en]": "用法：/language [show|list|set zh-CN|set en]",
        # 输出风格
        "Usage: /output-style [show|list|set NAME]": "用法：/output-style [show|list|set NAME]",
        # 诊断与隐私
        "Doctor summary:": "诊断摘要：",
        "Privacy settings:": "隐私设置：",
        # Git
        "Usage: /branch [show|list]": "用法：/branch [show|list]",
        "Nothing to commit.": "没有可提交的改动。",
        # 后台任务
        "No background tasks.": "没有后台任务。",
        "Progress must be an integer between 0 and 100.": "进度必须是 0 到 100 之间的整数。",
        "Nothing to continue (no pending tool results).": "没有待继续的内容（无待处理工具结果）。",
        "Continuing pending tool loop...": "正在继续待处理的工具循环…",
        # MCP
        "HTTP/WS MCP auth supports bearer or header modes.": "HTTP/WS MCP 认证支持 bearer 或 header 模式。",
        "stdio MCP auth supports bearer or env modes.": "stdio MCP 认证支持 bearer 或 env 模式。",
        "No MCP servers configured.": "未配置 MCP 服务器。",
        # Issue 与 PR 评论
        "Cleared issue context.": "已清除 issue 上下文。",
        "No issue context to clear.": "没有可清除的 issue 上下文。",
        "Cleared PR comments context.": "已清除 PR 评论上下文。",
        "No PR comments context to clear.": "没有可清除的 PR 评论上下文。",
        # 用法提示
        "Usage: /summary [MAX_MESSAGES]": "用法：/summary [最大消息数]",
        "Usage: /compact [PRESERVE_RECENT]": "用法：/compact [保留近期消息数]",
        "Usage: /memory add TITLE :: CONTENT": "用法：/memory add 标题 :: 内容",
        "Usage: /memory [list|show NAME|add TITLE :: CONTENT|remove NAME]": "用法：/memory [list|show 名称|add 标题 :: 内容|remove 名称]",
        "Usage: /rewind [TURNS]": "用法：/rewind [轮数]",
        "Usage: /config [show|set KEY VALUE]": "用法：/config [show|set 键 值]",
        "Usage: /fast [show|on|off|toggle]": "用法：/fast [show|on|off|toggle]",
        "Usage: /effort [show|low|medium|high]": "用法：/effort [show|low|medium|high]",
        "Usage: /passes [show|COUNT]": "用法：/passes [数量]",
        "Usage: /turns [show|COUNT]": "用法：/turns [数量]",
        "Usage: /continue [COUNT]": "用法：/continue [数量]",
        "Usage: /plan [on|off]": "用法：/plan [on|off]",
        "Usage: /permissions [show|set MODE]": "用法：/permissions [show|set 模式]",
        "Usage: /issue set TITLE :: BODY": "用法：/issue set 标题 :: 正文",
        "Usage: /issue [show|set TITLE :: BODY|clear]": "用法：/issue [show|set 标题 :: 正文|clear]",
        "Usage: /pr_comments add FILE[:LINE] :: COMMENT": "用法：/pr_comments add 文件[:行号] :: 评论",
        "Usage: /pr_comments [show|add FILE[:LINE] :: COMMENT|clear]": "用法：/pr_comments [show|add 文件[:行号] :: 评论|clear]",
        "Usage: /plugin [list|enable NAME|disable NAME|install PATH|uninstall NAME]":
            "用法：/plugin [list|enable 名称|disable 名称|install 路径|uninstall 名称]",
        "Usage: /bridge [show|encode API_BASE_URL TOKEN|decode SECRET|sdk API_BASE_URL SESSION_ID|spawn CMD|list|output SESSION_ID|stop SESSION_ID]":
            "用法：/bridge [show|encode API_BASE_URL TOKEN|decode SECRET|sdk API_BASE_URL SESSION_ID|spawn CMD|list|output SESSION_ID|stop SESSION_ID]",
        "Usage: /tasks update ID [description TEXT|progress NUMBER|note TEXT]":
            "用法：/tasks update ID [description 文本|progress 数字|note 文本]",
        "Usage: /tasks [list|run CMD|stop ID|show ID|update ID description TEXT|update ID progress NUMBER|update ID note TEXT|output ID]":
            "用法：/tasks [list|run CMD|stop ID|show ID|update ID description 文本|update ID progress 数字|update ID note 文本|output ID]",
        # 快速模式
        "No conversation content to summarize.": "没有可总结的对话内容。",
        # 删除与规则
        "Saved sessions:": "已保存会话：",
        "Use /resume <session_id> to restore a specific session.": "使用 /resume <会话ID> 恢复指定会话。",
        # 登录
        "Usage: /login API_KEY": "用法：/login API_KEY",
        # Doctor
        "- backend host: available": "- 后端宿主：可用",
        "- network: enabled only for provider and explicit web/MCP calls": "- 网络：仅用于提供商和显式 web/MCP 调用",
        "- storage: local files under ~/.illusion and project .illusion": "- 存储：本地文件位于 ~/.illusion 和项目 .illusion",
    }
    if message in exact:
        return exact[message]

    substitutions: list[tuple[re.Pattern[str], str]] = [
        # 版本
        (re.compile(r"^IllusionCode (.+)$"), r"IllusionCode 版本 \1"),
        # 模型
        (re.compile(r"^Model: (.+)$"), r"模型：\1"),
        (re.compile(r"^Model set to (.+)\. Restart session to use it\.$"), r"模型已设置为 \1。重启会话后生效。"),
        (re.compile(r"^Model set to (.+)\.$"), r"模型已设置为 \1。"),
        (re.compile(r"^Unknown model: (.+)$"), r"未知模型：\1"),
        # 语言
        (re.compile(r"^UI language: (.+)$"), r"界面语言：\1"),
        (re.compile(r"^UI language set to (.+)$"), r"界面语言已设置为 \1"),
        # 输出风格
        (re.compile(r"^Output style: (.+)$"), r"输出风格：\1"),
        (re.compile(r"^Output style set to (.+)$"), r"输出风格已设置为 \1"),
        (re.compile(r"^Unknown output style: (.+)$"), r"未知输出风格：\1"),
        # 快速模式
        (re.compile(r"^Fast mode: (on|off)$"), r"快速模式：\1"),
        (re.compile(r"^Fast mode (enabled|disabled)\.$"), lambda m: f"快速模式{'已开启' if m.group(1) == 'enabled' else '已关闭'}。"),
        # 推理强度
        (re.compile(r"^Reasoning effort: (.+)$"), r"推理强度：\1"),
        (re.compile(r"^Reasoning effort set to (.+)\.$"), r"推理强度已设置为 \1。"),
        # 推理轮数
        (re.compile(r"^Passes: (.+)$"), r"推理轮数：\1"),
        (re.compile(r"^Pass count set to (.+)\.$"), r"推理轮数已设置为 \1。"),
        # 最大轮数
        (re.compile(r"^Max turns set to (.+)\.$"), r"最大轮数已设置为 \1。"),
        # 权限
        (re.compile(r"^Permission mode set to (.+)$"), r"权限模式已设置为 \1"),
        (re.compile(r"^Mode: (.+)$"), r"模式：\1"),
        # 会话
        (re.compile(r"^Session not found: (.+)$"), r"未找到会话：\1"),
        (re.compile(r"^Restored (\d+) messages from session (.+)$"), r"已从会话 \2 恢复 \1 条消息"),
        (re.compile(r"^Restored (\d+) messages from the latest session\.$"), r"已从最近会话恢复 \1 条消息。"),
        (re.compile(r"^Exported transcript to (.+)$"), r"已导出转录到 \1"),
        (re.compile(r"^Created shareable transcript snapshot at (.+)$"), r"已创建可分享的转录快照：\1"),
        (re.compile(r"^Copied (\d+) characters to the clipboard\.$"), r"已复制 \1 个字符到剪贴板。"),
        (re.compile(r"^Clipboard unavailable\. Saved copied text to (.+)$"), r"剪贴板不可用，已保存到 \1"),
        (re.compile(r"^Rewound (\d+) turn\(s\); removed (\d+) message\(s\)\.$"), r"已回退 \1 轮，移除 \2 条消息。"),
        # 任务
        (re.compile(r"^Started task (.+)$"), r"已启动任务 \1"),
        (re.compile(r"^Stopped task (.+)$"), r"已停止任务 \1"),
        (re.compile(r"^No task found with ID: (.+)$"), r"未找到任务 ID：\1"),
        (re.compile(r"^Updated task (.+) description$"), r"已更新任务 \1 的描述"),
        (re.compile(r"^Updated task (.+) progress to (\d+)%$"), r"已更新任务 \1 的进度为 \2%"),
        (re.compile(r"^Updated task (.+) note$"), r"已更新任务 \1 的备注"),
        (re.compile(r"^Deleted (\d+) session file\(s\)\.$"), r"已删除 \1 个会话文件。"),
        (re.compile(r"^Deleted session: (.+)$"), r"已删除会话：\1"),
        # Agent
        (re.compile(r"^No agent found with ID: (.+)$"), r"未找到 agent ID：\1"),
        # Bridge
        (re.compile(r"^Spawned bridge session (.+) pid=(\d+)$"), r"已创建 bridge 会话 \1 进程 \2"),
        (re.compile(r"^Stopped bridge session (.+)$"), r"已停止 bridge 会话 \1"),
        # 插件
        (re.compile(r"^Enabled plugin '(.+)'\. Restart session to reload\.$"), r"已启用插件「\1」，重启会话后生效。"),
        (re.compile(r"^Disabled plugin '(.+)'\. Restart session to reload\.$"), r"已禁用插件「\1」，重启会话后生效。"),
        (re.compile(r"^Installed plugin to (.+)$"), r"已安装插件到 \1"),
        (re.compile(r"^Uninstalled plugin '(.+)'$"), r"已卸载插件「\1」"),
        (re.compile(r"^Plugin '(.+)' not found$"), r"未找到插件「\1」"),
        # 配置
        (re.compile(r"^Unknown config key: (.+)$"), r"未知配置项：\1"),
        (re.compile(r"^Updated (.+)$"), r"已更新 \1"),
        # 记忆
        (re.compile(r"^Memory entry not found: (.+)$"), r"未找到记忆条目：\1"),
        (re.compile(r"^Added memory entry (.+)$"), r"已添加记忆条目 \1"),
        (re.compile(r"^Removed memory entry (.+)$"), r"已移除记忆条目 \1"),
        # MCP
        (re.compile(r"^Unknown MCP server: (.+)$"), r"未知 MCP 服务器：\1"),
        (re.compile(r"^Server (.+) does not support auth updates$"), r"服务器 \1 不支持认证更新"),
        (re.compile(r"^Saved MCP auth for (.+)\. Restart session to reconnect\.$"), r"已保存 \1 的 MCP 认证，重启会话后重新连接。"),
        # Issue 与 PR 评论
        (re.compile(r"^No issue context\. File path: (.+)$"), r"无 issue 上下文。文件路径：\1"),
        (re.compile(r"^Saved issue context to (.+)$"), r"已保存 issue 上下文到 \1"),
        (re.compile(r"^No PR comments context\. File path: (.+)$"), r"无 PR 评论上下文。文件路径：\1"),
        (re.compile(r"^Added PR comment to (.+)$"), r"已添加 PR 评论到 \1"),
        # 反馈
        (re.compile(r"^Saved feedback to (.+)$"), r"已保存反馈到 \1"),
        # 初始化
        (re.compile(r"^Initialized project files:$"), r"已初始化项目文件："),
        # 技能
        (re.compile(r"^Skill not found: (.+)$"), r"未找到技能：\1"),
        # 规则
        (re.compile(r"^No rules found in (.+)$"), r"在 \1 中未找到规则"),
        (re.compile(r"^Rule not found: (.+)\. Use /rules to list available rules\.$"), r"未找到规则：\1。使用 /rules 查看可用规则。"),
        # 状态行（多行消息的逐行翻译）
        (re.compile(r"^Session stats:$"), r"会话统计："),
        (re.compile(r"^Messages: (\d+)$"), r"消息数：\1"),
        (re.compile(r"^Usage: input=(\d+) output=(\d+)$"), r"用量：输入=\1 输出=\2"),
        (re.compile(r"^Effort: (.+)$"), r"推理强度：\1"),
        (re.compile(r"^Actual usage: input=(\d+) output=(\d+)$"), r"实际用量：输入=\1 输出=\2"),
        (re.compile(r"^Estimated conversation tokens: (\d+)$"), r"预估对话 token：\1"),
        (re.compile(r"^Input tokens: (\d+)$"), r"输入 token：\1"),
        (re.compile(r"^Output tokens: (\d+)$"), r"输出 token：\1"),
        (re.compile(r"^Total tokens: (\d+)$"), r"总计 token：\1"),
        (re.compile(r"^Estimated cost: (.+)$"), r"预估费用：\1"),
        (re.compile(r"^Max turns \(engine\): (.+)$"), r"最大轮数（引擎）：\1"),
        (re.compile(r"^Max turns \(config\): (.+)$"), r"最大轮数（配置）：\1"),
        (re.compile(r"^Memory directory: (.+)$"), r"记忆目录：\1"),
        (re.compile(r"^Entrypoint: (.+)$"), r"入口文件：\1"),
        (re.compile(r"^Compacted conversation from (\d+) messages to (\d+)\.$"), r"已压缩对话：\1 条 → \2 条。"),
        (re.compile(r"^Current branch: (.+)$"), r"当前分支：\1"),
        (re.compile(r"^Feedback log: (.+)$"), r"反馈日志：\1"),
        (re.compile(r"^Auth status:$"), r"认证状态："),
        (re.compile(r"^Bridge summary:$"), r"Bridge 摘要："),
        (re.compile(r"^Reloaded plugins:$"), r"已重新加载插件："),
        (re.compile(r"^Available skills:$"), r"可用技能："),
        (re.compile(r"^Rules directory: (.+)$"), r"规则目录：\1"),
        (re.compile(r"^Updated (.+)$"), r"已更新 \1"),
        # - 前缀行（doctor, privacy-settings, bridge, login, stats, permissions 等）
        (re.compile(r"^- backend host: available$"), r"- 后端宿主：可用"),
        (re.compile(r"^- network: enabled only for provider and explicit web/MCP calls$"), r"- 网络：仅用于提供商和显式 web/MCP 调用"),
        (re.compile(r"^- storage: local files under ~\/\.illusion and project \.illusion$"), r"- 存储：本地文件位于 ~/.illusion 和项目 .illusion"),
        (re.compile(r"^Usage: \/login API_KEY$"), r"用法：/login API_KEY"),
        (re.compile(r"^- messages: (\d+)$"), r"- 消息数：\1"),
        (re.compile(r"^- estimated_tokens: (\d+)$"), r"- 预估 token：\1"),
        (re.compile(r"^- tools: (\d+)$"), r"- 工具数：\1"),
        (re.compile(r"^- memory_files: (\d+)$"), r"- 记忆文件：\1"),
        (re.compile(r"^- background_tasks: (\d+)$"), r"- 后台任务：\1"),
        (re.compile(r"^- output_style: (.+)$"), r"- 输出风格：\1"),
        (re.compile(r"^- cwd: (.+)$"), r"- 工作目录：\1"),
        (re.compile(r"^- sessions: (\d+)$"), r"- 会话数：\1"),
        (re.compile(r"^- utilities: (.+)$"), r"- 工具集：\1"),
        (re.compile(r"^- provider: (.+)$"), r"- 提供商：\1"),
        (re.compile(r"^- auth_status: (.+)$"), r"- 认证状态：\1"),
        (re.compile(r"^- base_url: (.+)$"), r"- 基础 URL：\1"),
        (re.compile(r"^- model: (.+)$"), r"- 模型：\1"),
        (re.compile(r"^- api_key: (.+)$"), r"- API Key：\1"),
        (re.compile(r"^Allowed tools: (.+)$"), r"允许的工具：\1"),
        (re.compile(r"^Denied tools: (.+)$"), r"拒绝的工具：\1"),
        (re.compile(r"^- permission_mode: (.+)$"), r"- 权限模式：\1"),
        (re.compile(r"^- theme: (.+)$"), r"- 主题：\1"),
        (re.compile(r"^- ui_language: (.+)$"), r"- 界面语言：\1"),
        (re.compile(r"^- memory_dir: (.+)$"), r"- 记忆目录：\1"),
        (re.compile(r"^- plugin_count: (\d+)$"), r"- 插件数：\1"),
        (re.compile(r"^- mcp_configured: (yes|no)$"), lambda m: f"- MCP 已配置：{'是' if m.group(1) == 'yes' else '否'}"),
        (re.compile(r"^- user_config_dir: (.+)$"), r"- 用户配置目录：\1"),
        (re.compile(r"^- project_config_dir: (.+)$"), r"- 项目配置目录：\1"),
        (re.compile(r"^- session_dir: (.+)$"), r"- 会话目录：\1"),
        (re.compile(r"^- feedback_log: (.+)$"), r"- 反馈日志：\1"),
        (re.compile(r"^- api_base_url: (.+)$"), r"- API 基础 URL：\1"),
    ]
    # 支持多行消息：按行分割，逐行翻译，重新拼接
    lines = message.split("\n")
    translated_lines = [_translate_single_line(line, exact, substitutions) for line in lines]
    return "\n".join(translated_lines)


@dataclass
class CommandContext:
    """命令处理器可用的上下文
    
    Attributes:
        engine: 查询引擎实例
        hooks_summary: hooks摘要
        mcp_summary: MCP摘要
        plugin_summary: 插件摘要
        cwd: 当前工作目录
        tool_registry: 工具注册表
        app_state: 应用状态存储
    """

    engine: QueryEngine  # 查询引擎
    hooks_summary: str = ""  # hooks摘要
    mcp_summary: str = ""  # MCP摘要
    plugin_summary: str = ""  # 插件摘要
    cwd: str = "."  # 当前工作目录
    tool_registry: ToolRegistry | None = None  # 工具注册表
    app_state: AppStateStore | None = None  # 应用状态


# 命令处理器类型别名
CommandHandler = Callable[[str, CommandContext], Awaitable[CommandResult]]


@dataclass
class SlashCommand:
    """斜杠命令定义
    
    Attributes:
        name: 命令名称 (不含前导/)
        description: 命令描述
        handler: 命令处理器函数
    """

    name: str  # 命令名称
    description: str  # 命令描述
    handler: CommandHandler  # 处理器函数


class CommandRegistry:
    """斜杠命令到处理器的映射容器
    
    Attributes:
        _commands: 命令名到SlashCommand的映射
    """

    def __init__(self) -> None:
        self._commands: dict[str, SlashCommand] = {}  # 命令映射初始化

    def register(self, command: SlashCommand) -> None:
        """注册命令
        
        Args:
            command: 要注册的SlashCommand
        """
        original_handler = command.handler

        async def _localized_handler(args: str, context: CommandContext) -> CommandResult:
            result = await original_handler(args, context)
            if result.message:
                result.message = _translate_command_message(
                    result.message,
                    locale=_resolve_ui_language(context),
                )
            return result

        self._commands[command.name] = SlashCommand(
            name=command.name,
            description=command.description,
            handler=_localized_handler,
        )

    def lookup(self, raw_input: str) -> tuple[SlashCommand, str] | None:
        """解析斜杠命令并返回其处理器和原始参数
        
        Args:
            raw_input: 原始输入字符串
        
        Returns:
            tuple[SlashCommand, str] | None: (命令对象, 参数) 或 None
        """
        if not raw_input.startswith("/"):  # 不是斜杠命令
            return None
        name, _, args = raw_input[1:].partition(" ")  # 分割名称和参数
        command = self._commands.get(name)  # 查找命令
        if command is None:  # 未找到
            return None
        return command, args.strip()  # 返回命令和参数

    def help_text(self) -> str:
        """返回所有已注册命令的格式化摘要
        
        Returns:
            str: 格式化的命令帮助文本
        """
        locale = _resolve_ui_language(None)
        lines = ["可用命令：" if _is_zh(locale) else "Available commands:"]  # 标题
        for command in sorted(self._commands.values(), key=lambda item: item.name):  # 遍历命令
            description = command.description
            if _is_zh(locale):
                description = _COMMAND_DESCRIPTIONS_ZH.get(command.name, description)
            lines.append(f"/{command.name:<12} {description}")  # 格式化输出
        return "\n".join(lines)

    def list_commands(self) -> list[SlashCommand]:
        """按照注册顺序返回命令列表
        
        Returns:
            list[SlashCommand]: 命令列表
        """
        return list(self._commands.values())


def _run_git_command(cwd: str, *args: str) -> tuple[bool, str]:
    """执行git命令并返回结果
    
    Args:
        cwd: 工作目录
        args: git子命令和参数
    
    Returns:
        tuple[bool, str]: (是否成功, 输出内容)
    """
    try:
        run_kwargs: dict = {}
        if sys.platform == "win32":
            run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            **run_kwargs,
        )
    except FileNotFoundError:  # git未安装
        return False, "git is not installed."
    output = (completed.stdout or completed.stderr).strip()  # 合并输出
    if completed.returncode != 0:  # 失败
        return False, output or f"git {' '.join(args)} failed"
    return True, output  # 成功


def _copy_to_clipboard(text: str) -> tuple[bool, str]:
    """复制文本到剪贴板
    
    尝试多种复制方式: pyperclip, pbcopy, wl-copy, xclip, xsel
    
    Args:
        text: 要复制的文本
    
    Returns:
        tuple[bool, str]: (是否成功, 目标位置)
    """
    try:
        pyperclip.copy(text)
        return True, "clipboard"
    except Exception:
        clip_kwargs: dict = {}
        if sys.platform == "win32":
            clip_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        for command in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard"]):
            try:
                subprocess.run(command, input=text, text=True, check=True, capture_output=True, **clip_kwargs)
                return True, "clipboard"
            except Exception:
                continue
    fallback = get_data_dir() / "last_copy.txt"  # 后备方案：文件
    fallback.write_text(text, encoding="utf-8")
    return False, str(fallback)


def _last_message_text(messages: list[ConversationMessage]) -> str:
    """获取最后一条有内容的用户消息
    
    Args:
        messages: 消息列表
    
    Returns:
        str: 消息文本，空字符串若无
    """
    for message in reversed(messages):  # 反向遍历
        if message.text.strip():  # 有内容
            return message.text.strip()
    return ""


def _rewind_turns(messages: list[ConversationMessage], turns: int) -> list[ConversationMessage]:
    """回退指定数量的对话回合
    
    回退到上一个非空的user消息
    
    Args:
        messages: 消息列表
        turns: 回退回合数
    
    Returns:
        list[ConversationMessage]: 回退后的消息列表
    """
    updated = list(messages)  # 复制列表
    for _ in range(max(0, turns)):  # 指定次数
        if not updated:  # 空列表
            break
        while updated:
            popped = updated.pop()  # 弹出
            if popped.role == "user" and popped.text.strip():  # 找到用户消息
                break
    return updated


def _coerce_setting_value(settings: Settings, key: str, raw: str):
    """将字符串值强制转换为设置字段的正确类型
    
    Args:
        settings: 设置对象
        key: 字段名
        raw: 原始字符串值
    
    Returns:
        转换后的值
    
    Raises:
        KeyError: 字段不存在
        ValueError: 值无效
    """
    field = Settings.model_fields.get(key)  # 获取字段定义
    if field is None:  # 不存在
        raise KeyError(key)
    annotation = field.annotation  # 类型注解
    if annotation is bool:  # 布尔类型
        lowered = raw.lower()
        if lowered in {"1", "true", "yes", "on"}:  # 真值
            return True
        if lowered in {"0", "false", "no", "off"}:  # 假值
            return False
        raise ValueError(f"Invalid boolean value for {key}: {raw}")
    if annotation is int:  # 整数类型
        return int(raw)
    if annotation is str:  # 字符串类型
        return raw
    if annotation is Literal or getattr(annotation, "__origin__", None) is Literal:  # 字面量类型
        allowed = get_args(annotation)
        if raw not in allowed:  # 不在允许值中
            raise ValueError(f"Invalid value for {key}: {raw}")
        return raw
    return raw


def create_default_command_registry() -> CommandRegistry:
    """Create the built-in command registry."""
    registry = CommandRegistry()

    async def _help_handler(_: str, context: CommandContext) -> CommandResult:
        del context
        return CommandResult(message=registry.help_text())

    async def _exit_handler(_: str, context: CommandContext) -> CommandResult:
        del context
        return CommandResult(should_exit=True)

    async def _clear_handler(_: str, context: CommandContext) -> CommandResult:
        context.engine.clear()
        return CommandResult(message="Conversation cleared.", clear_screen=True)

    async def _new_handler(_: str, context: CommandContext) -> CommandResult:
        context.engine.clear()
        return CommandResult(
            message="Started a new conversation session.",
            clear_screen=True,
            reset_session=True,
        )

    async def _status_handler(_: str, context: CommandContext) -> CommandResult:
        usage = context.engine.total_usage
        state = context.app_state.get() if context.app_state is not None else None
        return CommandResult(
            message=(
                f"Messages: {len(context.engine.messages)}\n"
                f"Usage: input={usage.input_tokens} output={usage.output_tokens}\n"
                f"Effort: {state.effort if state is not None else load_settings().effort}\n"
                f"Passes: {state.passes if state is not None else load_settings().passes}"
            )
        )

    async def _version_handler(_: str, context: CommandContext) -> CommandResult:
        del context
        try:
            version = importlib.metadata.version("illusion")
        except importlib.metadata.PackageNotFoundError:
            version = "0.1.0"
        return CommandResult(message=f"IllusionCode {version}")

    async def _context_handler(_: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        prompt = build_runtime_system_prompt(settings, cwd=context.cwd)
        return CommandResult(message=prompt)

    async def _summary_handler(args: str, context: CommandContext) -> CommandResult:
        max_messages = 8
        if args:
            try:
                max_messages = max(1, int(args))
            except ValueError:
                return CommandResult(message="Usage: /summary [MAX_MESSAGES]")
        summary = summarize_messages(context.engine.messages, max_messages=max_messages)
        return CommandResult(message=summary or "No conversation content to summarize.")

    async def _compact_handler(args: str, context: CommandContext) -> CommandResult:
        preserve_recent = 6
        if args:
            try:
                preserve_recent = max(1, int(args))
            except ValueError:
                return CommandResult(message="Usage: /compact [PRESERVE_RECENT]")
        before = len(context.engine.messages)
        compacted = compact_messages(context.engine.messages, preserve_recent=preserve_recent)
        context.engine.load_messages(compacted)
        return CommandResult(
            message=f"Compacted conversation from {before} messages to {len(compacted)}."
        )

    async def _usage_handler(_: str, context: CommandContext) -> CommandResult:
        usage = context.engine.total_usage
        estimated = estimate_conversation_tokens(context.engine.messages)
        return CommandResult(
            message=(
                f"Actual usage: input={usage.input_tokens} output={usage.output_tokens}\n"
                f"Estimated conversation tokens: {estimated}\n"
                f"Messages: {len(context.engine.messages)}"
            )
        )

    async def _cost_handler(_: str, context: CommandContext) -> CommandResult:
        usage = context.engine.total_usage
        model = context.app_state.get().model if context.app_state is not None else load_settings().model
        estimated_cost = "unavailable"
        if model.startswith("claude-3-5-sonnet"):
            estimated = (usage.input_tokens * 3.0 + usage.output_tokens * 15.0) / 1_000_000
            estimated_cost = f"${estimated:.4f} (estimated)"
        elif model.startswith("claude-3-7-sonnet"):
            estimated = (usage.input_tokens * 3.0 + usage.output_tokens * 15.0) / 1_000_000
            estimated_cost = f"${estimated:.4f} (estimated)"
        elif model.startswith("claude-3-opus"):
            estimated = (usage.input_tokens * 15.0 + usage.output_tokens * 75.0) / 1_000_000
            estimated_cost = f"${estimated:.4f} (estimated)"
        return CommandResult(
            message=(
                f"Model: {model}\n"
                f"Input tokens: {usage.input_tokens}\n"
                f"Output tokens: {usage.output_tokens}\n"
                f"Total tokens: {usage.total_tokens}\n"
                f"Estimated cost: {estimated_cost}"
            )
        )

    async def _stats_handler(_: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        memory_count = len(list_memory_files(context.cwd))
        task_count = len(get_task_manager().list_tasks())
        tool_count = len(context.tool_registry.list_tools()) if context.tool_registry is not None else 0
        style = settings.output_style
        if context.app_state is not None:
            state = context.app_state.get()
            style = state.output_style
        return CommandResult(
            message=(
                "Session stats:\n"
                f"- messages: {len(context.engine.messages)}\n"
                f"- estimated_tokens: {estimate_conversation_tokens(context.engine.messages)}\n"
                f"- tools: {tool_count}\n"
                f"- memory_files: {memory_count}\n"
                f"- background_tasks: {task_count}\n"
                f"- output_style: {style}"
            )
        )

    async def _memory_handler(args: str, context: CommandContext) -> CommandResult:
        tokens = args.split(maxsplit=1)
        if not tokens:
            memory_dir = get_project_memory_dir(context.cwd)
            entrypoint = get_memory_entrypoint(context.cwd)
            return CommandResult(
                message=f"Memory directory: {memory_dir}\nEntrypoint: {entrypoint}"
            )
        action = tokens[0]
        rest = tokens[1] if len(tokens) == 2 else ""
        if action == "list":
            memory_files = list_memory_files(context.cwd)
            if not memory_files:
                return CommandResult(message="No memory files.")
            return CommandResult(message="\n".join(path.name for path in memory_files))
        if action == "show" and rest:
            memory_dir = get_project_memory_dir(context.cwd)
            path = memory_dir / rest
            if not path.exists():
                path = memory_dir / f"{rest}.md"
            if not path.exists():
                return CommandResult(message=f"Memory entry not found: {rest}")
            return CommandResult(message=path.read_text(encoding="utf-8"))
        if action == "add" and rest:
            title, separator, content = rest.partition("::")
            if not separator or not title.strip() or not content.strip():
                return CommandResult(message="Usage: /memory add TITLE :: CONTENT")
            path = add_memory_entry(context.cwd, title.strip(), content.strip())
            return CommandResult(message=f"Added memory entry {path.name}")
        if action == "remove" and rest:
            if remove_memory_entry(context.cwd, rest.strip()):
                return CommandResult(message=f"Removed memory entry {rest.strip()}")
            return CommandResult(message=f"Memory entry not found: {rest.strip()}")
        return CommandResult(message="Usage: /memory [list|show NAME|add TITLE :: CONTENT|remove NAME]")

    async def _hooks_handler(_: str, context: CommandContext) -> CommandResult:
        return CommandResult(message=context.hooks_summary or "No hooks configured.")

    async def _resume_handler(args: str, context: CommandContext) -> CommandResult:
        from illusion.services.session_storage import list_session_snapshots, load_session_by_id

        tokens = args.strip().split()

        # /resume <session_id> — load a specific session
        if tokens:
            sid = tokens[0]
            snapshot = load_session_by_id(context.cwd, sid)
            if snapshot is None:
                return CommandResult(message=f"Session not found: {sid}")
            messages = [
                ConversationMessage.model_validate(item)
                for item in snapshot.get("messages", [])
            ]
            context.engine.load_messages(messages)
            summary = snapshot.get("summary", "")[:60]
            return CommandResult(
                message=f"Restored {len(messages)} messages from session {sid}"
                + (f" ({summary})" if summary else ""),
                replay_messages=messages,
                restored_session_id=str(snapshot.get("session_id") or sid),
            )

        # /resume — list sessions (for the TUI to show a picker)
        sessions = list_session_snapshots(context.cwd, limit=10)
        if not sessions:
            # Fall back to latest.json
            snapshot = load_session_snapshot(context.cwd)
            if snapshot is None:
                return CommandResult(message="No saved sessions found for this project.")
            messages = [
                ConversationMessage.model_validate(item)
                for item in snapshot.get("messages", [])
            ]
            context.engine.load_messages(messages)
            return CommandResult(
                message=f"Restored {len(messages)} messages from the latest session.",
                replay_messages=messages,
                restored_session_id=str(snapshot.get("session_id", "")),
            )

        # Format session list for display / picker
        import time
        lines = ["Saved sessions:"]
        for s in sessions:
            ts = time.strftime("%m/%d %H:%M", time.localtime(s["created_at"]))
            summary = s["summary"][:50] or "(no summary)"
            lines.append(f"  {s['session_id']}  {ts}  {s['message_count']}msg  {summary}")
        lines.append("")
        lines.append("Use /resume <session_id> to restore a specific session.")
        return CommandResult(message="\n".join(lines))

    async def _export_handler(_: str, context: CommandContext) -> CommandResult:
        path = export_session_markdown(cwd=context.cwd, messages=context.engine.messages)
        return CommandResult(message=f"Exported transcript to {path}")

    async def _share_handler(_: str, context: CommandContext) -> CommandResult:
        path = export_session_markdown(cwd=context.cwd, messages=context.engine.messages)
        return CommandResult(message=f"Created shareable transcript snapshot at {path}")

    async def _copy_handler(args: str, context: CommandContext) -> CommandResult:
        text = args.strip() or _last_message_text(context.engine.messages)
        if not text:
            return CommandResult(message="Nothing to copy.")
        copied, target = _copy_to_clipboard(text)
        if copied:
            return CommandResult(message=f"Copied {len(text)} characters to the clipboard.")
        return CommandResult(message=f"Clipboard unavailable. Saved copied text to {target}")

    async def _rewind_handler(args: str, context: CommandContext) -> CommandResult:
        turns = 1
        if args.strip():
            try:
                turns = max(1, int(args.strip()))
            except ValueError:
                return CommandResult(message="Usage: /rewind [TURNS]")
        before = len(context.engine.messages)
        updated = _rewind_turns(context.engine.messages, turns)
        context.engine.load_messages(updated)
        removed = before - len(updated)
        return CommandResult(
            clear_screen=True,
            replay_messages=list(updated),
            message=f"Rewound {turns} turn(s); removed {removed} message(s).",
        )

    async def _files_handler(args: str, context: CommandContext) -> CommandResult:
        raw = args.strip()
        root = Path(context.cwd)
        max_items = 30
        tokens = raw.split(maxsplit=1)
        if tokens and tokens[0] == "dirs":
            dirs = [
                path
                for path in sorted(root.rglob("*"))
                if path.is_dir() and ".git" not in path.parts and ".venv" not in path.parts
            ]
            lines = [str(path.relative_to(root)) for path in dirs[:max_items]]
            if len(dirs) > max_items:
                lines.append(f"... {len(dirs) - max_items} more")
            return CommandResult(message="\n".join(lines) if lines else "(no directories)")
        if tokens and tokens[0].isdigit():
            max_items = max(1, min(int(tokens[0]), 200))
            raw = tokens[1] if len(tokens) == 2 else ""
        needle = raw.lower()
        files = [
            path
            for path in sorted(root.rglob("*"))
            if path.is_file() and ".git" not in path.parts and ".venv" not in path.parts
        ]
        if needle:
            files = [path for path in files if needle in str(path.relative_to(root)).lower()]
        lines = [str(path.relative_to(root)) for path in files[:max_items]]
        if len(files) > max_items:
            lines.append(f"... {len(files) - max_items} more")
        return CommandResult(
            message="\n".join(lines) if lines else "(no matching files)"
        )

    async def _agents_handler(args: str, context: CommandContext) -> CommandResult:
        tokens = args.split(maxsplit=1)
        if tokens and tokens[0] == "show" and len(tokens) == 2:
            task = get_task_manager().get_task(tokens[1])
            if task is None or task.type not in {"local_agent", "remote_agent", "in_process_teammate"}:
                return CommandResult(message=f"No agent found with ID: {tokens[1]}")
            output = get_task_manager().read_task_output(task.id)
            return CommandResult(
                message=(
                    f"{task.id} {task.type} {task.status} {task.description}\n"
                    f"metadata={task.metadata}\n"
                    f"output:\n{output or '(no output)'}"
                )
            )
        tasks = [
            task
            for task in get_task_manager().list_tasks()
            if task.type in {"local_agent", "remote_agent", "in_process_teammate"}
        ]
        if not tasks:
            return CommandResult(message="No active or recorded agents.")
        lines = [
            f"{task.id} {task.type} {task.status} {task.description}"
            for task in tasks
        ]
        return CommandResult(message="\n".join(lines))

    async def _init_handler(args: str, context: CommandContext) -> CommandResult:
        del args
        project_dir = get_project_config_dir(context.cwd)
        created: list[str] = []

        claudemd = Path(context.cwd) / "CLAUDE.md"
        if not claudemd.exists():
            claudemd.write_text(
                "# Project Instructions\n\n"
                "- Use IllusionCode tools deliberately.\n"
                "- Keep changes minimal and verify with tests when possible.\n",
                encoding="utf-8",
            )
            created.append(str(claudemd.relative_to(Path(context.cwd))))

        for relative, content in (
            (
                project_dir / "README.md",
                "# Project IllusionCode Config\n\nThis directory stores project-specific IllusionCode state.\n",
            ),
            (
                project_dir / "memory" / "MEMORY.md",
                "# Project Memory\n\nAdd reusable project knowledge here.\n",
            ),
            (
                project_dir / "plugins" / ".gitkeep",
                "",
            ),
            (
                project_dir / "skills" / ".gitkeep",
                "",
            ),
        ):
            relative.parent.mkdir(parents=True, exist_ok=True)
            if not relative.exists():
                relative.write_text(content, encoding="utf-8")
                created.append(str(relative.relative_to(Path(context.cwd))))

        if not created:
            return CommandResult(message="Project already initialized for IllusionCode.")
        return CommandResult(message="Initialized project files:\n" + "\n".join(f"- {item}" for item in created))

    async def _bridge_handler(args: str, context: CommandContext) -> CommandResult:
        tokens = args.split()
        if not tokens or tokens[0] == "show":
            sessions = get_bridge_manager().list_sessions()
            lines = [
                "Bridge summary:",
                "- backend host: available",
                f"- cwd: {context.cwd}",
                f"- sessions: {len(sessions)}",
                "- utilities: encode, decode, sdk, spawn, list, output, stop",
            ]
            return CommandResult(message="\n".join(lines))
        if tokens[0] == "encode" and len(tokens) == 3:
            encoded = encode_work_secret(
                WorkSecret(version=1, session_ingress_token=tokens[2], api_base_url=tokens[1])
            )
            return CommandResult(message=encoded)
        if tokens[0] == "decode" and len(tokens) == 2:
            secret = decode_work_secret(tokens[1])
            return CommandResult(message=json.dumps(secret.__dict__, indent=2))
        if tokens[0] == "sdk" and len(tokens) == 3:
            return CommandResult(message=build_sdk_url(tokens[1], tokens[2]))
        if tokens[0] == "spawn" and len(tokens) >= 2:
            command = args[len("spawn ") :]
            handle = await get_bridge_manager().spawn(
                session_id=f"bridge-{datetime.now(timezone.utc).strftime('%H%M%S')}",
                command=command,
                cwd=context.cwd,
            )
            return CommandResult(
                message=f"Spawned bridge session {handle.session_id} pid={handle.process.pid}"
            )
        if tokens[0] == "list":
            sessions = get_bridge_manager().list_sessions()
            if not sessions:
                return CommandResult(message="No bridge sessions.")
            return CommandResult(
                message="\n".join(
                    f"{item.session_id} [{item.status}] pid={item.pid} {item.command}"
                    for item in sessions
                )
            )
        if tokens[0] == "output" and len(tokens) == 2:
            return CommandResult(message=get_bridge_manager().read_output(tokens[1]) or "(no output)")
        if tokens[0] == "stop" and len(tokens) == 2:
            try:
                await get_bridge_manager().stop(tokens[1])
            except ValueError as exc:
                return CommandResult(message=str(exc))
            return CommandResult(message=f"Stopped bridge session {tokens[1]}")
        return CommandResult(
            message="Usage: /bridge [show|encode API_BASE_URL TOKEN|decode SECRET|sdk API_BASE_URL SESSION_ID|spawn CMD|list|output SESSION_ID|stop SESSION_ID]"
        )

    async def _reload_plugins_handler(_: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        plugins = load_plugins(settings, context.cwd)
        if not plugins:
            return CommandResult(message="No plugins discovered.")
        lines = ["Reloaded plugins:"]
        for plugin in plugins:
            state = "enabled" if plugin.enabled else "disabled"
            lines.append(f"- {plugin.manifest.name} [{state}]")
        return CommandResult(message="\n".join(lines))

    async def _skills_handler(args: str, context: CommandContext) -> CommandResult:
        skill_registry = load_skill_registry(context.cwd)
        if args:
            skill = skill_registry.get(args)
            if skill is None:
                return CommandResult(message=f"Skill not found: {args}")
            return CommandResult(message=skill.content)
        skills = skill_registry.list_skills()
        if not skills:
            return CommandResult(message="No skills available.")
        lines = ["Available skills:"]
        for skill in skills:
            source = f" [{skill.source}]"
            lines.append(f"- {skill.name}{source}: {skill.description}")
        return CommandResult(message="\n".join(lines))

    async def _config_handler(args: str, context: CommandContext) -> CommandResult:
        del context
        settings = load_settings()
        tokens = args.split(maxsplit=2)
        if not tokens or tokens[0] == "show":
            return CommandResult(message=settings.model_dump_json(indent=2))
        if tokens[0] == "set" and len(tokens) == 3:
            key, value = tokens[1], tokens[2]
            if key not in Settings.model_fields:
                return CommandResult(message=f"Unknown config key: {key}")
            try:
                coerced = _coerce_setting_value(settings, key, value)
            except ValueError as exc:
                return CommandResult(message=str(exc))
            setattr(settings, key, coerced)
            save_settings(settings)
            return CommandResult(message=f"Updated {key}")
        return CommandResult(message="Usage: /config [show|set KEY VALUE]")

    async def _login_handler(args: str, context: CommandContext) -> CommandResult:
        del context
        settings = load_settings()
        provider = detect_provider(settings)
        api_key = args.strip()
        if not api_key:
            masked = (
                f"{settings.api_key[:6]}...{settings.api_key[-4:]}"
                if settings.api_key
                else "(not configured)"
            )
            return CommandResult(
                message=(
                    f"Auth status:\n"
                    f"- provider: {provider.name}\n"
                    f"- auth_status: {auth_status(settings)}\n"
                    f"- base_url: {settings.base_url or '(default)'}\n"
                    f"- model: {settings.model}\n"
                    f"- api_key: {masked}\n"
                    "Usage: /login API_KEY"
                )
            )
        settings.api_key = api_key
        save_settings(settings)
        return CommandResult(message="Stored API key in ~/.illusion/settings.json")

    async def _logout_handler(_: str, context: CommandContext) -> CommandResult:
        del context
        settings = load_settings()
        settings.api_key = ""
        save_settings(settings)
        return CommandResult(message="Cleared stored API key.")

    async def _feedback_handler(args: str, context: CommandContext) -> CommandResult:
        del context
        path = get_feedback_log_path()
        if not args.strip():
            return CommandResult(message=f"Feedback log: {path}\nUsage: /feedback TEXT")
        timestamp = datetime.now(timezone.utc).isoformat()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {args.strip()}\n")
        return CommandResult(message=f"Saved feedback to {path}")

    async def _fast_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        current = (
            context.app_state.get().fast_mode
            if context.app_state is not None
            else settings.fast_mode
        )
        action = args.strip() or "show"
        if action == "show":
            return CommandResult(message=f"Fast mode: {'on' if current else 'off'}")
        enabled = {"on": True, "off": False, "toggle": not current}.get(action)
        if enabled is None:
            return CommandResult(message="Usage: /fast [show|on|off|toggle]")
        settings.fast_mode = enabled
        save_settings(settings)
        if context.app_state is not None:
            context.app_state.set(fast_mode=enabled)
        return CommandResult(message=f"Fast mode {'enabled' if enabled else 'disabled'}.")

    async def _effort_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        current = context.app_state.get().effort if context.app_state is not None else settings.effort
        value = args.strip() or "show"
        if value == "show":
            return CommandResult(message=f"Reasoning effort: {current}")
        if value not in {"low", "medium", "high"}:
            return CommandResult(message="Usage: /effort [show|low|medium|high]")
        settings.effort = value
        save_settings(settings)
        context.engine.set_system_prompt(build_runtime_system_prompt(settings, cwd=context.cwd))
        if context.app_state is not None:
            context.app_state.set(effort=value)
        return CommandResult(message=f"Reasoning effort set to {value}.")

    async def _passes_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        current = context.app_state.get().passes if context.app_state is not None else settings.passes
        value = args.strip() or "show"
        if value == "show":
            return CommandResult(message=f"Passes: {current}")
        try:
            passes = max(1, min(int(value), 8))
        except ValueError:
            return CommandResult(message="Usage: /passes [show|COUNT]")
        settings.passes = passes
        save_settings(settings)
        context.engine.set_system_prompt(build_runtime_system_prompt(settings, cwd=context.cwd))
        if context.app_state is not None:
            context.app_state.set(passes=passes)
        return CommandResult(message=f"Pass count set to {passes}.")

    async def _turns_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        tokens = args.split()
        if not tokens or tokens[0] == "show":
            return CommandResult(
                message=(
                    f"Max turns (engine): {context.engine.max_turns}\n"
                    f"Max turns (config): {settings.max_turns}\n"
                    "Usage: /turns [show|COUNT]"
                )
            )
        if tokens[0] == "set" and len(tokens) == 2:
            raw = tokens[1]
        elif len(tokens) == 1:
            raw = tokens[0]
        else:
            return CommandResult(message="Usage: /turns [show|COUNT]")
        try:
            turns = int(raw)
        except ValueError:
            return CommandResult(message="Usage: /turns [show|COUNT]")
        turns = max(1, min(turns, 512))
        settings.max_turns = turns
        save_settings(settings)
        context.engine.set_max_turns(turns)
        return CommandResult(message=f"Max turns set to {turns}.")

    async def _continue_handler(args: str, context: CommandContext) -> CommandResult:
        raw = args.strip()
        if not context.engine.has_pending_continuation():
            return CommandResult(message="Nothing to continue (no pending tool results).")

        turns: int | None = None
        if raw:
            tokens = raw.split()
            if tokens[0] == "set" and len(tokens) == 2:
                raw = tokens[1]
            try:
                turns = int(raw)
            except ValueError:
                return CommandResult(message="Usage: /continue [COUNT]")
            turns = max(1, min(turns, 512))

        return CommandResult(
            message="Continuing pending tool loop...",
            continue_pending=True,
            continue_turns=turns,
        )

    async def _issue_handler(args: str, context: CommandContext) -> CommandResult:
        path = get_project_issue_file(context.cwd)
        tokens = args.split(maxsplit=1)
        action = tokens[0] if tokens else "show"
        rest = tokens[1] if len(tokens) == 2 else ""
        if action == "show":
            if not path.exists():
                return CommandResult(message=f"No issue context. File path: {path}")
            return CommandResult(message=path.read_text(encoding="utf-8"))
        if action == "set" and rest:
            title, separator, body = rest.partition("::")
            if not separator or not title.strip() or not body.strip():
                return CommandResult(message="Usage: /issue set TITLE :: BODY")
            content = f"# {title.strip()}\n\n{body.strip()}\n"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return CommandResult(message=f"Saved issue context to {path}")
        if action == "clear":
            if path.exists():
                path.unlink()
                return CommandResult(message="Cleared issue context.")
            return CommandResult(message="No issue context to clear.")
        return CommandResult(message="Usage: /issue [show|set TITLE :: BODY|clear]")

    async def _pr_comments_handler(args: str, context: CommandContext) -> CommandResult:
        path = get_project_pr_comments_file(context.cwd)
        tokens = args.split(maxsplit=1)
        action = tokens[0] if tokens else "show"
        rest = tokens[1] if len(tokens) == 2 else ""
        if action == "show":
            if not path.exists():
                return CommandResult(message=f"No PR comments context. File path: {path}")
            return CommandResult(message=path.read_text(encoding="utf-8"))
        if action == "add" and rest:
            location, separator, comment = rest.partition("::")
            if not separator or not location.strip() or not comment.strip():
                return CommandResult(message="Usage: /pr_comments add FILE[:LINE] :: COMMENT")
            existing = path.read_text(encoding="utf-8") if path.exists() else "# PR Comments\n"
            if not existing.endswith("\n"):
                existing += "\n"
            existing += f"- {location.strip()}: {comment.strip()}\n"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(existing, encoding="utf-8")
            return CommandResult(message=f"Added PR comment to {path}")
        if action == "clear":
            if path.exists():
                path.unlink()
                return CommandResult(message="Cleared PR comments context.")
            return CommandResult(message="No PR comments context to clear.")
        return CommandResult(message="Usage: /pr_comments [show|add FILE[:LINE] :: COMMENT|clear]")

    async def _mcp_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        tokens = args.split()
        if tokens and tokens[0] == "auth" and len(tokens) >= 3:
            server_name = tokens[1]
            config = settings.mcp_servers.get(server_name)
            if config is None:
                return CommandResult(message=f"Unknown MCP server: {server_name}")

            if len(tokens) == 3:
                mode = "bearer"
                key = None
                value = tokens[2]
            elif len(tokens) == 4:
                mode = tokens[2]
                key = None
                value = tokens[3]
            elif len(tokens) == 5:
                mode = tokens[2]
                key = tokens[3]
                value = tokens[4]
            else:
                return CommandResult(
                    message="Usage: /mcp auth SERVER TOKEN | /mcp auth SERVER [bearer|env] VALUE | /mcp auth SERVER header KEY VALUE"
                )

            if hasattr(config, "headers"):
                if mode not in {"bearer", "header"}:
                    return CommandResult(message="HTTP/WS MCP auth supports bearer or header modes.")
                header_key = key or "Authorization"
                header_value = (
                    f"Bearer {value}" if mode == "bearer" and header_key == "Authorization" else value
                )
                headers = dict(getattr(config, "headers", {}) or {})
                headers[header_key] = header_value
                settings.mcp_servers[server_name] = config.model_copy(update={"headers": headers})
            elif hasattr(config, "env"):
                if mode not in {"bearer", "env"}:
                    return CommandResult(message="stdio MCP auth supports bearer or env modes.")
                env_key = key or "MCP_AUTH_TOKEN"
                env_value = f"Bearer {value}" if mode == "bearer" else value
                env = dict(getattr(config, "env", {}) or {})
                env[env_key] = env_value
                settings.mcp_servers[server_name] = config.model_copy(update={"env": env})
            else:
                return CommandResult(message=f"Server {server_name} does not support auth updates")
            save_settings(settings)
            return CommandResult(message=f"Saved MCP auth for {server_name}. Restart session to reconnect.")
        return CommandResult(message=context.mcp_summary or "No MCP servers configured.")

    async def _plugin_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        tokens = args.split()
        if not tokens or tokens[0] == "list":
            return CommandResult(message=context.plugin_summary or "No plugins discovered.")
        if tokens[0] == "enable" and len(tokens) == 2:
            settings.enabled_plugins[tokens[1]] = True
            save_settings(settings)
            return CommandResult(message=f"Enabled plugin '{tokens[1]}'. Restart session to reload.")
        if tokens[0] == "disable" and len(tokens) == 2:
            settings.enabled_plugins[tokens[1]] = False
            save_settings(settings)
            return CommandResult(message=f"Disabled plugin '{tokens[1]}'. Restart session to reload.")
        if tokens[0] == "install" and len(tokens) == 2:
            path = install_plugin_from_path(tokens[1])
            return CommandResult(message=f"Installed plugin to {path}")
        if tokens[0] == "uninstall" and len(tokens) == 2:
            if uninstall_plugin(tokens[1]):
                return CommandResult(message=f"Uninstalled plugin '{tokens[1]}'")
            return CommandResult(message=f"Plugin '{tokens[1]}' not found")
        plugins = load_plugins(settings, context.cwd)
        if plugins:
            return CommandResult(message=context.plugin_summary)
        return CommandResult(message="Usage: /plugin [list|enable NAME|disable NAME|install PATH|uninstall NAME]")

    _MODE_LABELS = {"default": "Default", "plan": "Plan Mode", "full_auto": "Auto"}

    async def _permissions_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        tokens = args.split()
        if not tokens or tokens[0] == "show":
            permission = settings.permission
            label = _MODE_LABELS.get(permission.mode.value, permission.mode.value)
            return CommandResult(
                message=(
                    f"Mode: {label}\n"
                    f"Allowed tools: {permission.allowed_tools}\n"
                    f"Denied tools: {permission.denied_tools}"
                )
            )
        if tokens[0] == "set" and len(tokens) == 2:
            settings.permission.mode = PermissionMode(tokens[1])
            save_settings(settings)
            context.engine.set_permission_checker(PermissionChecker(settings.permission))
            if context.app_state is not None:
                context.app_state.set(permission_mode=settings.permission.mode.value)
            label = _MODE_LABELS.get(tokens[1], tokens[1])
            return CommandResult(message=f"Permission mode set to {label}")
        return CommandResult(message="Usage: /permissions [show|set MODE]")

    async def _plan_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        mode = args.strip() or "on"
        if mode in {"on", "enter"}:
            settings.permission.mode = PermissionMode.PLAN
            save_settings(settings)
            context.engine.set_permission_checker(PermissionChecker(settings.permission))
            if context.app_state is not None:
                context.app_state.set(permission_mode=settings.permission.mode.value)
            return CommandResult(message="Plan mode enabled.")
        if mode in {"off", "exit"}:
            settings.permission.mode = PermissionMode.DEFAULT
            save_settings(settings)
            context.engine.set_permission_checker(PermissionChecker(settings.permission))
            if context.app_state is not None:
                context.app_state.set(permission_mode=settings.permission.mode.value)
            return CommandResult(message="Plan mode disabled.")
        return CommandResult(message="Usage: /plan [on|off]")

    async def _model_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        tokens = args.split(maxsplit=1)
        if not tokens or tokens[0] == "show":
            return CommandResult(message=f"Model: {settings.model}")
        # /model set MODEL or /model MODEL (bare model name)
        if tokens[0] == "set" and len(tokens) == 2:
            model_name = tokens[1]
        elif tokens[0] not in ("set", "show") and len(tokens) == 1:
            model_name = tokens[0]
        else:
            return CommandResult(message="Usage: /model [show|set MODEL]")
        settings.model = model_name
        save_settings(settings)
        context.engine.set_model(model_name)
        if context.app_state is not None:
            context.app_state.set(model=model_name)
        return CommandResult(message=f"Model set to {model_name}.")

    async def _language_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        current = (
            str(context.app_state.get().ui_language)
            if context.app_state is not None
            else settings.ui_language
        )
        tokens = args.split()
        if not tokens or tokens[0] == "show":
            return CommandResult(message=f"UI language: {current}")
        if tokens[0] == "list":
            return CommandResult(message="Available UI languages: zh-CN, en")
        if tokens[0] == "set" and len(tokens) == 2:
            value = tokens[1]
            if value not in {"zh-CN", "en"}:
                return CommandResult(message="Usage: /language [show|list|set zh-CN|set en]")
            settings.ui_language = value
            save_settings(settings)
            if context.app_state is not None:
                context.app_state.set(ui_language=value)
            return CommandResult(message=f"UI language set to {value}")
        return CommandResult(message="Usage: /language [show|list|set zh-CN|set en]")

    async def _output_style_handler(args: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        tokens = args.split(maxsplit=1)
        styles = load_output_styles()
        available = {style.name: style for style in styles}
        current = (
            context.app_state.get().output_style
            if context.app_state is not None
            else settings.output_style
        )
        if not tokens or tokens[0] == "show":
            return CommandResult(message=f"Output style: {current}")
        if tokens[0] == "list":
            return CommandResult(
                message="\n".join(f"{style.name} [{style.source}]" for style in styles)
            )
        if tokens[0] == "set" and len(tokens) == 2:
            if tokens[1] not in available:
                return CommandResult(message=f"Unknown output style: {tokens[1]}")
            settings.output_style = tokens[1]
            save_settings(settings)
            if context.app_state is not None:
                context.app_state.set(output_style=tokens[1])
            return CommandResult(message=f"Output style set to {tokens[1]}")
        return CommandResult(message="Usage: /output-style [show|list|set NAME]")

    async def _doctor_handler(_: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        memory_dir = get_project_memory_dir(context.cwd)
        state = context.app_state.get() if context.app_state is not None else None
        lines = [
            "Doctor summary:",
            f"- cwd: {context.cwd}",
            f"- model: {settings.model}",
            f"- permission_mode: {state.permission_mode if state is not None else settings.permission.mode}",
            f"- theme: {state.theme if state is not None else settings.theme}",
            f"- output_style: {state.output_style if state is not None else settings.output_style}",
            f"- ui_language: {state.ui_language if state is not None else settings.ui_language}",
            f"- effort: {state.effort if state is not None else settings.effort}",
            f"- passes: {state.passes if state is not None else settings.passes}",
            f"- memory_dir: {memory_dir}",
            f"- plugin_count: {max(len(context.plugin_summary.splitlines()) - 1, 0) if context.plugin_summary else 0}",
            f"- mcp_configured: {'yes' if context.mcp_summary and 'No MCP' not in context.mcp_summary else 'no'}",
        ]
        return CommandResult(message="\n".join(lines))

    async def _privacy_settings_handler(_: str, context: CommandContext) -> CommandResult:
        settings = load_settings()
        session_dir = get_project_session_dir(context.cwd)
        lines = [
            "Privacy settings:",
            f"- user_config_dir: {get_config_dir()}",
            f"- project_config_dir: {get_project_config_dir(context.cwd)}",
            f"- session_dir: {session_dir}",
            f"- feedback_log: {get_feedback_log_path()}",
            f"- api_base_url: {settings.base_url or '(default Anthropic-compatible endpoint)'}",
            "- network: enabled only for provider and explicit web/MCP calls",
            "- storage: local files under ~/.illusion and project .illusion",
        ]
        return CommandResult(message="\n".join(lines))

    async def _diff_handler(args: str, context: CommandContext) -> CommandResult:
        if args.strip() == "full":
            ok, output = _run_git_command(context.cwd, "diff", "HEAD")
            return CommandResult(message=output or "(no diff)")
        ok, output = _run_git_command(context.cwd, "diff", "--stat")
        if not ok:
            return CommandResult(message=output)
        return CommandResult(message=output or "(no diff)")

    async def _branch_handler(args: str, context: CommandContext) -> CommandResult:
        action = args.strip() or "show"
        if action == "show":
            ok, current = _run_git_command(context.cwd, "branch", "--show-current")
            if not ok:
                return CommandResult(message=current)
            return CommandResult(message=f"Current branch: {current or '(detached HEAD)'}")
        if action == "list":
            ok, branches = _run_git_command(context.cwd, "branch", "--format", "%(refname:short)")
            return CommandResult(message=branches if ok else branches)
        return CommandResult(message="Usage: /branch [show|list]")

    async def _commit_handler(args: str, context: CommandContext) -> CommandResult:
        message = args.strip()
        if not message:
            ok, status = _run_git_command(context.cwd, "status", "--short")
            return CommandResult(message=status if ok and status else "(working tree clean)")
        ok, status = _run_git_command(context.cwd, "status", "--short")
        if not ok:
            return CommandResult(message=status)
        if not status.strip():
            return CommandResult(message="Nothing to commit.")
        ok, output = _run_git_command(context.cwd, "add", "-A")
        if not ok:
            return CommandResult(message=output)
        ok, output = _run_git_command(context.cwd, "commit", "-m", message)
        return CommandResult(message=output if ok else output)

    async def _tasks_handler(args: str, context: CommandContext) -> CommandResult:
        manager = get_task_manager()
        tokens = args.split(maxsplit=2)
        if not tokens or tokens[0] == "list":
            tasks = manager.list_tasks()
            if not tasks:
                return CommandResult(message="No background tasks.")
            return CommandResult(
                message="\n".join(f"{task.id} {task.type} {task.status} {task.description}" for task in tasks)
            )
        if tokens[0] == "run" and len(tokens) >= 2:
            command = args[len("run ") :]
            task = await manager.create_shell_task(
                command=command,
                description=command[:80],
                cwd=context.cwd,
            )
            return CommandResult(message=f"Started task {task.id}")
        if tokens[0] == "stop" and len(tokens) == 2:
            task = await manager.stop_task(tokens[1])
            return CommandResult(message=f"Stopped task {task.id}")
        if tokens[0] == "show" and len(tokens) == 2:
            task = manager.get_task(tokens[1])
            if task is None:
                return CommandResult(message=f"No task found with ID: {tokens[1]}")
            return CommandResult(message=str(task))
        if tokens[0] == "update" and len(tokens) == 3:
            task_id = tokens[1]
            rest = tokens[2]
            field, _, value = rest.partition(" ")
            if not value.strip():
                return CommandResult(
                    message="Usage: /tasks update ID [description TEXT|progress NUMBER|note TEXT]"
                )
            try:
                if field == "description":
                    task = manager.update_task(task_id, description=value)
                    return CommandResult(message=f"Updated task {task.id} description")
                if field == "progress":
                    try:
                        progress = int(value)
                    except ValueError:
                        return CommandResult(message="Progress must be an integer between 0 and 100.")
                    task = manager.update_task(task_id, progress=progress)
                    return CommandResult(message=f"Updated task {task.id} progress to {progress}%")
                if field == "note":
                    task = manager.update_task(task_id, status_note=value)
                    return CommandResult(message=f"Updated task {task.id} note")
            except ValueError as exc:
                return CommandResult(message=str(exc))
            return CommandResult(
                message="Usage: /tasks update ID [description TEXT|progress NUMBER|note TEXT]"
            )
        if tokens[0] == "output" and len(tokens) == 2:
            return CommandResult(message=manager.read_task_output(tokens[1]) or "(no output)")
        return CommandResult(
            message=(
                "Usage: /tasks "
                "[list|run CMD|stop ID|show ID|update ID description TEXT|update ID progress NUMBER|update ID note TEXT|output ID]"
            )
        )

    async def _delete_handler(args: str, context: CommandContext) -> CommandResult:
        from illusion.services.session_storage import (
            delete_all_sessions,
            delete_session_by_id,
            list_session_snapshots,
        )

        tokens = args.strip().split()

        # /delete — 列出会话供选择
        if not tokens:
            sessions = list_session_snapshots(context.cwd, limit=10)
            if not sessions:
                return CommandResult(message="No saved sessions found for this project.")
            import time
            lines = ["Saved sessions:"]
            for s in sessions:
                ts = time.strftime("%m/%d %H:%M", time.localtime(s["created_at"]))
                summary = s["summary"][:50] or "(no summary)"
                lines.append(f"  {s['session_id']}  {ts}  {s['message_count']}msg  {summary}")
            lines.append("")
            lines.append("Usage: /delete <session_id>  — delete a specific session")
            lines.append("       /delete all           — delete all sessions")
            return CommandResult(message="\n".join(lines))

        # /delete all / /delete __all__ — 清除所有会话
        if tokens[0] in ("all", "__all__"):
            count = delete_all_sessions(context.cwd)
            return CommandResult(message=f"Deleted {count} session file(s).")

        # /delete <session_id> — 删除指定会话
        sid = tokens[0]
        if delete_session_by_id(context.cwd, sid):
            return CommandResult(message=f"Deleted session: {sid}")
        return CommandResult(message=f"Session not found: {sid}")

    async def _rules_handler(args: str, context: CommandContext) -> CommandResult:
        from illusion.skills.loader import get_project_rules_dir

        rules_dir = get_project_rules_dir(context.cwd)
        rule_files = sorted(rules_dir.glob("*.md"))

        if not rule_files:
            return CommandResult(message=f"No rules found in {rules_dir}")

        tokens = args.strip().split()

        # /rules — 列出所有规则
        if not tokens:
            lines = [f"Rules directory: {rules_dir}", ""]
            for i, path in enumerate(rule_files, 1):
                # 读取第一行作为预览
                content = path.read_text(encoding="utf-8", errors="replace").strip()
                first_line = content.split("\n", 1)[0][:60] if content else "(empty)"
                lines.append(f"  {i}. {path.stem}  —  {first_line}")
            lines.append("")
            lines.append("Usage: /rules <name|number>  — view a specific rule")
            return CommandResult(message="\n".join(lines))

        # /rules <name|number> — 显示指定规则内容
        target = tokens[0]
        selected = None

        # 按编号选择
        try:
            idx = int(target) - 1
            if 0 <= idx < len(rule_files):
                selected = rule_files[idx]
        except ValueError:
            pass

        # 按名称选择
        if selected is None:
            for path in rule_files:
                if path.stem.lower() == target.lower():
                    selected = path
                    break

        if selected is None:
            return CommandResult(message=f"Rule not found: {target}. Use /rules to list available rules.")

        content = selected.read_text(encoding="utf-8", errors="replace").strip()
        return CommandResult(message=f"# {selected.stem}\n\n{content}")

    registry.register(SlashCommand("help", "Show available commands", _help_handler))
    registry.register(SlashCommand("exit", "Exit IllusionCode", _exit_handler))
    registry.register(SlashCommand("clear", "Clear conversation history", _clear_handler))
    registry.register(SlashCommand("new", "Start a new conversation session", _new_handler))
    registry.register(SlashCommand("version", "Show the installed IllusionCode version", _version_handler))
    registry.register(SlashCommand("status", "Show session status", _status_handler))
    registry.register(SlashCommand("context", "Show the active runtime system prompt", _context_handler))
    registry.register(SlashCommand("summary", "Summarize conversation history", _summary_handler))
    registry.register(SlashCommand("compact", "Compact older conversation history", _compact_handler))
    registry.register(SlashCommand("cost", "Show token usage and estimated cost", _cost_handler))
    registry.register(SlashCommand("usage", "Show usage and token estimates", _usage_handler))
    registry.register(SlashCommand("stats", "Show session statistics", _stats_handler))
    registry.register(SlashCommand("memory", "Inspect and manage project memory", _memory_handler))
    registry.register(SlashCommand("hooks", "Show configured hooks", _hooks_handler))
    registry.register(SlashCommand("resume", "Restore the latest saved session", _resume_handler))
    registry.register(SlashCommand("export", "Export the current transcript", _export_handler))
    registry.register(SlashCommand("share", "Create a shareable transcript snapshot", _share_handler))
    registry.register(SlashCommand("copy", "Copy the latest response or provided text", _copy_handler))
    registry.register(SlashCommand("rewind", "Remove the latest conversation turn(s)", _rewind_handler))
    registry.register(SlashCommand("files", "List files in the current workspace", _files_handler))
    registry.register(SlashCommand("init", "Initialize project IllusionCode files", _init_handler))
    registry.register(SlashCommand("bridge", "Inspect bridge helpers and spawn bridge sessions", _bridge_handler))
    registry.register(SlashCommand("login", "Show auth status or store an API key", _login_handler))
    registry.register(SlashCommand("logout", "Clear the stored API key", _logout_handler))
    registry.register(SlashCommand("feedback", "Save CLI feedback to the local feedback log", _feedback_handler))
    registry.register(SlashCommand("skills", "List or show available skills", _skills_handler))
    registry.register(SlashCommand("config", "Show or update configuration", _config_handler))
    registry.register(SlashCommand("mcp", "Show MCP status", _mcp_handler))
    registry.register(SlashCommand("plugin", "Manage plugins", _plugin_handler))
    registry.register(SlashCommand("reload-plugins", "Reload plugin discovery for this workspace", _reload_plugins_handler))
    registry.register(SlashCommand("permissions", "Show or update permission mode", _permissions_handler))
    registry.register(SlashCommand("plan", "Toggle plan permission mode", _plan_handler))
    registry.register(SlashCommand("fast", "Show or update fast mode", _fast_handler))
    registry.register(SlashCommand("effort", "Show or update reasoning effort", _effort_handler))
    registry.register(SlashCommand("passes", "Show or update reasoning pass count", _passes_handler))
    registry.register(SlashCommand("turns", "Show or update maximum agentic turn count", _turns_handler))
    registry.register(SlashCommand("continue", "Continue the previous tool loop if it was interrupted", _continue_handler))
    registry.register(SlashCommand("model", "Show or update the default model", _model_handler))
    registry.register(SlashCommand("language", "Show or update UI language", _language_handler))
    registry.register(SlashCommand("output-style", "Show or update output style", _output_style_handler))
    registry.register(SlashCommand("doctor", "Show environment diagnostics", _doctor_handler))
    registry.register(SlashCommand("diff", "Show git diff output", _diff_handler))
    registry.register(SlashCommand("branch", "Show git branch information", _branch_handler))
    registry.register(SlashCommand("commit", "Show status or create a git commit", _commit_handler))
    registry.register(SlashCommand("issue", "Show or update project issue context", _issue_handler))
    registry.register(SlashCommand("pr_comments", "Show or update project PR comments context", _pr_comments_handler))
    registry.register(SlashCommand("privacy-settings", "Show local privacy and storage settings", _privacy_settings_handler))
    registry.register(SlashCommand("agents", "List or inspect agent and teammate tasks", _agents_handler))
    registry.register(SlashCommand("tasks", "Manage background tasks", _tasks_handler))
    registry.register(SlashCommand("delete", "Delete saved sessions", _delete_handler))
    registry.register(SlashCommand("rules", "View project rules", _rules_handler))
    return registry
