"""
主题配置模式模块
================

本模块定义主题配置的数据模型。

主要组件：
    - ColorsConfig: 颜色配置
    - BorderConfig: 边框样式配置
    - IconConfig: 图标/符号配置
    - LayoutConfig: 布局配置
    - ThemeConfig: 完整主题配置

使用示例：
    >>> from illusion.themes.schema import ThemeConfig, ColorsConfig
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ColorsConfig(BaseModel):
    """主题颜色配置
    
    定义终端界面使用的颜色方案。
    
    Attributes:
        primary: 主色
        secondary: 次要色
        accent: 强调色
        error: 错误色
        muted: 弱化色
        background: 背景色
        foreground: 前景色
    """

    primary: str = "#5875d4"  # 主色
    secondary: str = "#4a9eff"  # 次要色
    accent: str = "#61afef"  # 强调色
    error: str = "#e06c75"  # 错误色
    muted: str = "#5c6370"  # 弱化色
    background: str = "#282c34"  # 背景色
    foreground: str = "#abb2bf"  # 前景色


class BorderConfig(BaseModel):
    """边框样式配置
    
    定义终端边框的样式和字符。
    
    Attributes:
        style: 边框样式（rounded/single/double/none）
        char: 自定义边框字符
    """

    style: Literal["rounded", "single", "double", "none"] = "rounded"  # 边框样式
    char: str | None = None  # 自定义边框字符


class IconConfig(BaseModel):
    """图标/符号配置
    
    定义终端界面使用的各种符号。
    
    Attributes:
        spinner: 加载动画符号
        tool: 工具符号
        error: 错误符号
        success: 成功符号
        agent: 智能体符号
    """

    spinner: str = "⠋"  # 加载动画
    tool: str = "⚙"  # 工具
    error: str = "✖"  # 错误
    success: str = "✔"  # 成功
    agent: str = "◆"  # 智能体


class LayoutConfig(BaseModel):
    """布局配置
    
    定义终端界面的布局选项。
    
    Attributes:
        compact: 是否使用紧凑模式
        show_tokens: 是否显示令牌数量
        show_time: 是否显示时间
    """

    compact: bool = False  # 紧凑模式
    show_tokens: bool = True  # 显示令牌数量
    show_time: bool = True  # 显示时间


class ThemeConfig(BaseModel):
    """完整主题配置
    
    组合所有配置项的完整主题定义。
    
    Attributes:
        name: 主题名称
        colors: 颜色配置
        borders: 边框配置
        icons: 图标配置
        layout: 布局配置
    """

    name: str  # 主题名称
    colors: ColorsConfig = ColorsConfig()  # 颜色配置
    borders: BorderConfig = BorderConfig()  # 边框配置
    icons: IconConfig = IconConfig()  # 图标配置
    layout: LayoutConfig = LayoutConfig()  # 布局配置
