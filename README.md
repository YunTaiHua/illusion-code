# Illusion Code

Illusion Code is a terminal-first AI coding assistant with two UI modes:
- Textual UI (`src/illusion/ui/textual_app.py`)
- React/Ink terminal frontend (`frontend/terminal` + `src/illusion/ui/backend_host.py`)

It supports streaming assistant output, tool execution, task/todo tracking, permission prompts, and profile-driven model/provider settings.

## Features

- Interactive chat with streaming responses
- Tool execution with transcripted tool calls/results
- Busy/phase state handling (`idle`, `thinking`, `tool_executing`)
- Permission and question modals for interactive tools
- Task/todo tooling (`task_*`, `todo_write`)
- Cron-style scheduling tools (`cron_create`, `cron_list`, `cron_delete`)
- Configurable provider/model profiles

## Project Structure

- `src/illusion/` - core Python application
  - `ui/` - textual and React backend host
  - `tools/` - built-in tools
  - `commands/` - slash command registry
  - `engine/` - query/stream execution pipeline
  - `services/` - cron/session/task support services
- `frontend/terminal/` - React + Ink terminal frontend
- `tests/` - pytest test suite

## Requirements

- Python 3.12+
- Node.js (for React terminal frontend development)
- Optional on Windows: Git Bash if you want `bash` tool behavior

## Installation

Using `uv` (recommended):

```bash
uv sync
```

Or with pip:

```bash
pip install -e .
```

## Running

Entry point:

```bash
python -m illusion
```

Or from repository root:

```bash
python main.py
```

## Testing

Run full test suite:

```bash
pytest -q
```

Run UI-focused tests:

```bash
pytest -q tests/test_ui
```

## Notes

- Temporary artifacts should go under `temp/`.
- The React frontend receives protocol events prefixed with `OHJSON:` from `ReactBackendHost`.
