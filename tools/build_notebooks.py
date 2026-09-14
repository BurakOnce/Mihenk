"""turn readable .py notebook sources into .ipynb files for fabric"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = REPO_ROOT / "fabric" / "notebooks"

CELL_MARKER = re.compile(r"^#\s*%%(?P<rest>.*)$")
MAGIC_COMMENT = re.compile(r"^(?P<indent>\s*)#\s?(?P<magic>%{1,2}[a-zA-Z].*)$")

def _parse_cells(source: str) -> list[tuple[str, list[str], list[str]]]:
    """split a percent-format file into (cell_type, tags, lines)"""
    cells: list[tuple[str, list[str], list[str]]] = []
    cell_type, tags, buffer = "code", [], []

    def flush() -> None:
        if buffer and any(line.strip() for line in buffer):
            cells.append((cell_type, tags, list(buffer)))
        buffer.clear()

    for line in source.splitlines():
        match = CELL_MARKER.match(line)
        if not match:
            buffer.append(line)
            continue

        flush()
        rest = match.group("rest").strip()
        cell_type = "markdown" if rest.startswith("[markdown]") else "code"
        tag_match = re.search(r'tags=\[(.*?)\]', rest)
        tags = (
            [t.strip().strip('"\'') for t in tag_match.group(1).split(",") if t.strip()]
            if tag_match else []
        )

    flush()
    return cells

def _strip_markdown_comments(lines: list[str]) -> list[str]:
    """markdown cells are written as comments; take the comment marker off"""
    out = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("# "):
            out.append(line.replace("# ", "", 1))
        elif stripped == "#":
            out.append("")
        else:
            out.append(line)
    return out

def _unescape_magics(lines: list[str]) -> list[str]:
    """a magic like %run isn't valid python, so the .py source comments it
    out (# %run x) to stay lint-clean; undo that so fabric actually runs it"""
    out = []
    for line in lines:
        match = MAGIC_COMMENT.match(line)
        out.append(f"{match['indent']}{match['magic']}" if match else line)
    return out

def _to_source(lines: list[str]) -> list[str]:
    """nbformat stores source as a list of lines, each keeping its newline"""
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return [line + "\n" for line in lines[:-1]] + (lines[-1:] if lines else [])

def build(py_path: Path) -> Path:
    cells_raw = _parse_cells(py_path.read_text(encoding="utf-8"))

    cells = []
    for cell_type, tags, lines in cells_raw:
        if cell_type == "markdown":
            lines = _strip_markdown_comments(lines)
            cells.append(
                {
                    "cell_type": "markdown",
                    "metadata": {"tags": tags} if tags else {},
                    "source": _to_source(lines),
                }
            )
        else:
            lines = _unescape_magics(lines)
            cells.append(
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {"tags": tags} if tags else {},
                    "outputs": [],
                    "source": _to_source(lines),
                }
            )

    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Synapse PySpark",
                "language": "Python",
                "name": "synapse_pyspark",
            },
            "language_info": {"name": "python"},

            "microsoft": {"language": "python"},
        },
        "cells": cells,
    }

    out_path = py_path.with_suffix(".ipynb")
    out_path.write_text(
        json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out_path

def main() -> int:
    sources = sorted(NOTEBOOK_DIR.glob("*.py"))
    if not sources:
        print(f"no .py notebook sources found in {NOTEBOOK_DIR}")
        return 1
    for source in sources:
        out = build(source)
        cells = len(json.loads(out.read_text(encoding="utf-8"))["cells"])
        print(f"{source.name:<34} -> {out.name:<36} {cells:>3} cells")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
