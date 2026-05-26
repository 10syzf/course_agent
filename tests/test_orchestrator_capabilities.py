"""Solver / Orchestrator 对 capability 的集成单测（Task 013）."""

from __future__ import annotations

from typing import Any

import pytest

from course_agent.agent import Orchestrator, SolverAgent
from course_agent.capabilities.adapters import build_default_capability_registry
from course_agent.capabilities.router import CapabilityRouter
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse, ToolCall
from course_agent.mcp.config import MCPConfig, MCPServerConfig
from course_agent.tools.registry import ToolRegistry


class _SkillLLM(BaseLLM):
    def __init__(self, tool_name: str) -> None:
        super().__init__(model="skill-llm")
        self.tool_name = tool_name

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        last_tool = next((m for m in reversed(messages) if m.role == "tool"), None)
        if last_tool is not None:
            return LLMResponse(content=f"最终结果：{last_tool.content}", finish_reason="stop")
        return LLMResponse(
            content="我需要调用 capability",
            tool_calls=[ToolCall(id="t1", name=self.tool_name, arguments={"topic": "线代", "days": 2})],
            finish_reason="tool_calls",
        )


class _MCPToolLLM(BaseLLM):
    def __init__(self, tool_name: str) -> None:
        super().__init__(model="mcp-llm")
        self.tool_name = tool_name

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        last_tool = next((m for m in reversed(messages) if m.role == "tool"), None)
        if last_tool is not None:
            return LLMResponse(content=f"最终结果：{last_tool.content}", finish_reason="stop")
        return LLMResponse(
            content="我需要调用 mcp",
            tool_calls=[ToolCall(id="t1", name=self.tool_name, arguments={"text": "alpha beta"})],
            finish_reason="tool_calls",
        )


@pytest.mark.asyncio
async def test_solver_can_call_skill_via_capability_tool_view():
    cap_reg = build_default_capability_registry(tool_registry=ToolRegistry(), mcp_cfg=MCPConfig(enabled=False))
    router = CapabilityRouter(cap_reg)
    solver = SolverAgent(
        llm=_SkillLLM("study_plan_skill"),
        registry=ToolRegistry(),
        capability_registry=cap_reg,
        capability_router=router,
        enable_capabilities=True,
    )
    result = await solver.solve({"id": 1, "title": "T", "expected_output": "O"})
    assert "最终结果" in result.answer
    assert "Day 1" in result.answer


@pytest.mark.asyncio
async def test_solver_can_call_mcp_via_capability_tool_view():
    mcp_cfg = MCPConfig(
        enabled=True,
        servers=[MCPServerConfig(name="demo", transport="mock")],
    )
    cap_reg = build_default_capability_registry(tool_registry=ToolRegistry(), mcp_cfg=mcp_cfg)
    router = CapabilityRouter(cap_reg)
    solver = SolverAgent(
        llm=_MCPToolLLM("mcp_demo_echo"),
        registry=ToolRegistry(),
        capability_registry=cap_reg,
        capability_router=router,
        mcp_cfg=mcp_cfg,
        enable_capabilities=True,
    )
    result = await solver.solve({"id": 1, "title": "T", "expected_output": "O"})
    assert "alpha beta" in result.answer


@pytest.mark.asyncio
async def test_planner_can_receive_capability_summary_hint():
    class _PlannerLLM(BaseLLM):
        def __init__(self) -> None:
            super().__init__(model="planner")
            self.seen = ""

        def chat(self, messages, tools=None, **kwargs):
            self.seen = "\n".join((m.content or "") for m in messages)
            return LLMResponse(
                content='{"sub_tasks":[{"id":1,"title":"先做规划","expected_output":"给出计划"}]}',
                finish_reason="stop",
            )

    from course_agent.agent.planner import PlannerAgent

    llm = _PlannerLLM()
    cap_reg = build_default_capability_registry(tool_registry=ToolRegistry(), mcp_cfg=MCPConfig(enabled=False))
    planner = PlannerAgent(
        llm=llm,
        registry=ToolRegistry(),
        capability_router=CapabilityRouter(cap_reg),
    )
    result = await planner.plan("做一个复习计划")
    assert len(result) == 1
    assert "study_plan_skill" in llm.seen


@pytest.mark.asyncio
async def test_orchestrator_enable_capabilities_still_constructs():
    mcp_cfg = MCPConfig(enabled=False)
    orch = Orchestrator(
        llm=_SkillLLM("study_plan_skill"),
        registry=ToolRegistry(),
        mcp_cfg=mcp_cfg,
        enable_capabilities=True,
        max_sub_tasks=1,
        max_refine_per_task=0,
        max_total_llm_calls=8,
    )
    assert orch.solver.allowed_tools


@pytest.mark.asyncio
async def test_orchestrator_with_capabilities_path_runs_single_subtask():
    class _ScriptLLM(BaseLLM):
        def __init__(self):
            super().__init__(model="script")
            self.n = 0

        def chat(self, messages, tools=None, **kwargs):
            self.n += 1
            last_tool = next((m for m in reversed(messages) if m.role == "tool"), None)
            if self.n == 1:
                return LLMResponse(
                    content='{"sub_tasks":[{"id":1,"title":"生成计划","expected_output":"输出内容"}]}',
                    finish_reason="stop",
                )
            if last_tool is None:
                return LLMResponse(
                    content="use skill",
                    tool_calls=[ToolCall(id="1", name="study_plan_skill", arguments={"topic": "概率论", "days": 1})],
                    finish_reason="tool_calls",
                )
            if self.n == 3:
                return LLMResponse(content=f"答案：{last_tool.content}", finish_reason="stop")
            return LLMResponse(content='{"score":4,"pass":true,"feedback":"ok"}', finish_reason="stop")

    orch = Orchestrator(
        llm=_ScriptLLM(),
        registry=ToolRegistry(),
        mcp_cfg=MCPConfig(enabled=False),
        enable_capabilities=True,
        max_sub_tasks=1,
        max_refine_per_task=0,
        max_total_llm_calls=8,
    )
    result = await orch.arun("帮我生成一个一天复习计划")
    assert "概率论" in result.final_answer
