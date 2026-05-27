"""Task 017：项目说明文件读取测试."""

from __future__ import annotations

from course_agent.prompt.project_instructions import find_project_root, read_project_instructions


def test_find_project_root_uses_pyproject(tmp_path):
    root = tmp_path / "repo"
    child = root / "a" / "b"
    child.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    assert find_project_root(child) == root


def test_read_project_instructions_prefers_course_agent_md(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "COURSE_AGENT.md").write_text("course instructions", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude instructions", encoding="utf-8")
    path, content = read_project_instructions(tmp_path)
    assert path is not None
    assert path.name == "COURSE_AGENT.md"
    assert content == "course instructions"


def test_read_project_instructions_falls_back_to_claude_md(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude instructions", encoding="utf-8")
    path, content = read_project_instructions(tmp_path)
    assert path is not None
    assert path.name == "CLAUDE.md"
    assert content == "claude instructions"


def test_read_project_instructions_returns_empty_when_missing(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    path, content = read_project_instructions(tmp_path)
    assert path is None
    assert content == ""
