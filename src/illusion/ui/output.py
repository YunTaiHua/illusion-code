"""
Output 输出模块
=============

本模块实现基于 rich 的终端渲染辅助功能。

主要功能：
    - Markdown 渲染
    - 语法高亮
    - 加载动画（spinner）
    - 工具执行状态显示

类说明：
    - OutputRenderer: 终端渲染器类

使用示例：
    >>> from illusion.ui.output import OutputRenderer
    >>> 
    >>> # 创建渲染器
    >>> renderer = OutputRenderer(style_name="default")
    >>> 
    >>> # 处理流式事件
    >>> renderer.render_event(event)
    >>> 
    >>> # 打印系统消息
    >>> renderer.print_system("任务已完成")
"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from illusion.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    StreamEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)


class OutputRenderer:
    """终端渲染器类。

    使用 rich 格式化渲染模型和工具事件到终端。
    支持 Markdown、语法高亮和加载动画。

    Attributes:
        console: Rich Console 实例
        _assistant_line_open: 助手行是否处于打开状态
        _assistant_buffer: 助手输出缓冲区
        _style_name: 样式名称
        _spinner_status: 加载动画状态
        _last_tool_input: 上一个工具输入参数
    """

    def __init__(self, style_name: str = "default") -> None:
        # 创建 Rich Console 实例
        self.console = Console()
        # 初始化状态
        self._assistant_line_open = False
        self._assistant_buffer = ""
        self._style_name = style_name
        self._spinner_status = None
        self._last_tool_input: dict | None = None

    def set_style(self, style_name: str) -> None:
        """设置输出样式。

        Args:
            style_name: 样式名称
        """
        self._style_name = style_name

    def show_thinking(self) -> None:
        """在第一个助手 token 到达之前显示思考加载动画。"""
        # 如果已有加载动画，则跳过
        if self._spinner_status is not None:
            return
        # minimal 样式不显示加载动画
        if self._style_name == "minimal":
            return
        # 创建并启动加载动画
        self._spinner_status = self.console.status(
            "[cyan]Thinking...[/cyan]", spinner="dots"
        )
        self._spinner_status.start()

    def start_assistant_turn(self) -> None:
        """开始助手回合。

        停止加载动画，准备输出助手文本。
        """
        # 停止加载动画
        self._stop_spinner()
        # 如果助手行已打开，先换行
        if self._assistant_line_open:
            self.console.print()
        # 重置缓冲区
        self._assistant_buffer = ""
        self._assistant_line_open = True
        # 根据样式打印提示符
        if self._style_name == "minimal":
            self.console.print("a> ", end="", style="green")
        else:
            self.console.print("[green bold]\u23fa[/green bold] ", end="")

    def render_event(self, event: StreamEvent) -> None:
        """渲染流式事件。

        Args:
            event: 流式事件对象
        """
        # 助手文本增量事件
        if isinstance(event, AssistantTextDelta):
            self._assistant_buffer += event.text
            # 流式输出原始文本以保持响应性
            self.console.print(event.text, end="", markup=False, highlight=False)
            return

        # 助手回合完成事件
        if isinstance(event, AssistantTurnComplete):
            if self._assistant_line_open:
                self.console.print()
                # 如果缓冲区包含 Markdown 指示符，则使用 Markdown 重新渲染
                if _has_markdown(self._assistant_buffer) and self._style_name != "minimal":
                    self.console.print()
                    self.console.print(Markdown(self._assistant_buffer.strip()))
                self._assistant_line_open = False
                self._assistant_buffer = ""
            return

        # 工具开始执行事件
        if isinstance(event, ToolExecutionStarted):
            self._stop_spinner()
            if self._assistant_line_open:
                self.console.print()
                self._assistant_line_open = False
            # 获取工具名称和输入摘要
            tool_name = event.tool_name
            summary = _summarize_tool_input(tool_name, event.tool_input)
            self._last_tool_input = event.tool_input
            # 根据样式渲染
            if self._style_name == "minimal":
                self.console.print(f"  > {tool_name} {summary}")
            else:
                self.console.print(
                    f"  [bold cyan]\u23f5 {tool_name}[/bold cyan] [dim]{summary}[/dim]"
                )
                self._start_spinner(tool_name)
            return

        # 工具执行完成事件
        if isinstance(event, ToolExecutionCompleted):
            self._stop_spinner()
            tool_name = event.tool_name
            output = event.output
            is_error = event.is_error
            # minimal 样式简单输出
            if self._style_name == "minimal":
                self.console.print(f"    {output}")
                return
            # 错误输出显示为红色面板
            if is_error:
                self.console.print(Panel(output, title=f"{tool_name} error", border_style="red", padding=(0, 1)))
                return
            # 根据工具类型渲染输出
            tool_input = getattr(event, "tool_input", None) or self._last_tool_input
            self._render_tool_output(tool_name, tool_input, output)

    def print_system(self, message: str) -> None:
        """打印系统消息。

        Args:
            message: 系统消息文本
        """
        self._stop_spinner()
        if self._assistant_line_open:
            self.console.print()
            self._assistant_line_open = False
        if self._style_name == "minimal":
            self.console.print(message)
        else:
            self.console.print(f"[yellow]\u2139 {message}[/yellow]")

    def print_status_line(
        self,
        *,
        model: str = "unknown",
        input_tokens: int = 0,
        output_tokens: int = 0,
        permission_mode: str = "default",
    ) -> None:
        """在每回合后打印紧凑状态行。

        Args:
            model: 模型名称
            input_tokens: 输入 token 数量
            output_tokens: 输出 token 数量
            permission_mode: 权限模式
        """
        parts = [f"[cyan]model: {model}[/cyan]"]
        if input_tokens > 0 or output_tokens > 0:
            down = "\u2193"
            up = "\u2191"
            parts.append(f"tokens: {_fmt_num(input_tokens)}{down} {_fmt_num(output_tokens)}{up}")
        parts.append(f"mode: {permission_mode}")
        sep = " \u2502 "
        line = sep.join(parts)
        self.console.print(f"[dim]{line}[/dim]")

    def clear(self) -> None:
        """清空终端屏幕。"""
        self.console.clear()

    def _start_spinner(self, tool_name: str) -> None:
        """启动工具执行加载动画。

        Args:
            tool_name: 工具名称
        """
        if self._style_name == "minimal":
            return
        self._spinner_status = self.console.status(f"Running {tool_name}...", spinner="dots")
        self._spinner_status.start()

    def _stop_spinner(self) -> None:
        """停止加载动画。"""
        if self._spinner_status is not None:
            self._spinner_status.stop()
            self._spinner_status = None

    def _render_tool_output(self, tool_name: str, tool_input: dict | None, output: str) -> None:
        """渲染工具输出。

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
            output: 工具输出文本
        """
        lower = tool_name.lower()
        # Bash：在面板中显示
        if lower == "bash":
            cmd = (tool_input or {}).get("command", "")
            title = f"$ {cmd[:80]}" if cmd else "Bash"
            self.console.print(Panel(output[:2000], title=title, border_style="dim", padding=(0, 1)))
            return
        # Read/FileRead：根据文件扩展名进行语法高亮
        if lower in ("read", "fileread", "file_read"):
            file_path = str((tool_input or {}).get("file_path", ""))
            ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
            lexer = _ext_to_lexer(ext)
            if lexer and len(output) < 5000:
                self.console.print(Syntax(output, lexer, theme="monokai", line_numbers=True, word_wrap=True))
            else:
                self.console.print(Panel(output[:2000], title=file_path, border_style="dim", padding=(0, 1)))
            return
        # Edit/FileEdit：显示为 diff 风格
        if lower in ("edit", "fileedit", "file_edit"):
            file_path = str((tool_input or {}).get("file_path", ""))
            self.console.print(Panel(output[:2000], title=f"Edit: {file_path}", border_style="green", padding=(0, 1)))
            return
        # Grep：显示搜索结果
        if lower in ("grep", "greptool"):
            self.console.print(Panel(output[:2000], title="Search results", border_style="cyan", padding=(0, 1)))
            return
        # Default：变暗文本并截断
        lines = output.split("\n")
        if len(lines) > 15:
            display = "\n".join(lines[:12]) + f"\n... ({len(lines) - 12} more lines)"
        else:
            display = output
        self.console.print(f"    [dim]{display}[/dim]")


def _has_markdown(text: str) -> bool:
    """检查文本是否可能包含 Markdown 格式化。

    Args:
        text: 要检查的文本

    Returns:
        bool: 是否可能包含 Markdown
    """
    indicators = ["```", "## ", "### ", "- ", "* ", "1. ", "**", "__", "> "]
    return any(ind in text for ind in indicators)


def _summarize_tool_input(tool_name: str, tool_input: dict | None) -> str:
    """生成工具输入的紧凑摘要。

    Args:
        tool_name: 工具名称
        tool_input: 工具输入参数

    Returns:
        str: 工具输入摘要
    """
    if not tool_input:
        return ""
    lower = tool_name.lower()
    # Bash：显示命令
    if lower == "bash" and "command" in tool_input:
        return str(tool_input["command"])[:120]
    # Read：显示文���路���
    if lower in ("read", "fileread", "file_read") and "file_path" in tool_input:
        return str(tool_input["file_path"])
    # Write：显示文件路径
    if lower in ("write", "filewrite", "file_write") and "file_path" in tool_input:
        return str(tool_input["file_path"])
    # Edit：显示文件路径
    if lower in ("edit", "fileedit", "file_edit") and "file_path" in tool_input:
        return str(tool_input["file_path"])
    # Grep：显示搜索模式
    if lower in ("grep", "greptool") and "pattern" in tool_input:
        return f"/{tool_input['pattern']}/"
    # Glob：显示 glob 模式
    if lower in ("glob", "globtool") and "pattern" in tool_input:
        return str(tool_input["pattern"])
    # Default：显示第一个键值对
    entries = list(tool_input.items())
    if entries:
        k, v = entries[0]
        return f"{k}={str(v)[:60]}"
    return ""


def _ext_to_lexer(ext: str) -> str | None:
    """将文件扩展名映射到语法高亮lexer。

    Args:
        ext: 文件扩展名

    Returns:
        str | None: lexer 名称
    """
    mapping = {
        "py": "python", "js": "javascript", "ts": "typescript", "tsx": "tsx",
        "jsx": "jsx", "rs": "rust", "go": "go", "rb": "ruby", "java": "java",
        "c": "c", "cpp": "cpp", "h": "c", "hpp": "cpp", "cs": "csharp",
        "sh": "bash", "bash": "bash", "zsh": "bash", "json": "json",
        "yaml": "yaml", "yml": "yaml", "toml": "toml", "xml": "xml",
        "html": "html", "css": "css", "sql": "sql", "md": "markdown",
        "txt": None,
    }
    return mapping.get(ext.lower())


def _fmt_num(n: int) -> str:
    """格式化数字（添加千位分隔符）。

    Args:
        n: 数字

    Returns:
        str: 格式化的数字字符串
    """
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)