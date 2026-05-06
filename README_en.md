# IllusionCode

<div align="center">

**AI-Powered Command-Line Programming Assistant**

*Python port of Claude Code | Adapted from OpenHarness (0.1.0)*

[中文版](README.md) | English

</div>

---

## 📖 Introduction

IllusionCode is an open-source AI-powered command-line programming assistant, migrated and adapted from OpenHarness (0.1.0) with full Claude Code prompt injection and optimized details and configurations. It helps developers efficiently complete software engineering tasks. It supports multiple AI providers, offers a rich set of tools and command systems, and features multi-agent collaboration capabilities.

### Core Features

- 🪟 **Deep Windows Optimization** - Auto-detect Git, PowerShell support, path compatibility optimization
- 🖥️ **Zero Terminal Flicker** - Stable rendering based on Ink Static component, suppressing resize event interference
- 🌍 **Full Chinese Support** - Command system, UI selectors, error messages fully localized for better Chinese user experience
- 📝 **Markdown Terminal Rendering** - Supports tables, bold, italic, inline code, links and other rich text styles
- 📂 **Project-Level Config Friendly** - Auto-generate skills 、 rules 、 mcp 、 plunges directories, project-level skills override global ones
- 🤖 **Multi AI Provider Support** - Anthropic Claude, OpenAI, GitHub Copilot, Alibaba Cloud DashScope, etc.
- 🛠️ **Rich Toolset** - 38+ built-in tools + MCP dynamic tool extension
- ⌨️ **51 Slash Commands** - Covering session management, configuration, project operations, task scheduling, etc.
- 🧠 **Multi-Agent Collaboration** - 7 built-in specialized Agents, supporting task orchestration
- 🔌 **Flexible Extension System** - Plugins, hooks, skills, MCP servers
- 🔐 **Comprehensive Permission Control** - Three modes + fine-grained rules + Always Allow one-click approval
- 💾 **Memory & Context** - Project knowledge persistence and dynamic retrieval
- 🎨 **Modern Terminal Interface** - React + Ink component-based TUI

### Project Highlights

**Windows User Friendly**: Auto-detect Git installation path, unified PowerShell and Bash tool processing, automatic path separator compatibility, out-of-the-box experience for Windows users.

**Zero Terminal Flicker**: Uses Ink `<Static>` component architecture, static rendering for completed messages, dynamic rendering for streaming messages, completely solving terminal flicker issues.

**Chinese Experience First**: All 51 slash commands support Chinese responses, UI selectors fully localized, multi-line messages translated line by line, error messages bilingual.

**Markdown Rich Text Rendering**: Full rendering of tables, bold, italic, inline code, links and other formats in terminal, significantly improving AI response readability.

**Project-Level Config Automation**: Auto-detect `<project>/.claude/rules/` and `<project>/.claude/skills/` directories, project-level configuration takes precedence over global configuration, facilitating team collaboration.

---

## 🚀 Quick Start

### Requirements

- Python >= 3.10
- Node.js (for frontend TUI)
- Supports Windows, macOS, Linux
- Windows users: Auto-detect Git, no manual PATH configuration needed

### Installation

```bash
git clone https://github.com/your-repo/illusion-code.git
cd illusion-code
uv sync
```

### Basic Usage

```bash
# Start interactive session (recommended)
illusion

# Non-interactive print mode
illusion -p "Analyze the structure of this project"

# Specify model
illusion -m sonnet

# Continue most recent session
illusion --continue

# Restore specific session
illusion --resume <session-id>

# Set permission mode
illusion --permission-mode full_auto

# Specify API provider
illusion --api-format copilot
```

---

## 📚 Command System

### Subcommands

```bash
# Authentication management
illusion auth login              # Login
illusion auth status             # View authentication status
illusion auth logout             # Logout
illusion auth switch <provider>  # Switch provider

# MCP management
illusion mcp list                # List MCP servers
illusion mcp add <name> <config> # Add server
illusion mcp remove <name>       # Remove server

# Plugin management
illusion plugin list             # List plugins
illusion plugin install <source> # Install plugin
illusion plugin uninstall <name> # Uninstall plugin

# Scheduled tasks
illusion cron start              # Start scheduler
illusion cron stop               # Stop scheduler
illusion cron status             # View status
illusion cron list               # List tasks
```

