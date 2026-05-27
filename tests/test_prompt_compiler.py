"""Task 017：prompt compiler 测试."""

from __future__ import annotations

from course_agent.prompt.compiler import (
    compile_prompt,
    load_prompt_artifact,
    prompt_to_markdown,
    save_prompt_artifact,
)


def test_compile_prompt_returns_envelope_with_sections(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "COURSE_AGENT.md").write_text("demo instructions", encoding="utf-8")
    envelope = compile_prompt(
        role="solver",
        role_prompt="你是 Solver。",
        user_input="帮我算 1+1",
        project_root=tmp_path,
    )
    assert envelope.role == "solver"
    assert envelope.sections


def test_compile_prompt_static_and_dynamic_are_separated():
    envelope = compile_prompt(
        role="react",
        role_prompt="你是助手。",
        user_input="你好",
    )
    assert envelope.static_prefix
    assert envelope.dynamic_tail
    assert envelope.full_prompt.startswith(envelope.static_prefix)


def test_compile_prompt_hash_changes_when_dynamic_changes():
    a = compile_prompt(role="react", role_prompt="你是助手。", user_input="你好")
    b = compile_prompt(role="react", role_prompt="你是助手。", user_input="再见")
    assert a.static_hash == b.static_hash
    assert a.dynamic_hash != b.dynamic_hash


def test_save_and_load_prompt_artifact(tmp_path):
    envelope = compile_prompt(role="react", role_prompt="你是助手。", user_input="你好")
    path = save_prompt_artifact(envelope, prompt_dir=tmp_path)
    loaded = load_prompt_artifact(path)
    assert loaded.full_prompt == envelope.full_prompt


def test_prompt_to_markdown_contains_sections():
    envelope = compile_prompt(role="react", role_prompt="你是助手。", user_input="你好")
    md = prompt_to_markdown(envelope)
    assert "# Prompt Inspect" in md
    assert "## Static Prefix" in md
    assert "## Dynamic Tail" in md


def test_compile_prompt_keeps_metadata():
    envelope = compile_prompt(
        role="react",
        role_prompt="你是助手。",
        user_input="你好",
        metadata={"scene": "chat"},
    )
    assert envelope.metadata["scene"] == "chat"
