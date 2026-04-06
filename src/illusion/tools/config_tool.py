"""Tool for reading and updating settings."""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.config.settings import load_settings, save_settings
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class ConfigToolInput(BaseModel):
    """Arguments for config access."""

    action: str = Field(default="show", description="show or set")
    key: str | None = Field(default=None)
    value: str | None = Field(default=None)


class ConfigTool(BaseTool):
    """Read or update IllusionCode settings."""

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
- editorMode: "vim" - Enable vim keybindings
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
- Enable vim mode: { "setting": "editorMode", "value": "vim" }
- Enable verbose: { "setting": "verbose", "value": true }
- Change model: { "setting": "model", "value": "opus" }
- Change permission mode: { "setting": "permissions.defaultMode", "value": "plan" }"""
    input_model = ConfigToolInput

    async def execute(self, arguments: ConfigToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        settings = load_settings()
        if arguments.action == "show":
            return ToolResult(output=settings.model_dump_json(indent=2))
        if arguments.action == "set" and arguments.key and arguments.value is not None:
            if not hasattr(settings, arguments.key):
                return ToolResult(output=f"Unknown config key: {arguments.key}", is_error=True)
            setattr(settings, arguments.key, arguments.value)
            save_settings(settings)
            return ToolResult(output=f"Updated {arguments.key}")
        return ToolResult(output="Usage: action=show or action=set with key/value", is_error=True)