### Interactive Slash Commands

In interactive sessions, you can use the following commands:

| Category | Command Examples | Description |
|----------|------------------|-------------|
| Session Management | `/help`, `/clear`, `/exit`, `/rewind`, `/delete` | Manage session state |
| Memory Snapshots | `/memory`, `/resume`, `/export`, `/rules` | Memory and session management |
| Configuration | `/config`, `/model`, `/permissions`, `/plan` | Adjust runtime configuration |
| Plugin Extensions | `/skills`, `/hooks`, `/mcp`, `/plugin` | Manage extension features |
| Project Git | `/init`, `/diff`, `/branch`, `/commit` | Project and version control |
| Multi-Agent | `/agents`, `/tasks`, `/continue` | Agent collaboration |

---

## 🏗️ Project Architecture

```
illusion-code/
├── src/illusion/           # Main source code
│   ├── api/                # API clients (Anthropic, OpenAI, Copilot, etc.)
│   ├── auth/               # Authentication management
│   ├── commands/           # Slash command system (51 commands)
│   ├── config/             # Configuration system
│   ├── coordinator/        # Multi-agent coordinator
│   ├── engine/             # Core conversation engine
│   ├── hooks/              # Hook system
│   ├── mcp/                # MCP client
│   ├── memory/             # Memory system
│   ├── permissions/        # Permission system
│   ├── plugins/            # Plugin system
│   ├── prompts/            # Prompt system
│   ├── skills/             # Skill system
│   ├── tasks/              # Task management
│   ├── tools/              # Toolset (38+ tools)
│   ├── ui/                 # User interface
│   └── cli.py              # CLI entry point
├── frontend/terminal/      # React TUI frontend
├── tests/                  # Test suite
└── pyproject.toml          # Project configuration
```

---

## 🔧 Core Modules

### API Client Layer

Supports multiple AI providers:

| Provider | API Format | Authentication |
|----------|------------|----------------|
| Anthropic Claude | anthropic | API Key / OAuth |
| OpenAI | openai | API Key |
| GitHub Copilot | copilot | OAuth Device Flow |
| Alibaba Cloud DashScope | openai | API Key |
| AWS Bedrock | anthropic | API Key |
| Google Vertex | anthropic | API Key |

### Tool System

Provides 38+ core tools, covering:

- **File I/O**: `bash`, `read_file`, `write_file`, `edit_file`
- **Search**: `glob`, `grep`, `web_fetch`, `web_search`
- **Task Management**: `task_create`, `task_list`, `task_stop`
- **Scheduled Tasks**: `cron_create`, `cron_list`, `cron_toggle`
- **Multi-Agent**: `agent`, `send_message`, `team_create`
- **Mode Switching**: `enter_plan_mode`, `exit_plan_mode`

### Permission System

Three permission modes:

| Mode | Description |
|------|-------------|
| `default` | Modification tools require user confirmation |
| `plan` | Block all modification tools |
| `full_auto` | Allow all operations |

### Multi-Agent Coordinator

Built-in 7 specialized Agents:

| Agent | Purpose |
|-------|---------|
| `general-purpose` | General research and multi-step tasks |
| `Explore` | Read-only file search expert |
| `Plan` | Read-only architecture/planning expert |
| `verification` | Adversarial verification expert |
| `worker` | Implementation-oriented Worker |
| `statusline-setup` | Shell PS1 converter |
| `claude-code-guide` | Documentation expert |

---

## 🎨 Frontend Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.3.1 | UI framework |
| Ink | 5.1.0 | Terminal UI component library |
| TypeScript | 5.7.3 | Type safety |

---

## 📦 Main Dependencies

| Dependency | Purpose |
|------------|---------|
| anthropic | Anthropic SDK |
| openai | OpenAI SDK |
| rich | Rich text output |
| prompt-toolkit | Advanced input processing |
| textual | TUI framework |
| typer | CLI framework |
| pydantic | Data validation |
| httpx | HTTP client |
| mcp | MCP protocol |

---

## ⚙️ Configuration Files

### Configuration Overview

