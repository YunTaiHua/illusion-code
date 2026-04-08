"""Minimal Jupyter notebook editing tool."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class NotebookEditToolInput(BaseModel):
    """Arguments for notebook editing."""

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
    """Edit notebook cells without requiring nbformat."""

    name = "notebook_edit"
    description = """Completely replaces the contents of a specific cell in a Jupyter notebook (.ipynb file) with new source. Jupyter notebooks are interactive documents that combine code, text, and visualizations, commonly used for data analysis and scientific computing. The notebook_path parameter must be an absolute path, not a relative path. The cell_number is 0-indexed. Use edit_mode=insert to add a new cell at the index specified by cell_number. Use edit_mode=delete to delete the cell at the index specified by cell_number. Defaults to edit_mode=replace. When using edit_mode=insert, cell_type is required. When using edit_mode=replace, cell_type defaults to the current cell type."""
    input_model = NotebookEditToolInput

    async def execute(
        self,
        arguments: NotebookEditToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        path = _resolve_path(context.cwd, arguments.notebook_path)

        # Validate .ipynb extension
        if path.suffix.lower() != ".ipynb":
            return ToolResult(
                output=f"File must have .ipynb extension: {path}",
                is_error=True,
            )

        # Read-before-edit check for existing files
        if path.exists():
            from illusion.tools.file_edit_tool import has_file_been_read
            if not has_file_been_read(str(path)):
                return ToolResult(
                    output=f"You must read the file at {path} using the Read tool before you can edit it.",
                    is_error=True,
                )

        notebook = _load_notebook(path)
        if notebook is None:
            return ToolResult(output=f"Notebook not found: {path}", is_error=True)

        cells = notebook.setdefault("cells", [])

        # Resolve cell index from cell_id
        cell_index = _resolve_cell_index(cells, arguments.cell_id)

        # Determine cell type
        effective_cell_type = arguments.cell_type
        if effective_cell_type is None:
            if arguments.edit_mode == "insert":
                return ToolResult(
                    output="cell_type is required for insert mode",
                    is_error=True,
                )
            # For replace/delete, use existing cell type
            if 0 <= cell_index < len(cells):
                effective_cell_type = cells[cell_index].get("cell_type", "code")
            else:
                effective_cell_type = "code"

        # Handle edge case: replace at end → convert to insert
        if arguments.edit_mode == "replace" and cell_index >= len(cells):
            arguments = arguments.model_copy(update={"edit_mode": "insert"})
            cell_index = len(cells)

        # Execute the edit operation
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
            # Insert at the specified index
            insert_at = min(cell_index, len(cells))
            cells.insert(insert_at, new_cell)
            _save_notebook(path, notebook)
            return ToolResult(
                output=f"Inserted cell at index {insert_at} in {path}"
            )

        # Replace mode
        if cell_index >= len(cells):
            # Auto-extend with empty cells
            while len(cells) <= cell_index:
                cells.append(_empty_cell(effective_cell_type))

        cell = cells[cell_index]
        cell["cell_type"] = effective_cell_type
        cell.setdefault("metadata", {})
        if effective_cell_type == "code":
            cell.setdefault("outputs", [])
            cell.setdefault("execution_count", None)
            # Reset execution state on replace
            cell["execution_count"] = None
            cell["outputs"] = []

        cell["source"] = arguments.new_source

        _save_notebook(path, notebook)
        return ToolResult(output=f"Updated notebook cell {cell_index} in {path}")


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _resolve_cell_index(cells: list[dict], cell_id: str | None) -> int:
    """Resolve a cell_id to a numeric index.

    Supports:
    - None → defaults to 0
    - Numeric index like "3" → 3
    - "cell-N" format → N
    - Actual cell ID string → match by id field
    """
    if cell_id is None:
        return 0

    # Try parsing as numeric index directly
    try:
        return int(cell_id)
    except ValueError:
        pass

    # Try "cell-N" format
    if cell_id.startswith("cell-"):
        try:
            return int(cell_id[5:])
        except ValueError:
            pass

    # Try matching actual cell IDs
    for i, cell in enumerate(cells):
        if cell.get("id") == cell_id:
            return i

    # Default to 0 if nothing matched
    return 0


def _load_notebook(path: Path) -> dict | None:
    """Load a notebook from disk. Returns None if file doesn't exist."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_notebook(path: Path, notebook: dict) -> None:
    """Save a notebook to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")


def _generate_cell_id() -> str:
    """Generate a unique cell ID for nbformat >= 4.5."""
    return secrets.token_hex(8)


def _empty_cell(cell_type: str) -> dict:
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
    if isinstance(source, list):
        return "".join(source)
    return str(source)
