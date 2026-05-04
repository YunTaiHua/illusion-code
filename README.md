# IllusionCode

<div align="center">

**AI 驱动的命令行编程助手**

*Claude Code 的 Python 移植版本 | OpenHarness（0.1.0）的改编版本*

</div>

---

## 📖 项目简介

IllusionCode 是一个开源的 AI 驱动命令行编程助手，由 OpenHarness（0.1.0）迁移改编而来，全量注入claude code提示词，并优化了一些细节和配置，帮助开发者高效完成软件工程任务。它支持多种 AI 提供商，提供丰富的工具集和命令系统，并具备多智能体协作能力。

### 核心特性

- 🤖 **多 AI 提供商支持** - Anthropic Claude、OpenAI、GitHub Copilot、阿里云 DashScope 等
- 🛠️ **丰富的工具集** - 38+ 内置工具 + MCP 动态工具扩展
- ⌨️ **51 个斜杠命令** - 覆盖会话管理、配置、项目操作、任务调度等
- 🧠 **多智能体协作** - 7 种内置专业 Agent，支持任务编排
- 🔌 **灵活扩展系统** - 插件、钩子、技能、MCP 服务器
- 🔐 **完善权限控制** - 三种模式 + 细粒度规则
- 💾 **记忆与上下文** - 项目知识持久化与动态检索
- 🎨 **现代终端界面** - React + Ink 组件化 TUI

---

## 🚀 快速开始

### 环境要求

- Python >= 3.10
- Node.js (用于前端 TUI)
- 支持 Windows、macOS、Linux

### 安装

```bash
git clone https://github.com/your-repo/illusion-code.git
cd illusion-code
uv sync
```

### 基本使用

```bash
# 启动交互式会话（推荐）
illusion

# 非交互式打印模式
illusion -p "帮我分析这个项目的结构"

# 指定模型
illusion -m sonnet

# 继续最近会话
illusion --continue

# 恢复指定会话
illusion --resume <session-id>

# 设置权限模式
illusion --permission-mode full_auto

# 指定 API 提供商
illusion --api-format copilot
```

---

## 📚 命令系统

### 子命令

```bash
# 认证管理
illusion auth login              # 登录
illusion auth status             # 查看认证状态
illusion auth logout             # 登出
illusion auth switch <provider>  # 切换提供商

# MCP 管理
illusion mcp list                # 列出 MCP 服务器
illusion mcp add <name> <config> # 添加服务器
illusion mcp remove <name>       # 移除服务器

# 插件管理
illusion plugin list             # 列出插件
illusion plugin install <source> # 安装插件
illusion plugin uninstall <name> # 卸载插件

# 定时任务
illusion cron start              # 启动调度器
illusion cron stop               # 停止调度器
illusion cron status             # 查看状态
illusion cron list               # 列出任务
```

### 交互式斜杠命令

在交互式会话中，可使用以下命令：

| 类别 | 命令示例 | 说明 |
|------|----------|------|
| 会话管理 | `/help`, `/clear`, `/exit`, `/rewind`, `/delete` | 管理会话状态 |
| 记忆快照 | `/memory`, `/resume`, `/export`, `/rules` | 记忆与会话管理 |
| 配置设置 | `/config`, `/model`, `/permissions`, `/plan` | 调整运行配置 |
| 插件扩展 | `/skills`, `/hooks`, `/mcp`, `/plugin` | 管理扩展功能 |
| 项目 Git | `/init`, `/diff`, `/branch`, `/commit` | 项目与版本控制 |
| 多智能体 | `/agents`, `/tasks`, `/continue` | Agent 协作 |

---

## 🏗️ 项目架构