| File | Location | Scope | Purpose |
|------|----------|-------|---------|
| `settings.json` | `~/.illusion/settings.json` | Global | Main settings file, API config, permissions, hooks, etc. |
| `credentials.json` | `~/.illusion/credentials.json` | Global | Secure credential storage (API keys, etc.) |
| `CLAUDE.md` | Project root | Project-level | Project instructions and context |
| `MEMORY.md` | Project root | Project-level | Memory entry file |
| `.illusion/mcp/*.json` | Project root | Project-level | MCP server configuration |
| `.illusion/rules/*.md` | Project root | Project-level | Project rule files |

### Configuration Priority

Configuration resolution priority (from high to low):

1. **CLI Arguments** - Command-line arguments have the highest priority
2. **Environment Variables** - Such as `ANTHROPIC_API_KEY`, `illusion_MODEL`, etc.
3. **Configuration Files** - `~/.illusion/settings.json`
4. **Default Values** - Built-in default configurations

---

### Global Configuration (settings.json)

Global configuration file is located at `~/.illusion/settings.json` and applies to all projects.

#### Configuration Methods

settings.json supports two configuration methods:

**Method 1: Flat Configuration (Simple Format)**

Directly set API-related fields at the top level, suitable for single-provider scenarios:

```json
{
  "api_key": "nvapi-xxxxx",
  "model": "stepfun-ai/step-3.5-flash",
  "max_tokens": 16384,
  "base_url": "https://integrate.api.nvidia.com/v1",
  "api_format": "openai",
  "max_turns": 200
}
```

**Method 2: Profile Configuration (Advanced Format)**

Manage multiple provider configurations through `profiles`, suitable for scenarios requiring switching between different providers:

```json
{
  "active_profile": "nvidia-nim",
  "profiles": {
    "nvidia-nim": {
      "label": "NVIDIA NIM",
      "provider": "nvidia",
      "api_format": "openai",
      "auth_source": "openai_api_key",
      "default_model": "stepfun-ai/step-3.5-flash",
      "base_url": "https://integrate.api.nvidia.com/v1"
    }
  }
}
```

> **Tip**: Both methods can be mixed. Flat fields will be automatically converted to Profile configuration. Profile configuration is recommended for easier management of multiple providers.

#### Complete Configuration Structure

```json
{
  "api_key": "",
  "model": "claude-sonnet-4-6",
  "max_tokens": 16384,
  "base_url": null,
  "api_format": "anthropic",
  "provider": "",
  "active_profile": "claude-api",
  "profiles": {},
  "max_turns": 200,
  "system_prompt": null,
  "permission": {
    "mode": "default",
    "allowed_tools": [],
    "denied_tools": [],
    "path_rules": [],
    "denied_commands": []
  },
  "hooks": {},
  "memory": {
    "enabled": true,
    "max_files": 5,
    "max_entrypoint_lines": 200
  },
  "sandbox": {
    "enabled": false,
    "fail_if_unavailable": false,
    "enabled_platforms": [],
    "network": {
      "allowed_domains": [],
      "denied_domains": []
    },
    "filesystem": {
      "allow_read": [],
      "deny_read": [],
      "allow_write": ["."],
      "deny_write": []
    }
  },
  "enabled_plugins": {},
  "mcp_servers": {},
  "ui_language": "en",
  "output_style": "default",
  "fast_mode": false,
  "effort": "medium",
  "passes": 1,
  "verbose": false
}
```

#### Configuration Field Description

| Field | Type | Default | Description | Example |
|-------|------|---------|-------------|---------|
| `api_key` | string | "" | API key (recommend using environment variables or credential storage) | `"sk-ant-xxxxx"` |
| `model` | string | "claude-sonnet-4-6" | Default model | `"claude-opus-4-6"` |
| `max_tokens` | int | 16384 | Maximum output token count | `32768` |
| `base_url` | string\|null | null | Custom API endpoint | `"https://api.example.com/v1"` |
| `api_format` | string | "anthropic" | API format: anthropic/openai/copilot | `"openai"` |
| `provider` | string | "" | Provider identifier | `"anthropic"` |
| `active_profile` | string | "claude-api" | Currently active profile name | `"my-custom-profile"` |
| `profiles` | object | {} | User-defined provider profiles | `{"my-profile": {...}}` |
| `max_turns` | int | 200 | Maximum conversation turns | `500` |
| `system_prompt` | string\|null | null | Custom system prompt | `"You are a professional Python developer"` |
| `ui_language` | string | "en" | UI language | `"zh-CN"` |
| `fast_mode` | bool | false | Fast mode | `true` |
| `effort` | string | "medium" | Effort level: low/medium/high | `"high"` |
| `verbose` | bool | false | Verbose output mode | `true` |

