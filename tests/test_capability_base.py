"""Capability 基础抽象单测（Task 013）."""

from __future__ import annotations

from course_agent.capabilities import (
    BaseCapabilityProvider,
    CapabilityCallResult,
    CapabilityKind,
    CapabilitySpec,
)


class _DummyProvider:
    provider_name = "dummy"

    def list_capabilities(self) -> list[CapabilitySpec]:
        return [
            CapabilitySpec(
                name="dummy_cap",
                kind=CapabilityKind.SKILL,
                description="x",
            )
        ]

    async def call(self, name: str, arguments: dict[str, object]) -> CapabilityCallResult:
        return CapabilityCallResult(
            capability_name=name,
            kind=CapabilityKind.SKILL,
            ok=True,
            output=str(arguments),
        )


def test_capability_kind_values():
    assert CapabilityKind.INTERNAL_TOOL.value == "internal_tool"
    assert CapabilityKind.SKILL.value == "skill"
    assert CapabilityKind.MCP.value == "mcp"


def test_capability_spec_defaults():
    spec = CapabilitySpec(name="x", kind=CapabilityKind.SKILL)
    assert spec.description == ""
    assert spec.parameters == {}
    assert spec.enabled is True
    assert spec.tags == []
    assert spec.meta == {}


def test_capability_spec_serializable():
    spec = CapabilitySpec(
        name="study_plan_skill",
        kind=CapabilityKind.SKILL,
        source="skills",
        tags=["study"],
    )
    data = spec.model_dump()
    assert data["name"] == "study_plan_skill"
    assert data["kind"] == CapabilityKind.SKILL
    assert data["source"] == "skills"


def test_capability_call_result_defaults():
    rec = CapabilityCallResult(
        capability_name="a",
        kind=CapabilityKind.MCP,
    )
    assert rec.ok is True
    assert rec.output == ""
    assert rec.error is None
    assert rec.latency_ms == 0


def test_capability_provider_protocol_runtime_checkable():
    provider = _DummyProvider()
    assert isinstance(provider, BaseCapabilityProvider)


def test_capability_spec_can_hold_meta():
    spec = CapabilitySpec(
        name="mcp_demo_echo",
        kind=CapabilityKind.MCP,
        meta={"display_name": "demo/echo"},
    )
    assert spec.meta["display_name"] == "demo/echo"