```
illusion-code/
├── src/illusion/           # 主要源代码
│   ├── api/                # API 客户端 (Anthropic, OpenAI, Copilot 等)
│   ├── auth/               # 认证管理
│   ├── commands/           # 斜杠命令系统 (51 个命令)
│   ├── config/             # 配置系统
│   ├── coordinator/        # 多智能体协调器
│   ├── engine/             # 核心对话引擎
│   ├── hooks/              # 钩子系统
│   ├── mcp/                # MCP 客户端
│   ├── memory/             # 记忆系统
│   ├── permissions/        # 权限系统
│   ├── plugins/            # 插件系统
│   ├── prompts/            # 提示词系统
│   ├── skills/             # 技能系统
│   ├── tasks/              # 任务管理
│   ├── tools/              # 工具集 (38+ 个工具)
│   ├── ui/                 # 用户界面
│   └── cli.py              # CLI 入口
├── frontend/terminal/      # React TUI 前端
├── tests/                  # 测试套件
└── pyproject.toml          # 项目配置
```

---

## 🔧 核心模块

### API 客户端层

支持多种 AI 提供商：

| 提供商 | API 格式 | 认证方式 |
|--------|----------|----------|
| Anthropic Claude | anthropic | API Key / OAuth |
| OpenAI | openai | API Key |
| GitHub Copilot | copilot | OAuth Device Flow |
| 阿里云 DashScope | openai | API Key |
| AWS Bedrock | anthropic | API Key |
| Google Vertex | anthropic | API Key |

### 工具系统

提供 38+ 个核心工具，涵盖：

- **文件 I/O**: `bash`, `read_file`, `write_file`, `edit_file`
- **搜索**: `glob`, `grep`, `web_fetch`, `web_search`
- **任务管理**: `task_create`, `task_list`, `task_stop`
- **定时任务**: `cron_create`, `cron_list`, `cron_toggle`
- **多智能体**: `agent`, `send_message`, `team_create`
- **模式切换**: `enter_plan_mode`, `exit_plan_mode`

### 权限系统

三种权限模式：

| 模式 | 说明 |
|------|------|
| `default` | 修改类工具需要用户确认 |
| `plan` | 阻止所有修改类工具 |
| `full_auto` | 允许一切操作 |

### 多智能体协调器

内置 7 种专业 Agent：

| Agent | 用途 |
|-------|------|
| `general-purpose` | 通用研究和多步任务 |
| `Explore` | 只读文件搜索专家 |
| `Plan` | 只读架构/规划专家 |
| `verification` | 对抗性验证专家 |
| `worker` | 实现导向的 Worker |
| `statusline-setup` | Shell PS1 转换器 |
| `claude-code-guide` | 文档专家 |

---

## 🎨 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.3.1 | UI 框架 |
| Ink | 5.1.0 | 终端 UI 组件库 |
| TypeScript | 5.7.3 | 类型安全 |

---

## 📦 主要依赖

| 依赖 | 用途 |
|------|------|
| anthropic | Anthropic SDK |
| openai | OpenAI SDK |
| rich | 富文本输出 |
| prompt-toolkit | 高级输入处理 |
| textual | TUI 框架 |
| typer | CLI 框架 |
| pydantic | 数据验证 |
| httpx | HTTP 客户端 |
| mcp | MCP 协议 |

---

## ⚙️ 配置文件

### 配置文件概览

| 文件 | 位置 | 作用域 | 用途 |
|------|------|--------|------|
| `settings.json` | `~/.illusion/settings.json` | 全局 | 主设置文件，API配置、权限、钩子等 |
| `credentials.json` | `~/.illusion/credentials.json` | 全局 | 安全凭据存储（API密钥等） |
| `CLAUDE.md` | 项目根目录 | 项目级 | 项目指令和上下文 |
| `MEMORY.md` | 项目根目录 | 项目级 | 记忆入口文件 |
| `.mcp.json` | 项目根目录 | 项目级 | MCP 服务器配置 |
| `.claude/rules/*.md` | 项目根目录 | 项目级 | 项目规则文件 |

### 配置优先级

配置解析优先级（从高到低）：