---

### Provider Configuration (Provider Profiles)

IllusionCode supports multiple AI providers, configured through `profiles` for different workflows.

#### Built-in Provider Profiles

| Profile Name | Provider | API Format | Authentication | Default Model |
|--------------|----------|------------|----------------|---------------|
| `claude-api` | Anthropic | anthropic | API Key | claude-sonnet-4-6 |
| `claude-subscription` | Anthropic Claude | anthropic | Claude Subscription | claude-sonnet-4-6 |
| `openai-compatible` | OpenAI | openai | API Key | gpt-5.4 |
| `codex` | OpenAI Codex | openai | Codex Subscription | gpt-5.4 |
| `copilot` | GitHub Copilot | copilot | OAuth | gpt-5.4 |

#### Provider Configuration Format

```json
{
  "profiles": {
    "my-custom-profile": {
      "label": "My Custom Configuration",
      "provider": "anthropic",
      "api_format": "anthropic",
      "auth_source": "anthropic_api_key",
      "default_model": "claude-sonnet-4-6",
      "base_url": null,
      "last_model": null
    }
  }
}
```

#### ProviderProfile Field Description

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | Yes | Display name |
| `provider` | string | Yes | Provider identifier |
| `api_format` | string | Yes | API format: anthropic/openai/copilot |
| `auth_source` | string | Yes | Authentication source |
| `default_model` | string | Yes | Default model |
| `base_url` | string\|null | No | Custom API endpoint |
| `last_model` | string\|null | No | Last used model |

#### Multi-Model Configuration Example

Configure multiple models under the same provider, switch through different profiles:

```json
{
  "active_profile": "nvidia-step-flash",
  "profiles": {
    "nvidia-step-flash": {
      "label": "NVIDIA - Step 3.5 Flash",
      "provider": "nvidia",
      "api_format": "openai",
      "auth_source": "openai_api_key",
      "default_model": "stepfun-ai/step-3.5-flash",
      "base_url": "https://integrate.api.nvidia.com/v1"
    },
    "nvidia-minimax": {
      "label": "NVIDIA - MiniMax M2.7",
      "provider": "nvidia",
      "api_format": "openai",
      "auth_source": "openai_api_key",
      "default_model": "minimaxai/minimax-m2.7",
      "base_url": "https://integrate.api.nvidia.com/v1"
    }
  }
}
```

**Ways to switch models**:

```bash
# Method 1: Use /model command to switch
/model

# Method 2: Use -m parameter to specify model
illusion -m minimaxai/minimax-m2.7

# Method 3: Modify active_profile field
# Change active_profile to "nvidia-minimax" in settings.json
```

---

### Provider Configuration Examples

#### 1. Anthropic Claude API

```json
{
  "active_profile": "claude-api",
  "profiles": {
    "claude-api": {
      "label": "Claude API",
      "provider": "anthropic",
      "api_format": "anthropic",
      "auth_source": "anthropic_api_key",
      "default_model": "claude-sonnet-4-6"
    }
  }
}
```

**Authentication**:
- Environment variable: `ANTHROPIC_API_KEY`
- Credential storage: `illusion auth login anthropic`

**Supported Model Aliases**:
| Alias | Actual Model | Description |
|-------|--------------|-------------|
| `default` | claude-sonnet-4-6 | Recommended model |
| `best` | claude-opus-4-6 | Most powerful model |
| `sonnet` | claude-sonnet-4-6 | Daily coding |
| `opus` | claude-opus-4-6 | Complex reasoning |
| `haiku` | claude-haiku-4-5 | Fastest model |
| `sonnet[1m]` | claude-sonnet-4-6[1m] | 1M context |
| `opus[1m]` | claude-opus-4-6[1m] | 1M context |
| `opusplan` | Dynamic selection | Plan mode uses Opus |

