"""
IllusionCode 程序入口模块
========================

本模块作为 IllusionCode 的入口点，支持通过 `python -m illusion` 运行。

使用示例：
    >>> python -m illusion                    # 启动交互式会话
    >>> python -m illusion -p "你的提示词"     # 非交互式打印模式
"""

from illusion.cli import app  # 从 CLI 模块导入主应用程序

if __name__ == "__main__":  # 当直接运行此模块时执行主应用
    app()  # 启动 CLI 应用程序