1. **CLI 参数** - 命令行传入的参数优先级最高
2. **环境变量** - 如 `ANTHROPIC_API_KEY`、`illusion_MODEL` 等
3. **配置文件** - `~/.illusion/settings.json`
4. **默认值** - 代码内置的默认配置

---

### 全局配置 (settings.json)

全局配置文件位于 `~/.illusion/settings.json`，对所有项目生效。

#### 配置方式

settings.json 支持两种配置方式：

**方式一：扁平配置（简单格式）**

直接在顶层设置 API 相关字段，适合单一提供商场景：

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

**方式二：Profile 配置（高级格式）**

通过 `profiles` 管理多个提供商配置，适合需要切换不同提供商的场景：

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

> **提示**：两种方式可以混用。扁平字段会被自动转换为 Profile 配置。推荐使用 Profile 配置以便于管理多个提供商。

#### 完整配置结构

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
  "ui_language": "zh-CN",
  "output_style": "default",
  "fast_mode": false,
  "effort": "medium",
  "passes": 1,
  "verbose": false
}
```

#### 配置字段说明

| 字段 | 类型 | 默认值 | 说明 | 示例 |
|------|------|--------|------|------|
| `api_key` | string | "" | API 密钥（建议使用环境变量或凭据存储） | `"sk-ant-xxxxx"` |
| `model` | string | "claude-sonnet-4-6" | 默认模型 | `"claude-opus-4-6"` |
| `max_tokens` | int | 16384 | 最大输出 token 数 | `32768` |
| `base_url` | string\|null | null | 自定义 API 端点 | `"https://api.example.com/v1"` |
| `api_format` | string | "anthropic" | API 格式：anthropic/openai/copilot | `"openai"` |
| `provider` | string | "" | 提供商标识符 | `"anthropic"` |
| `active_profile` | string | "claude-api" | 当前激活的配置文件名 | `"my-custom-profile"` |
| `profiles` | object | {} | 用户自定义的提供商配置文件 | `{"my-profile": {...}}` |
| `max_turns` | int | 200 | 最大对话轮数 | `500` |
| `system_prompt` | string\|null | null | 自定义系统提示词 | `"你是一个专业的Python开发者"` |
| `ui_language` | string | "zh-CN" | 界面语言 | `"en-US"` |
| `fast_mode` | bool | false | 快速模式 | `true` |
| `effort` | string | "medium" | 工作量级别：low/medium/high | `"high"` |
| `verbose` | bool | false | 详细输出模式 | `true` |

---

### 提供商配置 (Provider Profiles)

IllusionCode 支持多种 AI 提供商，通过 `profiles` 配置不同的工作流。

#### 内置提供商配置文件

| 配置文件名 | 提供商 | API 格式 | 认证方式 | 默认模型 |
|------------|--------|----------|----------|----------|
| `claude-api` | Anthropic | anthropic | API Key | claude-sonnet-4-6 |
| `claude-subscription` | Anthropic Claude | anthropic | Claude 订阅 | claude-sonnet-4-6 |
| `openai-compatible` | OpenAI | openai | API Key | gpt-5.4 |
| `codex` | OpenAI Codex | openai | Codex 订阅 | gpt-5.4 |
| `copilot` | GitHub Copilot | copilot | OAuth | gpt-5.4 |

#### 提供商配置格式

```json
{
  "profiles": {
    "my-custom-profile": {
      "label": "我的自定义配置",
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

#### ProviderProfile 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `label` | string | 是 | 显示名称 |
| `provider` | string | 是 | 提供商标识符 |
| `api_format` | string | 是 | API 格式：anthropic/openai/copilot |
| `auth_source` | string | 是 | 认证来源 |
| `default_model` | string | 是 | 默认模型 |
| `base_url` | string\|null | 否 | 自定义 API 端点 |
| `last_model` | string\|null | 否 | 上次使用的模型 |

#### 多模型配置示例

在同一个提供商下配置多个模型，通过不同的 profile 切换：

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

**切换模型的方式**：

```bash
# 方式一：使用 /model 命令切换
/model

# 方式二：使用 -m 参数指定模型
illusion -m minimaxai/minimax-m2.7

# 方式三：修改 active_profile 字段
# 在 settings.json 中将 active_profile 改为 "nvidia-minimax"
```

---

### 各提供商配置示例

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

**认证方式**：
- 环境变量：`ANTHROPIC_API_KEY`
- 凭据存储：`illusion auth login anthropic`

**支持的模型别名**：
| 别名 | 实际模型 | 说明 |
|------|----------|------|
| `default` | claude-sonnet-4-6 | 推荐模型 |
| `best` | claude-opus-4-6 | 最强模型 |
| `sonnet` | claude-sonnet-4-6 | 日常编码 |
| `opus` | claude-opus-4-6 | 复杂推理 |
| `haiku` | claude-haiku-4-5 | 最快模型 |
| `sonnet[1m]` | claude-sonnet-4-6[1m] | 1M 上下文 |
| `opus[1m]` | claude-opus-4-6[1m] | 1M 上下文 |
| `opusplan` | 动态选择 | 计划模式使用 Opus |

---

#### 2. Claude 订阅 (Claude Subscription)

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

**认证方式**：
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

**认证方式**：
- 环境变量：`OPENAI_API_KEY`
- 凭据存储：`illusion auth login openai`

---

#### 4. OpenAI Codex 订阅

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

**认证方式**：
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

**认证方式**：
```bash
illusion auth login copilot
```

---

#### 6. 阿里云 DashScope

```json
{
  "active_profile": "dashscope",
  "profiles": {
    "dashscope": {
      "label": "阿里云 DashScope",
      "provider": "dashscope",
      "api_format": "openai",
      "auth_source": "dashscope_api_key",
      "default_model": "qwen-max",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    }
  }
}
```

**认证方式**：
- 环境变量：`DASHSCOPE_API_KEY`
- 凭据存储：`illusion auth login dashscope`

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

**认证方式**：
- 配置 AWS 凭据（~/.aws/credentials）
- 环境变量：`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`

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

**认证方式**：
- 配置 Google Cloud 凭据
- 环境变量：`GOOGLE_APPLICATION_CREDENTIALS`

---

#### 9. 自定义 OpenAI 兼容端点

```json
{
  "active_profile": "custom-llm",
  "profiles": {
    "custom-llm": {
      "label": "自定义 LLM",
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

NVIDIA NIM 提供多种开源模型的 API 服务：

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

**认证方式**：
- 环境变量：`NVIDIA_API_KEY` 或 `OPENAI_API_KEY`
- 获取 API Key：https://build.nvidia.com/

**支持的模型示例**：
| 模型 ID | 说明 |
|---------|------|
| `meta/llama-3.1-405b-instruct` | Llama 3.1 405B |
| `meta/llama-3.1-70b-instruct` | Llama 3.1 70B |
| `mistralai/mistral-large` | Mistral Large |
| `stepfun-ai/step-3.5-flash` | Step 3.5 Flash |

**简单配置格式**：

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

### 项目级配置

项目级配置仅对当前项目生效，放置在项目根目录。

#### CLAUDE.md - 项目指令

在项目根目录创建 `CLAUDE.md` 文件，为 AI 提供项目特定的上下文和指令：

```markdown
# 项目说明

这是一个 Python Web 项目，使用 FastAPI 框架。

## 代码规范

- 使用 Python 3.10+ 特性
- 遵循 PEP 8 代码风格
- 使用 type hints

## 目录结构

- src/api: API 路由
- src/models: 数据模型
- src/services: 业务逻辑

## 注意事项

- 不要修改 tests/ 目录下的文件
- 提交前运行 pytest
```

#### .claude/rules/ - 规则文件

在 `.claude/rules/` 目录下创建 `.md` 文件，每个文件是一条独立规则：

```
项目根目录/
├── .claude/
│   └── rules/
│       ├── python-style.md
│       ├── git-workflow.md
│       └── testing.md
```

#### .mcp.json - MCP 服务器配置

在项目根目录创建 `.mcp.json` 文件，配置项目专属的 MCP 服务器：

```json
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

**MCP 服务器配置类型**：

| 类型 | 字段 | 说明 |
|------|------|------|
| `stdio` | command, args, env, cwd | 通过标准输入输出通信 |
| `http` | url, headers | 通过 HTTP 协议通信 |
| `ws` | url, headers | 通过 WebSocket 协议通信 |

---

### 权限配置

#### 权限模式

| 模式 | 值 | 说明 |
|------|-----|------|
| 默认模式 | `default` | 修改类工具需要用户确认 |
| 计划模式 | `plan` | 阻止所有修改类工具 |
| 全自动模式 | `full_auto` | 允许一切操作 |

#### 权限配置示例

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

### 钩子配置

钩子允许在特定事件发生时执行自定义操作。

#### 支持的钩子类型

| 钩子事件 | 说明 |
|----------|------|
| `PRE_TOOL_USE` | 工具执行前 |
| `POST_TOOL_USE` | 工具执行后 |
| `USER_PROMPT_SUBMIT` | 用户提交提示词后 |

#### 钩子配置示例

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
        "prompt": "检查用户输入是否包含敏感信息",
        "block_on_failure": true
      }
    ]
  }
}
```

#### 钩子类型详解

| 类型 | 必填字段 | 可选字段 | 说明 |
|------|----------|----------|------|
| `command` | command | timeout_seconds, matcher, block_on_failure | 执行 Shell 命令 |
| `prompt` | prompt | model, timeout_seconds, matcher, block_on_failure | 使用 LLM 验证 |
| `http` | url | headers, timeout_seconds, matcher, block_on_failure | 发送 HTTP 请求 |
| `agent` | prompt | model, timeout_seconds, matcher, block_on_failure | 使用 Agent 验证 |

---

### 环境变量

支持的环境变量：

| 变量名 | 说明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API 密钥 |
| `ANTHROPIC_MODEL` / `illusion_MODEL` | 默认模型 |
| `ANTHROPIC_BASE_URL` / `illusion_BASE_URL` | API 端点 |
| `illusion_MAX_TOKENS` | 最大 token 数 |
| `illusion_MAX_TURNS` | 最大对话轮数 |
| `illusion_API_FORMAT` | API 格式 |
| `illusion_PROVIDER` | 提供商 |
| `illusion_SANDBOX_ENABLED` | 是否启用沙箱 |
| `ILLUSION_CONFIG_DIR` | 配置目录路径 |
| `ILLUSION_DATA_DIR` | 数据目录路径 |
| `ILLUSION_LOGS_DIR` | 日志目录路径 |

---

### 记忆系统配置

```json
{
  "memory": {
    "enabled": true,
    "max_files": 5,
    "max_entrypoint_lines": 200
  }
}
```

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `enabled` | true | 是否启用记忆功能 |
| `max_files` | 5 | 最大记忆文件数 |
| `max_entrypoint_lines` | 200 | 入口文件最大行数 |

---

### 沙箱配置

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

## 🔌 扩展开发

### 钩子系统

支持多种钩子类型：

- `PRE_TOOL_USE` - 工具执行前
- `POST_TOOL_USE` - 工具执行后
- `USER_PROMPT_SUBMIT` - 用户提交提示词后

### 插件系统

通过 `plugin.json` 清单定义：

- 技能 (Skills)
- 命令 (Commands)
- 钩子 (Hooks)
- MCP 服务器

---

## 🧪 开发与测试

```bash
# 安装开发依赖
uv sync --dev

# 运行测试
pytest

```

---

## 📄 许可证

本项目采用 [MIT](LICENSE) 许可证开源。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

</div>
