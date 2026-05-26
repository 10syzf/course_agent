"""Skill Runtime 单测（Task 013）."""

from __future__ import annotations

import pytest

from course_agent.capabilities import CapabilityKind
from course_agent.skills.runtime import (
    LocalSkillProvider,
    SkillRegistry,
    get_skill_registry,
    skill,
)


def test_skill_registry_register_and_get():
    reg = SkillRegistry()

    @skill(
        name="demo_skill",
        description="d",
        parameters={"type": "object", "properties": {}, "required": []},
        registry=reg,
    )
    def _demo(ctx):
        return "ok"

    assert reg.get("demo_skill").name == "demo_skill"


def test_skill_registry_duplicate_rejected():
    reg = SkillRegistry()

    @skill(
        name="dup_skill",
        description="d",
        parameters={"type": "object", "properties": {}, "required": []},
        registry=reg,
    )
    def _demo(ctx):
        return "ok"

    with pytest.raises(ValueError):

        @skill(
            name="dup_skill",
            description="d2",
            parameters={"type": "object", "properties": {}, "required": []},
            registry=reg,
        )
        def _demo2(ctx):
            return "ok"


def test_local_skill_provider_lists_capabilities():
    reg = SkillRegistry()

    @skill(
        name="list_me",
        description="desc",
        parameters={"type": "object", "properties": {}, "required": []},
        registry=reg,
    )
    def _demo(ctx):
        return "ok"

    provider = LocalSkillProvider(registry=reg)
    rows = provider.list_capabilities()
    assert len(rows) == 1
    assert rows[0].kind == CapabilityKind.SKILL
    assert rows[0].name == "list_me"


@pytest.mark.asyncio
async def test_local_skill_provider_call_sync_skill():
    reg = SkillRegistry()

    @skill(
        name="sync_skill",
        description="desc",
        parameters={
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
        },
        registry=reg,
    )
    def _demo(ctx, x: int):
        return f"v={x}"

    provider = LocalSkillProvider(registry=reg)
    result = await provider.call("sync_skill", {"x": 3})
    assert result.ok is True
    assert result.output == "v=3"


@pytest.mark.asyncio
async def test_local_skill_provider_call_async_skill():
    reg = SkillRegistry()

    @skill(
        name="async_skill",
        description="desc",
        parameters={"type": "object", "properties": {}, "required": []},
        registry=reg,
    )
    async def _demo(ctx):
        return "async-ok"

    provider = LocalSkillProvider(registry=reg)
    result = await provider.call("async_skill", {})
    assert result.output == "async-ok"


@pytest.mark.asyncio
async def test_local_skill_provider_missing_skill_raises():
    provider = LocalSkillProvider(registry=SkillRegistry())
    with pytest.raises(KeyError):
        await provider.call("missing", {})


def test_global_skill_registry_has_builtin_skills():
    reg = get_skill_registry()
    names = reg.list_names()
    assert "study_plan_skill" in names
    assert "quiz_from_notes_skill" in names


def test_skill_to_capability_spec_contains_tags():
    reg = SkillRegistry()

    @skill(
        name="tagged_skill",
        description="desc",
        parameters={"type": "object", "properties": {}, "required": []},
        tags=["a", "b"],
        registry=reg,
    )
    def _demo(ctx):
        return "ok"

    spec = reg.get("tagged_skill").to_capability_spec()
    assert spec.tags == ["a", "b"]
