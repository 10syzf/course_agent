"""Capability Router 单测（Task 013）."""

from __future__ import annotations

from course_agent.capabilities import (
    CapabilityKind,
    CapabilityRegistry,
    CapabilityRouter,
    CapabilitySpec,
)


class _Provider:
    provider_name = "p"

    def list_capabilities(self):
        return [
            CapabilitySpec(name="kb_search", kind=CapabilityKind.INTERNAL_TOOL, description="kb"),
            CapabilitySpec(name="study_plan_skill", kind=CapabilityKind.SKILL, description="study"),
            CapabilitySpec(name="mcp_demo_echo", kind=CapabilityKind.MCP, description="echo"),
        ]

    async def call(self, name, arguments):
        raise NotImplementedError


def _router() -> CapabilityRouter:
    reg = CapabilityRegistry()
    reg.register_provider(_Provider())
    return CapabilityRouter(reg)


def test_router_planner_only_exposes_internal_tools():
    rows = _router().select_for_agent("Planner")
    assert [r.name for r in rows] == ["kb_search"]


def test_router_solver_can_see_all_enabled_capabilities():
    rows = _router().select_for_agent("Solver")
    assert {r.name for r in rows} == {"kb_search", "study_plan_skill", "mcp_demo_echo"}


def test_router_critic_only_exposes_internal_tools():
    rows = _router().select_for_agent("Critic")
    assert [r.name for r in rows] == ["kb_search"]


def test_router_allowed_names_filters_subset():
    rows = _router().select_for_agent("Solver", allowed_names=["study_plan_skill"])
    assert [r.name for r in rows] == ["study_plan_skill"]


def test_router_summarize_for_planner_only_returns_skill_and_mcp():
    rows = _router().summarize_for_planner()
    names = {r["name"] for r in rows}
    assert names == {"study_plan_skill", "mcp_demo_echo"}


def test_router_summarize_for_planner_has_kind_and_description():
    row = _router().summarize_for_planner(max_items=1)[0]
    assert "kind" in row
    assert "description" in row