---

#### 2. Claude Subscription

```json
{
  "active_profile": "claude-subscription",
  "profiles": {
    "claude-subscription": {
      "label": "Claude Subscription",
      "provider": "anthropic_claude",
      "api_format": "anthropic",
      "auth_source": "claude_subscription",
      "default_model": "claude-sonnet-4-6"
    }
  }
}
```

**Authentication**:
```bash
illusion auth claude-login
```

---

#### 3. OpenAI API

```json
{
  "active_profile": "openai-compatible",
  "profiles": {
    "openai-compatible": {
      "label": "OpenAI Compatible",
      "provider": "openai",
      "api_format": "openai",
      "auth_source": "openai_api_key",
      "default_model": "gpt-5.4"
    }
  }
}
```

**Authentication**:
- Environment variable: `OPENAI_API_KEY`
- Credential storage: `illusion auth login openai`

---

#### 4. OpenAI Codex Subscription

```json
{
  "active_profile": "codex",
  "profiles": {
    "codex": {
      "label": "Codex Subscription",
      "provider": "openai_codex",
      "api_format": "openai",
      "auth_source": "codex_subscription",
      "default_model": "gpt-5.4"
    }
  }
}
```

**Authentication**:
```bash
illusion auth codex-login
```

---

#### 5. GitHub Copilot

```json
{
  "active_profile": "copilot",
  "profiles": {
    "copilot": {
      "label": "GitHub Copilot",
      "provider": "copilot",
      "api_format": "copilot",
      "auth_source": "copilot_oauth",
      "default_model": "gpt-5.4"
    }
  }
}
```

**Authentication**:
```bash
illusion auth login copilot
```

---

#### 6. Alibaba Cloud DashScope

```json
{
  "active_profile": "dashscope",
  "profiles": {
    "dashscope": {
      "label": "Alibaba Cloud DashScope",
      "provider": "dashscope",
      "api_format": "openai",
      "auth_source": "dashscope_api_key",
      "default_model": "qwen-max",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    }
  }
}
```

**Authentication**:
- Environment variable: `DASHSCOPE_API_KEY`
- Credential storage: `illusion auth login dashscope`

---

#### 7. AWS Bedrock

```json
{
  "active_profile": "bedrock",
  "profiles": {
    "bedrock": {
      "label": "AWS Bedrock",
      "provider": "bedrock",
      "api_format": "anthropic",
      "auth_source": "bedrock_api_key",
      "default_model": "anthropic.claude-3-sonnet"
    }
  }
}
```

**Authentication**:
- Configure AWS credentials (~/.aws/credentials)
- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

---

#### 8. Google Vertex AI

```json
{
  "active_profile": "vertex",
  "profiles": {
    "vertex": {
      "label": "Google Vertex AI",
      "provider": "vertex",
      "api_format": "anthropic",
      "auth_source": "vertex_api_key",
      "default_model": "claude-3-sonnet"
    }
  }
}
```

**Authentication**:
- Configure Google Cloud credentials
- Environment variable: `GOOGLE_APPLICATION_CREDENTIALS`

---

#### 9. Custom OpenAI Compatible Endpoint

```json
{
  "active_profile": "custom-llm",
  "profiles": {
    "custom-llm": {
      "label": "Custom LLM",
      "provider": "openai",
      "api_format": "openai",
      "auth_source": "openai_api_key",
      "default_model": "llama-3-70b",
      "base_url": "https://api.your-llm.com/v1"
    }
  }
}
```

---

#### 10. NVIDIA NIM

NVIDIA NIM provides API services for various open-source models:

```json
{
  "active_profile": "nvidia-nim",
  "profiles": {
    "nvidia-nim": {
      "label": "NVIDIA NIM",
      "provider": "nvidia",
      "api_format": "openai",
      "auth_source": "openai_api_key",
      "default_model": "meta/llama-3.1-405b-instruct",
      "base_url": "https://integrate.api.nvidia.com/v1"
    }
  }
}
```

**Authentication**:
- Environment variable: `NVIDIA_API_KEY` or `OPENAI_API_KEY`
- Get API Key: https://build.nvidia.com/

