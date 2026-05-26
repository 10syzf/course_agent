"""BaseAgent Protocol + AgentMessage + AgentState.scratch 单测（Task 012）.

覆盖：
- ``ExaminerAgent`` / ``SolverAgent`` / ``PlannerAgent`` / ``CriticAgent`` 都满足 ``BaseAgent`` 鸭子契约
- ``AgentMessage`` 序列化 + ``to_llm_message`` 角色与前缀
- ``AgentState.scratch`` 默认空 dict + 可写
"""

from __future__ import annotations

from course_agent.agent import (
    AgentMessage,
    BaseAgent,
    CriticAgent,
    ExaminerAgent,
    PlannerAgent,
    SolverAgent,
)
from course_agent.core.state import AgentState
from course_agent.llm.mock import MockLLM


def test_agent_message_default_role_and_meta():
    msg = AgentMessage(agent_name="Planner", content="hi")
    assert msg.role == "assistant"
    assert msg.meta == {}
    assert msg.content == "hi"


def test_agent_message_to_llm_message_prefixes_agent_name():
    msg = AgentMessage(agent_name="Critic", content="评分: 4")
    llm_msg = msg.to_llm_message()
    assert llm_msg.role == "assistant"
    assert "Critic" in llm_msg.content
    assert "评分: 4" in llm_msg.content


def test_agent_message_to_llm_message_falls_back_to_assistant_for_invalid_role():
    msg = AgentMessage(agent_name="X", role="planner", content="abc")
    llm_msg = msg.to_llm_message()
    assert llm_msg.role == "assistant"


def test_agent_message_serializable_with_meta():
    msg = AgentMessage(
        agent_name="Solver", content="ok", meta={"sub_task_id": 1}
    )
    d = msg.model_dump()
    assert d["agent_name"] == "Solver"
    assert d["meta"] == {"sub_task_id": 1}


def test_agent_state_scratch_default_empty_dict():
    s = AgentState()
    assert s.scratch == {}
    s.scratch["foo"] = 1
    assert s.scratch == {"foo": 1}


def test_examiner_agent_satisfies_base_agent_protocol():
    ex = ExaminerAgent(llm=MockLLM())
    assert isinstance(ex, BaseAgent)
    assert hasattr(ex, "name") or hasattr(ex, "allowed_tools")
    assert isinstance(ex.allowed_tools, list)


def test_planner_solver_critic_satisfy_base_agent_protocol():
    llm = MockLLM()
    for cls in (PlannerAgent, SolverAgent, CriticAgent):
        agent = cls(llm=llm)
        assert isinstance(agent, BaseAgent), f"{cls.__name__} 不满足 BaseAgent 协议"
        assert agent.name in ("Planner", "Solver", "Critic")
        assert isinstance(agent.allowed_tools, list)
