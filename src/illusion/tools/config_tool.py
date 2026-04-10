"""
配置工具
========

本模块提供读取和更新 IllusionCode 配置设置的功能。

主要组件：
    - ConfigTool: 读取或更新配置的工，使用示例：
    >>> from illusion.tools import ConfigTool
    >>> tool = ConfigTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.config.settings import load_settings, save_settings
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class ConfigToolInput(BaseModel):
    """配置访问参数。

    属性：
        action: 操作类型，show 或 set
        key: 配置键名
        value: 配置值
    """

    action: str = Field(default="show", description="show or set")
    key: str | None = Field(default=None)
    value: str | None = Field(default=None)


class ConfigTool(BaseTool):
    """读取或更新 IllusionCode 配置设置。

    用于查看或更改 IllusionCode 设置。当用户请求配置更改、询问当前设置时使用此工具。
    """

    name = "config"
    description = """Get or set Illusion Code configuration settings.

View or change Illusion Code settings. Use when the user requests configuration changes, asks about current settings, or when adjusting a setting would benefit them.

## Usage
- **Get current value:** Omit the "value" parameter
- **Set new value:** Include the "value" parameter

## Configurable settings list
The following settings are available for you to change:

### Global Settings (stored in ~/.illusion.json)
- theme: "dark", "light", "ansi" - Terminal color theme
- verbose: true/false - Show detailed output
- permissions.defaultMode: "accept-edits", "plan", "accept-all" - Default permission mode
- model: Model override (sonnet, opus, haiku, best, or full model ID)

### Project Settings (stored in settings.json)
- outputStyle: Output style configuration
- language: Language preference for responses

## Model
- model - Override the default model. Available options:
  - null/"default": Use the default model
  - "sonnet": Illusion Sonnet (fast, capable)
  - "opus": Illusion Opus (most capable)
  - "haiku": Illusion Haiku (fastest)
  - "best": Automatically select the best model

## Examples
- Get theme: { "setting": "theme" }
- Set dark theme: { "setting": "theme", "value": "dark" }
- Enable verbose: { "setting": "verbose", "value": true }
- Change model: { "setting": "model", "value": "opus" }
- Change permission mode: { "setting": "permissions.defaultMode", "value": "plan" }"""
    input_model = ConfigToolInput

    async def execute(self, arguments: ConfigToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        # 加载当前设置
        settings = load_settings()
        # 显示当前所有配置
        if arguments.action == "show":
            return ToolResult(output=settings.model_dump_json(indent=2))
        # 设置配置值
        if arguments.action == "set" and arguments.key and arguments.value is not None:
            # 检查配置键是否存在
            if not hasattr(settings, arguments.key):
                return ToolResult(output=f"Unknown config key: {arguments.key}", is_error=True)
            # 更新配置值
            setattr(settings, arguments.key, arguments.value)
            # 保存设置
            save_settings(settings)
            return ToolResult(output=f"Updated {arguments.key}")
        return ToolResult(output="Usage: action=show or action=set with key/value", is_error=True)