**Supported Model Examples**:
| Model ID | Description |
|----------|-------------|
| `meta/llama-3.1-405b-instruct` | Llama 3.1 405B |
| `meta/llama-3.1-70b-instruct` | Llama 3.1 70B |
| `mistralai/mistral-large` | Mistral Large |
| `stepfun-ai/step-3.5-flash` | Step 3.5 Flash |

**Simple Configuration Format**:

```json
{
  "api_key": "nvapi-xxxxx",
  "model": "stepfun-ai/step-3.5-flash",
  "max_tokens": 16384,
  "base_url": "https://integrate.api.nvidia.com/v1",
  "api_format": "openai"
}
```

---

### Project-Level Configuration

Project-level configuration only applies to the current project and is placed in the project root directory.

#### CLAUDE.md - Project Instructions

Create a `CLAUDE.md` file in the project root to provide project-specific context and instructions for AI:

```markdown
# Project Description

This is a Python Web project using the FastAPI framework.

## Code Standards

- Use Python 3.10+ features
- Follow PEP 8 code style
- Use type hints

## Directory Structure

- src/api: API routes
- src/models: Data models
- src/services: Business logic

## Notes

- Do not modify files in the tests/ directory
- Run pytest before committing
```

#### .illusion/rules/ - Rule Files

Create `.md` files in the `.illusion/rules/` directory, each file is an independent rule:

```
Project Root/
├── .illusion/
│   └── rules/
│       ├── python-style.md
│       ├── git-workflow.md
│       └── testing.md
```

#### MCP Server Configuration

MCP servers support three configuration methods, with priority from high to low: **Plugin > Project-level > Global settings**

##### 1. Global Configuration (settings.json)

Configure in the `mcp_servers` field of `~/.illusion/settings.json`, applies to all projects:

```json
{
  "mcp_servers": {
    "solidworks": {
      "type": "stdio",
      "command": "python",
      "args": ["E:\\claudecode\\SolidWorks-MCP\\server.py"]
    }
  }
}
```

You can also manage via command line:
```bash
illusion mcp list                # List MCP servers
illusion mcp add <name> <config> # Add server
illusion mcp remove <name>       # Remove server
```

##### 2. Project-level Configuration (.illusion/mcp/)

Create `.json` files in the `.illusion/mcp/` directory under the project root, only applies to the current project (directory auto-generated):

**Method 1: Single Server Configuration (filename as server name)**

```json
// .illusion/mcp/solidworks.json
{
  "type": "stdio",
  "command": "python",
  "args": ["E:\\claudecode\\SolidWorks-MCP\\server.py"]
}
```

**Method 2: Multiple Server Configuration (using mcpServers key)**

```json
// .illusion/mcp/servers.json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./data"],
      "env": {
        "NODE_OPTIONS": "--max-old-space-size=4096"
      }
    },
    "database": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server_postgres"],
      "env": {
        "DATABASE_URL": "postgresql://localhost/mydb"
      }
    },
    "remote-api": {
      "type": "http",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer your-token"
      }
    },
    "websocket-service": {
      "type": "ws",
      "url": "wss://ws.example.com/mcp",
      "headers": {}
    }
  }
}
```

##### 3. Plugin Configuration

Place `.mcp.json` or `mcp.json` files in the plugin directory, loaded automatically with the plugin:

```
~/.illusion/plugins/my-plugin/
├── plugin.json      # Plugin manifest
├── .mcp.json        # MCP config (or mcp.json)
└── ...
```

MCP servers from plugins are registered with the format `plugin_name:server_name` to avoid conflicts with other configurations.

##### MCP Server Configuration Types

| Type | Fields | Description |
|------|--------|-------------|
| `stdio` | command, args, env, cwd | Communication via standard input/output |
| `http` | url, headers | Communication via HTTP protocol |
| `ws` | url, headers | Communication via WebSocket protocol |

---

### Permission Configuration

#### Permission Modes

| Mode | Value | Description |
|------|-------|-------------|
| Default Mode | `default` | Modification tools require user confirmation |
| Plan Mode | `plan` | Block all modification tools |
| Full Auto Mode | `full_auto` | Allow all operations |

#### Permission Configuration Example

