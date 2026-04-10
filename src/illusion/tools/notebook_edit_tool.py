"""
最小 Jupyter notebook 编辑工具
==============================

本模块提供编辑 Jupyter notebook 单元格的功能，无需使用 nbformat。

主要组件：
    - NotebookEditTool: 编辑 notebook 单元格的工具

使用示例：
    >>> from illusion.tools import NotebookEditTool
    >>> tool = NotebookEditTool()
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class NotebookEditToolInput(BaseModel):
    """Notebook 编辑参数。

    属性：
        notebook_path: Jupyter notebook 文件的绝对路径
        cell_id: 要编辑的单元格 ID
        new_source: 单元格的新源代码
        cell_type: 单元格类型（code 或 markdown）
        edit_mode: 编辑类型：replace、insert 或 delete
    """

    notebook_path: str = Field(description="The absolute path to the Jupyter notebook file")
    cell_id: str | None = Field(
        default=None,
        description="The ID of the cell to edit. Use edit_mode=insert to add a new cell at this index, edit_mode=delete to delete.",
    )
    new_source: str = Field(description="The new source for the cell")
    cell_type: Literal["code", "markdown"] | None = Field(
        default=None,
        description="The type of the cell (code or markdown). Required for insert mode. Defaults to the current cell type for replace.",
    )
    edit_mode: Literal["replace", "insert", "delete"] = Field(
        default="replace",
        description="The type of edit to make. replace: replace cell content, insert: add new cell at index, delete: remove the cell.",
    )


class NotebookEditTool(BaseTool):
    """编辑 notebook 单元格而不需要 nbformat。

    用于修改 Jupyter notebook (.ipynb 文件) 中的单元格内容。
    """

    name = "notebook_edit"
    description = """Completely replaces the contents of a specific cell in a Jupyter notebook (.ipynb file) with new source. Jupyter notebooks are interactive documents that combine code, text, and visualizations, commonly used for data analysis and scientific computing. The notebook_path parameter must be an absolute path, not a relative path. The cell_number is 0-indexed. Use edit_mode=insert to add a new cell at the index specified by cell_number. Use edit_mode=delete to delete the cell at the index specified by cell_number. Defaults to edit_mode=replace. When using edit_mode=insert, cell_type is required. When using edit_mode=replace, cell_type defaults to the current cell type."""
    input_model = NotebookEditToolInput

    async def execute(
        self,
        arguments: NotebookEditToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        # 解析文件路径
        path = _resolve_path(context.cwd, arguments.notebook_path)

        # 验证 .ipynb 扩展名
        if path.suffix.lower() != ".ipynb":
            return ToolResult(
                output=f"File must have .ipynb extension: {path}",
                is_error=True,
            )

        # 对现有文件进行读后编辑检查
        if path.exists():
            from illusion.tools.file_edit_tool import has_file_been_read
            if not has_file_been_read(str(path)):
                return ToolResult(
                    output=f"You must read the file at {path} using the Read tool before you can edit it.",
                    is_error=True,
                )

        # 加载 notebook
        notebook = _load_notebook(path)
        if notebook is None:
            return ToolResult(output=f"Notebook not found: {path}", is_error=True)

        # 获取单元格列表
        cells = notebook.setdefault("cells", [])

        # 从 cell_id 解析单元格索引
        cell_index = _resolve_cell_index(cells, arguments.cell_id)

        # 确定单元格类型
        effective_cell_type = arguments.cell_type
        if effective_cell_type is None:
            if arguments.edit_mode == "insert":
                return ToolResult(
                    output="cell_type is required for insert mode",
                    is_error=True,
                )
            # 对于 replace/delete，使用现有单元格类型
            if 0 <= cell_index < len(cells):
                effective_cell_type = cells[cell_index].get("cell_type", "code")
            else:
                effective_cell_type = "code"

        # 处理边界情况：replace 在末尾 → 转换为 insert
        if arguments.edit_mode == "replace" and cell_index >= len(cells):
            arguments = arguments.model_copy(update={"edit_mode": "insert"})
            cell_index = len(cells)

        # 执行编辑操作
        if arguments.edit_mode == "delete":
            if cell_index >= len(cells):
                return ToolResult(
                    output=f"Cell index {cell_index} out of range (notebook has {len(cells)} cells)",
                    is_error=True,
                )
            deleted = cells.pop(cell_index)
            _save_notebook(path, notebook)
            return ToolResult(
                output=f"Deleted cell {cell_index} from {path}"
            )

        if arguments.edit_mode == "insert":
            new_cell = _empty_cell(effective_cell_type)
            new_cell["id"] = _generate_cell_id()
            new_cell["source"] = arguments.new_source
            # 在指定索引处插入
            insert_at = min(cell_index, len(cells))
            cells.insert(insert_at, new_cell)
            _save_notebook(path, notebook)
            return ToolResult(
                output=f"Inserted cell at index {insert_at} in {path}"
            )

        # Replace 模式
        if cell_index >= len(cells):
            # 自动扩展空单元格
            while len(cells) <= cell_index:
                cells.append(_empty_cell(effective_cell_type))

        cell = cells[cell_index]
        cell["cell_type"] = effective_cell_type
        cell.setdefault("metadata", {})
        if effective_cell_type == "code":
            cell.setdefault("outputs", [])
            cell.setdefault("execution_count", None)
            # 替换时重置执行状态
            cell["execution_count"] = None
            cell["outputs"] = []

        cell["source"] = arguments.new_source

        _save_notebook(path, notebook)
        return ToolResult(output=f"Updated notebook cell {cell_index} in {path}")


def _resolve_path(base: Path, candidate: str) -> Path:
    """解析相对路径为绝对路径。"""
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_cell_index(cells: list[dict], cell_id: str | None) -> int:
    """将 cell_id 解析为数字索引。

    支持：
    - None → 默认为 0
    - 数字索引如 "3" → 3
    - "cell-N" 格式 → N
    - 实际单元格 ID 字符串 → 按 id 字段匹配
    """
    if cell_id is None:
        return 0

    # 尝试直接解析为数字索引
    try:
        return int(cell_id)
    except ValueError:
        pass

    # 尝试 "cell-N" 格式
    if cell_id.startswith("cell-"):
        try:
            return int(cell_id[5:])
        except ValueError:
            pass

    # 尝试匹配实际单元格 ID
    for i, cell in enumerate(cells):
        if cell.get("id") == cell_id:
            return i

    # 如果没有匹配，默认返回 0
    return 0


def _load_notebook(path: Path) -> dict | None:
    """从磁盘加载 notebook。如果文件不存在返回 None。"""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_notebook(path: Path, notebook: dict) -> None:
    """将 notebook 保存到磁盘。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")


def _generate_cell_id() -> str:
    """为 nbformat >= 4.5 生成唯一的单元格 ID。"""
    return secrets.token_hex(8)


def _empty_cell(cell_type: str) -> dict:
    """创建空单元格。"""
    if cell_type == "markdown":
        return {"cell_type": "markdown", "metadata": {}, "source": ""}
    return {
        "cell_type": "code",
        "metadata": {},
        "source": "",
        "outputs": [],
        "execution_count": None,
    }


def _normalize_source(source: str | list[str]) -> str:
    """规范化源代码（支持字符串或字符串列表）。"""
    if isinstance(source, list):
        return "".join(source)
    return str(source)
