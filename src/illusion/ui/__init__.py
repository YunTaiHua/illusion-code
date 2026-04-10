"""
UI 模块
=======

本模块提供 IllusionCode 用户界面的核心功能。

主要组件：
    - run_repl: 运行交互式 REPL（默认的 React 终端界面）
    - run_print_mode: 运行非交互式打印模式（适合脚本和自动化任务）

使用示例：
    >>> from illusion.ui import run_repl, run_print_mode
    >>> 
    >>> # 启动交互式 REPL
    >>> await run_repl()
    >>> 
    >>> # 运行单次交互模式
    >>> await run_print_mode(prompt="帮我写一个 hello world 程序")
"""

from illusion.ui.app import run_repl, run_print_mode

__all__ = ["run_repl", "run_print_mode"]
