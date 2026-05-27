"""Task 016：HITL 节点测试."""

from __future__ import annotations

import pytest

from course_agent.graph.human_nodes import (
    decide_human_gate,
    wait_approval_node,
    wait_human_input_node,
)


def test_decide_human_gate_routes_to_wait_human_input():
    route = decide_human_gate({"user_input": "这题我稍后补充资料"})
    assert route == "wait_human_input"


def test_decide_human_gate_routes_to_wait_approval():
    route = decide_human_gate({"user_input": "需要你确认后再继续"})
    assert route == "wait_approval"


def test_decide_human_gate_routes_to_llm_when_resume_input_exists():
    route = decide_human_gate(
        {"user_input": "需要你确认后再继续", "resume_input": "approved"}
    )
    assert route == "llm"


@pytest.mark.asyncio
async def test_wait_human_input_node_returns_pause_state():
    out = await wait_human_input_node({"trace": []})
    assert out["status"] == "waiting_human_input"
    assert out["done"] is True


@pytest.mark.asyncio
async def test_wait_approval_node_returns_pause_state():
    out = await wait_approval_node({"trace": []})
    assert out["status"] == "waiting_approval"
    assert out["done"] is True
