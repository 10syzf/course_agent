"""Task 017：prompt integration 测试."""

from __future__ import annotations

import pytest

from course_agent.agent.planner import PlannerAgent
from course_agent.agent.solver import SolverAgent
from course_agent.core import AgentLoop
from course_agent.llm import MockLLM
from course_agent.runtime.react_graph_runtime import ReactGraphRuntime
from course_agent.tools import get_registry


def test_agent_loop_builds_and_saves_prompt_artifact(tmp_path):
    loop = AgentLoop(llm=MockLLM(), prompt_dir=str(tmp_path))
    result = loop.run("你好")
    prompt = loop.get_last_prompt()
    assert prompt is not None
    assert prompt.role == "react"
    assert result.prompt_artifact_path


@pytest.mark.asyncio
async def test_planner_agent_uses_planner_prompt_role():
    planner = PlannerAgent(llm=MockLLM())
    await planner.arun("帮我规划一个任务")
    prompt = planner.loop.get_last_prompt()
    assert prompt is not None
    assert prompt.role == "planner"


@pytest.mark.asyncio
async def test_solver_agent_uses_solver_prompt_role():
    solver = SolverAgent(llm=MockLLM(), registry=get_registry())
    await solver.arun("帮我算一下 1+1")
    prompt = solver.loop.get_last_prompt()
    assert prompt is not None
    assert prompt.role == "solver"


def test_react_graph_runtime_saves_prompt_artifact(tmp_path):
    runtime = ReactGraphRuntime(
        llm=MockLLM(),
        registry=get_registry(),
        trace_dir=str(tmp_path / "replays"),
        prompt_dir=str(tmp_path / "prompts"),
    )
    result = runtime.run("你好")
    prompt = runtime.get_last_prompt()
    assert prompt is not None
    assert prompt.role == "react"
    assert result.prompt_artifact_path
