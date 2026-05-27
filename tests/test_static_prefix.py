"""Task 017：静态前缀测试."""

from __future__ import annotations

from course_agent.prompt.static_prefix import build_static_prefix


def test_build_static_prefix_includes_global_sections():
    text, sections = build_static_prefix(role="react", role_prompt="")
    assert "role_definition" in text
    assert "safety_guardrails" in text
    assert len(sections) >= 2


def test_build_static_prefix_includes_role_specific_prefix():
    text, _ = build_static_prefix(role="planner", role_prompt="")
    assert "Planner" in text


def test_build_static_prefix_includes_role_instructions():
    text, sections = build_static_prefix(role="solver", role_prompt="你必须输出中文。")
    assert "你必须输出中文" in text
    assert sections[-1].name == "role_instructions"


def test_build_static_prefix_role_fallbacks_to_react():
    text, _ = build_static_prefix(role="unknown", role_prompt="")
    assert "通用执行代理" in text


def test_build_static_prefix_sections_marked_static():
    _, sections = build_static_prefix(role="critic", role_prompt="")
    assert all(section.is_static for section in sections)
