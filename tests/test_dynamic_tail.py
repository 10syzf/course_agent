"""Task 017：动态尾部测试."""

from __future__ import annotations

from course_agent.prompt.dynamic_tail import build_dynamic_tail


def test_build_dynamic_tail_contains_env_section():
    text, sections = build_dynamic_tail(user_input="你好")
    assert "工作目录:" in text
    assert sections[0].name == "env_section"


def test_build_dynamic_tail_loads_project_instructions(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "COURSE_AGENT.md").write_text("project instructions", encoding="utf-8")
    text, sections = build_dynamic_tail(user_input="你好", project_root=tmp_path)
    assert "project instructions" in text
    assert any(s.name == "project_instruction_section" for s in sections)


def test_build_dynamic_tail_renders_memory_notes():
    text, _ = build_dynamic_tail(user_input="你好", memory_notes={"user": "高级工程师"})
    assert "高级工程师" in text


def test_build_dynamic_tail_renders_mcp_notes():
    text, _ = build_dynamic_tail(user_input="你好", mcp_notes="- chrome: enabled")
    assert "chrome: enabled" in text


def test_build_dynamic_tail_renders_session_notes():
    text, _ = build_dynamic_tail(
        user_input="你好",
        session_notes={"session_id": "abc", "status": "waiting_human_input"},
    )
    assert "waiting_human_input" in text


def test_build_dynamic_tail_renders_task_section():
    text, sections = build_dynamic_tail(
        user_input="帮我算一下 1+1",
        history_count=3,
        task_notes={"scene": "math"},
    )
    assert "用户输入: 帮我算一下 1+1" in text
    assert "历史消息数: 3" in text
    assert any(s.name == "task_context_section" for s in sections)
