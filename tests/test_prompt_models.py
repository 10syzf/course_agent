"""Task 017：prompt 模型测试."""

from __future__ import annotations

from course_agent.prompt.models import PromptEnvelope, PromptSection


def test_prompt_section_char_count():
    section = PromptSection(name="demo", content="hello", is_static=True)
    assert section.char_count == 5


def test_prompt_envelope_create_builds_full_prompt():
    envelope = PromptEnvelope.create(
        role="react",
        static_prefix="static",
        dynamic_tail="dynamic",
        sections=[],
    )
    assert envelope.full_prompt == "static\n\ndynamic"


def test_prompt_envelope_hashes_are_stable_for_same_input():
    a = PromptEnvelope.create(
        role="react",
        static_prefix="static",
        dynamic_tail="dynamic",
        sections=[],
    )
    b = PromptEnvelope.create(
        role="react",
        static_prefix="static",
        dynamic_tail="dynamic",
        sections=[],
    )
    assert a.static_hash == b.static_hash
    assert a.dynamic_hash == b.dynamic_hash


def test_prompt_envelope_keeps_metadata():
    envelope = PromptEnvelope.create(
        role="solver",
        static_prefix="static",
        dynamic_tail="dynamic",
        sections=[],
        metadata={"x": 1},
    )
    assert envelope.metadata["x"] == 1
