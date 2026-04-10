"""
输出样式加载模块
=============

本模块提供输出样式的加载功能。

主要功能：
    - 获取自定义输出样式目录
    - 加载内置和自定义输出样式

类说明：
    - OutputStyle: 命名输出样式数据类
    - get_output_styles_dir: 获取自定义输出样式目录
    - load_output_styles: 加载内置和自定义输出样式

使用示例：
    >>> from illusion.output_styles import load_output_styles
    >>> # 加载输出样式
    >>> styles = load_output_styles()
    >>> for style in styles:
    >>>     print(style.name, style.source)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from illusion.config.paths import get_config_dir


@dataclass(frozen=True)
class OutputStyle:
    """命名输出样式。"""

    name: str
    content: str
    source: str


def get_output_styles_dir() -> Path:
    """返回自定义输出样式目录。"""
    path = get_config_dir() / "output_styles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_output_styles() -> list[OutputStyle]:
    """加载内置和自定义输出样式。"""
    # 内置样式
    styles = [
        OutputStyle(name="default", content="Standard rich console output.", source="builtin"),
        OutputStyle(name="minimal", content="Very terse plain-text output.", source="builtin"),
    ]
    # 加载自定义样式
    for path in sorted(get_output_styles_dir().glob("*.md")):
        styles.append(
            OutputStyle(
                name=path.stem,
                content=path.read_text(encoding="utf-8"),
                source="user",
            )
        )
    return styles