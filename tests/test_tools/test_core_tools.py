"""Tests for built-in tools."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

import pytest

from illusion.tools.bash_tool import BashTool, BashToolInput
from illusion.tools.base import ToolExecutionContext
from illusion.tools.brief_tool import BriefTool, BriefToolInput
from illusion.tools.cron_create_tool import CronCreateTool, CronCreateToolInput
from illusion.tools.cron_delete_tool import CronDeleteTool, CronDeleteToolInput
from illusion.tools.cron_list_tool import CronListTool, CronListToolInput
from illusion.tools.config_tool import ConfigTool, ConfigToolInput
from illusion.tools.enter_worktree_tool import EnterWorktreeTool, EnterWorktreeToolInput
from illusion.tools.exit_worktree_tool import ExitWorktreeTool, ExitWorktreeToolInput
from illusion.tools.file_edit_tool import FileEditTool, FileEditToolInput
from illusion.tools.file_read_tool import FileReadTool, FileReadToolInput
from illusion.tools.file_write_tool import FileWriteTool, FileWriteToolInput
from illusion.tools.glob_tool import GlobTool, GlobToolInput
from illusion.tools.grep_tool import GrepTool, GrepToolInput
from illusion.tools.lsp_tool import LspTool, LspToolInput
from illusion.tools.notebook_edit_tool import NotebookEditTool, NotebookEditToolInput
from illusion.tools.remote_trigger_tool import RemoteTriggerTool, RemoteTriggerToolInput
from illusion.tools.skill_tool import SkillTool, SkillToolInput
from illusion.tools.todo_write_tool import TodoWriteTool, TodoWriteToolInput
from illusion.tools.tool_search_tool import ToolSearchTool, ToolSearchToolInput
from illusion.tools import create_default_tool_registry
from illusion.platforms import get_platform


@pytest.mark.asyncio
async def test_file_write_read_and_edit(tmp_path: Path):
    context = ToolExecutionContext(cwd=tmp_path)

    write_result = await FileWriteTool().execute(
        FileWriteToolInput(path="notes.txt", content="one\ntwo\nthree\n"),
        context,
    )
    assert write_result.is_error is False
    assert (tmp_path / "notes.txt").exists()

    read_result = await FileReadTool().execute(
        FileReadToolInput(path="notes.txt", offset=1, limit=2),
        context,
    )
    assert "2\ttwo" in read_result.output
    assert "3\tthree" in read_result.output

    edit_result = await FileEditTool().execute(
        FileEditToolInput(path="notes.txt", old_str="two", new_str="TWO"),
        context,
    )
    assert edit_result.is_error is False
    assert "TWO" in (tmp_path / "notes.txt").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_glob_and_grep(tmp_path: Path):
    context = ToolExecutionContext(cwd=tmp_path)
    (tmp_path / "a.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def beta():\n    return 2\n", encoding="utf-8")

    glob_result = await GlobTool().execute(GlobToolInput(pattern="*.py"), context)
    assert glob_result.output.splitlines() == ["a.py", "b.py"]

    grep_result = await GrepTool().execute(
        GrepToolInput(pattern=r"def\s+beta", file_glob="*.py"),
        context,
    )
    assert "b.py:1:def beta():" in grep_result.output

    file_root_result = await GrepTool().execute(
        GrepToolInput(pattern=r"def\s+alpha", root="a.py"),
        context,
    )
    assert "a.py:1:def alpha():" in file_root_result.output


@pytest.mark.asyncio
async def test_bash_tool_runs_command(tmp_path: Path):
    if get_platform() == "windows":
        bash_path = shutil.which("bash")
        normalized = (bash_path or "").replace("/", "\\").lower()
        if (not bash_path) or normalized.endswith("\\windows\\system32\\bash.exe"):
            pytest.skip("No usable bash available on this Windows environment")

    result = await BashTool().execute(
        BashToolInput(command="printf 'hello'"),
        ToolExecutionContext(cwd=tmp_path),
    )
    assert result.is_error is False
    assert result.output == "hello"


@pytest.mark.asyncio
async def test_bash_tool_returns_clear_error_when_bash_missing_on_windows(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("illusion.tools.bash_tool.get_platform", lambda: "windows")
    monkeypatch.setattr("illusion.tools.bash_tool.shutil.which", lambda _name: None)

    result = await BashTool().execute(
        BashToolInput(command="rm -rf test"),
        ToolExecutionContext(cwd=tmp_path),
    )

    assert result.is_error is True
    assert "Bash is not available on this Windows machine" in result.output


@pytest.mark.asyncio
async def test_tool_search_and_brief_tools(tmp_path: Path):
    registry = create_default_tool_registry()
    context = ToolExecutionContext(cwd=tmp_path, metadata={"tool_registry": registry})

    search_result = await ToolSearchTool().execute(
        ToolSearchToolInput(query="file"),
        context,
    )
    assert "read_file" in search_result.output

    brief_result = await BriefTool().execute(
        BriefToolInput(text="abcdefghijklmnopqrstuvwxyz", max_chars=20),
        ToolExecutionContext(cwd=tmp_path),
    )
    assert brief_result.output == "abcdefghijklmnopqrst..."


@pytest.mark.asyncio
async def test_skill_todo_and_config_tools(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    skills_dir = tmp_path / "config" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "pytest.md").write_text("# Pytest\nHelpful pytest notes.\n", encoding="utf-8")

    skill_result = await SkillTool().execute(
        SkillToolInput(name="Pytest"),
        ToolExecutionContext(cwd=tmp_path),
    )
    assert "Helpful pytest notes." in skill_result.output

    todo_result = await TodoWriteTool().execute(
        TodoWriteToolInput(item="wire commands"),
        ToolExecutionContext(cwd=tmp_path),
    )
    assert todo_result.is_error is False
    assert "wire commands" in (tmp_path / "TODO.md").read_text(encoding="utf-8")

    config_result = await ConfigTool().execute(
        ConfigToolInput(action="set", key="theme", value="solarized"),
        ToolExecutionContext(cwd=tmp_path),
    )
    assert config_result.output == "Updated theme"


@pytest.mark.asyncio
async def test_notebook_edit_tool(tmp_path: Path):
    result = await NotebookEditTool().execute(
        NotebookEditToolInput(path="demo.ipynb", cell_index=0, new_source="print('nb ok')\n"),
        ToolExecutionContext(cwd=tmp_path),
    )
    assert result.is_error is False
    assert "demo.ipynb" in result.output
    assert "nb ok" in (tmp_path / "demo.ipynb").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_lsp_tool(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "utils.py").write_text(
        'def greet(name):\n    """Return a greeting."""\n    return f"hi {name}"\n',
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "app.py").write_text(
        "from pkg.utils import greet\n\nprint(greet('world'))\n",
        encoding="utf-8",
    )
    context = ToolExecutionContext(cwd=tmp_path)

    document_symbols = await LspTool().execute(
        LspToolInput(operation="document_symbol", file_path="pkg/utils.py"),
        context,
    )
    assert "function greet" in document_symbols.output

    definition = await LspTool().execute(
        LspToolInput(operation="go_to_definition", file_path="pkg/app.py", symbol="greet"),
        context,
    )
    assert "pkg/utils.py:1:1" in definition.output

    references = await LspTool().execute(
        LspToolInput(operation="find_references", file_path="pkg/app.py", symbol="greet"),
        context,
    )
    assert "pkg/app.py:1:from pkg.utils import greet" in references.output

    hover = await LspTool().execute(
        LspToolInput(operation="hover", file_path="pkg/app.py", symbol="greet"),
        context,
    )
    assert "Return a greeting." in hover.output


@pytest.mark.asyncio
async def test_worktree_tools(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "illusion@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "IllusionCode Tests"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    (tmp_path / "demo.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    enter_result = await EnterWorktreeTool().execute(
        EnterWorktreeToolInput(branch="feature/demo"),
        ToolExecutionContext(cwd=tmp_path),
    )
    assert enter_result.is_error is False
    worktree_path = Path(enter_result.output.split("Path: ", 1)[1].strip())
    assert worktree_path.exists()

    exit_result = await ExitWorktreeTool().execute(
        ExitWorktreeToolInput(path=str(worktree_path)),
        ToolExecutionContext(cwd=tmp_path),
    )
    assert exit_result.is_error is False
    assert not worktree_path.exists()


@pytest.mark.asyncio
async def test_cron_and_remote_trigger_tools(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))
    context = ToolExecutionContext(cwd=tmp_path)

    cron_command = "printf 'CRON_OK'"
    if get_platform() == "windows":
        cron_command = "Write-Output CRON_OK"

    create_result = await CronCreateTool().execute(
        CronCreateToolInput(name="nightly", schedule="0 0 * * *", command=cron_command),
        context,
    )
    assert create_result.is_error is False

    list_result = await CronListTool().execute(CronListToolInput(), context)
    assert "nightly" in list_result.output

    trigger_result = await RemoteTriggerTool().execute(
        RemoteTriggerToolInput(name="nightly"),
        context,
    )
    assert trigger_result.is_error is False
    assert "CRON_OK" in trigger_result.output

    delete_result = await CronDeleteTool().execute(
        CronDeleteToolInput(name="nightly"),
        context,
    )
    assert delete_result.is_error is False


def test_default_registry_matches_claude_tool_shape():
    registry = create_default_tool_registry()
    names = {tool.name for tool in registry.list_tools()}

    assert "powershell" in names
    assert "repl" in names
    assert "structured_output" in names

    # Claude source has create/list/delete cron operations in this tool family.
    assert "cron_create" in names
    assert "cron_list" in names
    assert "cron_delete" in names

    # Keep cron_toggle available as a module, but out of the default list.
    assert "cron_toggle" not in names


@pytest.mark.asyncio
async def test_bash_tool_empty_success_has_contextual_message(tmp_path: Path):
    """成功命令无输出时返回上下文消息，而非 '(no output)'。"""
    if get_platform() == "windows":
        bash_path = shutil.which("bash")
        normalized = (bash_path or "").replace("/", "\\").lower()
        if (not bash_path) or normalized.endswith("\\windows\\system32\\bash.exe"):
            pytest.skip("No usable bash available on this Windows environment")

    result = await BashTool().execute(
        BashToolInput(command="true"),
        ToolExecutionContext(cwd=tmp_path),
    )
    assert result.is_error is False
    assert result.output != "(no output)"
    assert "successfully" in result.output