```json
{
  "permission": {
    "mode": "default",
    "allowed_tools": ["read_file", "grep", "glob"],
    "denied_tools": ["bash"],
    "path_rules": [
      {"pattern": "src/**", "allow": true},
      {"pattern": "secrets/**", "allow": false}
    ],
    "denied_commands": ["/init", "/commit"]
  }
}
```

---

### Hook Configuration

Hooks allow executing custom operations when specific events occur.

#### Supported Hook Types

| Hook Event | Description |
|------------|-------------|
| `PRE_TOOL_USE` | Before tool execution |
| `POST_TOOL_USE` | After tool execution |
| `USER_PROMPT_SUBMIT` | After user prompt submission |

#### Hook Configuration Example

```json
{
  "hooks": {
    "PRE_TOOL_USE": [
      {
        "type": "command",
        "command": "echo 'Tool: $TOOL_NAME' >> /tmp/tool.log",
        "timeout_seconds": 30,
        "block_on_failure": false
      }
    ],
    "POST_TOOL_USE": [
      {
        "type": "http",
        "url": "https://hooks.example.com/tool-complete",
        "headers": {"Authorization": "Bearer token"},
        "timeout_seconds": 10
      }
    ],
    "USER_PROMPT_SUBMIT": [
      {
        "type": "prompt",
        "prompt": "Check if user input contains sensitive information",
        "block_on_failure": true
      }
    ]
  }
}
```

#### Hook Type Details

| Type | Required Fields | Optional Fields | Description |
|------|-----------------|-----------------|-------------|
| `command` | command | timeout_seconds, matcher, block_on_failure | Execute Shell command |
| `prompt` | prompt | model, timeout_seconds, matcher, block_on_failure | Use LLM for verification |
| `http` | url | headers, timeout_seconds, matcher, block_on_failure | Send HTTP request |
| `agent` | prompt | model, timeout_seconds, matcher, block_on_failure | Use Agent for verification |

---

### Environment Variables

Supported environment variables:

| Variable Name | Description |
|---------------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `DASHSCOPE_API_KEY` | Alibaba Cloud DashScope API key |
| `ANTHROPIC_MODEL` / `illusion_MODEL` | Default model |
| `ANTHROPIC_BASE_URL` / `illusion_BASE_URL` | API endpoint |
| `illusion_MAX_TOKENS` | Maximum token count |
| `illusion_MAX_TURNS` | Maximum conversation turns |
| `illusion_API_FORMAT` | API format |
| `illusion_PROVIDER` | Provider |
| `illusion_SANDBOX_ENABLED` | Whether to enable sandbox |
| `ILLUSION_CONFIG_DIR` | Configuration directory path |
| `ILLUSION_DATA_DIR` | Data directory path |
| `ILLUSION_LOGS_DIR` | Logs directory path |

---

### Memory System Configuration

```json
{
  "memory": {
    "enabled": true,
    "max_files": 5,
    "max_entrypoint_lines": 200
  }
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `enabled` | true | Whether to enable memory function |
| `max_files` | 5 | Maximum number of memory files |
| `max_entrypoint_lines` | 200 | Maximum lines for entry file |

---

### Sandbox Configuration

```json
{
  "sandbox": {
    "enabled": true,
    "fail_if_unavailable": false,
    "enabled_platforms": ["linux", "darwin"],
    "network": {
      "allowed_domains": ["api.anthropic.com"],
      "denied_domains": ["internal.company.com"]
    },
    "filesystem": {
      "allow_read": ["./src", "./docs"],
      "deny_read": ["./secrets"],
      "allow_write": ["./output"],
      "deny_write": ["./.git"]
    }
  }
}
```

---

## 🔌 Extension Development

### Hook System

Supports multiple hook types:

- `PRE_TOOL_USE` - Before tool execution
- `POST_TOOL_USE` - After tool execution
- `USER_PROMPT_SUBMIT` - After user prompt submission

### Plugin System

Defined through `plugin.json` manifest:

- Skills
- Commands
- Hooks
- MCP Servers

## 🧪 Development & Testing

```bash
# Install development dependencies
uv sync --dev

# Run tests
pytest

```

---

## 📄 License

This project is open-sourced under the [MIT](LICENSE) license.

---

## 🤝 Contributing

Welcome to submit Issues and Pull Requests!

---

</div>
