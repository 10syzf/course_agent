"""Task 017：项目级说明文件读取."""

from __future__ import annotations

from pathlib import Path


def find_project_root(start: str | Path | None = None) -> Path:
    """向上寻找项目根目录."""
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for path in [current, *current.parents]:
        if (path / "pyproject.toml").exists() or (path / ".git").exists():
            return path
    return current


def read_project_instructions(
    project_root: str | Path | None = None,
) -> tuple[Path | None, str]:
    """读取 `COURSE_AGENT.md`，兼容 `CLAUDE.md`."""
    root = find_project_root(project_root)
    for name in ("COURSE_AGENT.md", "CLAUDE.md"):
        path = root / name
        if path.exists():
            return path, path.read_text(encoding="utf-8").strip()
    return None, ""


__all__ = ["find_project_root", "read_project_instructions"]
