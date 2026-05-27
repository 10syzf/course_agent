"""Task 014：LangGraph Runtime / Orchestrator 测试."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse
from course_agent.runtime.langgraph_runtime import LangGraphRuntime
from course_agent.tools.registry import ToolRegistry


class _ScriptLLM(BaseLLM):
    def __init__(self, script: list[str]) -> None:
        super().__init__(model="script")
        self._script = list(script)
        self.calls: list[list[LLMMessage]] = []

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.calls.append(list(messages))
        text = self._script.pop(0) if self._script else "{}"
        return LLMResponse(content=text, finish_reason="stop")


def _plan(n: int) -> str:
    return json.dumps(
        {
            "plan_summary": f"{n} 个 sub_task",
            "sub_tasks": [
                {
                    "id": i,
                    "title": f"step{i}",
                    "expected_output": f"out{i}",
                    "suggested_tools": [],
                }
                for i in range(1, n + 1)
            ],
        }
    )


def _crit(score: int, passed: bool, fb: str = "ok") -> str:
    return json.dumps({"score": score, "pass": passed, "feedback": fb})


def _runtime(script: list[str], **kwargs: Any) -> LangGraphRuntime:
    return LangGraphRuntime(
        llm=_ScriptLLM(script),
        registry=ToolRegistry(),
        checkpoint=kwargs.pop("checkpoint", "memory"),
        draw_graph=kwargs.pop("draw_graph", True),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_langgraph_runtime_happy_path_single_subtask():
    runtime = _runtime([_plan(1), "答案 A", _crit(4, True, "不错")])
    result = await runtime.arun("执行一个简单任务")
    assert result.final_answer == "答案 A"
    assert result.total_llm_calls == 3
    assert len(result.sub_results) == 1


@pytest.mark.asyncio
async def test_langgraph_runtime_multi_subtask_synthesize():
    runtime = _runtime([_plan(2), "Sol1", _crit(4, True), "Sol2", _crit(5, True)])
    result = await runtime.arun("两步任务")
    assert len(result.sub_results) == 2
    assert "最终答案" in result.final_answer
    assert "Sub-Task #1" in result.final_answer
    assert "Sub-Task #2" in result.final_answer


@pytest.mark.asyncio
async def test_langgraph_runtime_refine_then_pass():
    runtime = _runtime(
        [_plan(1), "bad attempt", _crit(1, False, "方向错了"), "good attempt", _crit(4, True)]
    )
    result = await runtime.arun("T")
    sr = result.sub_results[0]
    assert sr.solver_output == "good attempt"
    assert sr.critic["pass"] is True
    assert sr.refine_rounds == 1


@pytest.mark.asyncio
async def test_langgraph_runtime_respects_refine_limit():
    runtime = _runtime(
        [_plan(1), "try1", _crit(1, False, "no"), "try2", _crit(1, False, "still no")],
        max_refine_per_task=1,
    )
    result = await runtime.arun("T")
    sr = result.sub_results[0]
    assert sr.solver_output == "try2"
    assert sr.critic["pass"] is False
    assert sr.refine_rounds == 1


@pytest.mark.asyncio
async def test_langgraph_runtime_planner_fallback_still_works():
    runtime = _runtime(["乱码 1", "还是乱码", "直接回答", _crit(4, True)])
    result = await runtime.arun("一个简单的任务")
    assert len(result.plan) == 1
    assert result.final_answer == "直接回答"


@pytest.mark.asyncio
async def test_langgraph_runtime_raises_when_total_calls_exceed():
    runtime = _runtime(
        [_plan(2), "A", _crit(1, False), "B", _crit(1, False)],
        max_refine_per_task=0,
        max_total_llm_calls=2,
    )
    with pytest.raises(RuntimeError, match="上限"):
        await runtime.arun("X")


@pytest.mark.asyncio
async def test_langgraph_runtime_injects_previous_subtask_context():
    runtime = _runtime(
        [_plan(2), "这是第一段答案", _crit(4, True), "第二段答案", _crit(4, True)]
    )
    llm = runtime.llm
    await runtime.arun("两步任务")
    solver2_msgs = llm.calls[3]
    joined = "\n".join(m.content or "" for m in solver2_msgs)
    assert "Sub-Task #1 完成" in joined
    assert "这是第一段答案" in joined


def test_langgraph_runtime_mermaid_contains_graph_nodes():
    runtime = _runtime([_plan(1), "A", _crit(4, True)])
    mermaid = runtime.get_graph_mermaid()
    assert "graph TD" in mermaid or "flowchart TD" in mermaid
    assert "planner" in mermaid.lower() or "pick_next_subtask" in mermaid.lower()


def test_langgraph_runtime_supports_checkpoint_none():
    runtime = _runtime([_plan(1), "A", _crit(4, True)], checkpoint="none")
    assert runtime._checkpointer is None


def test_langgraph_runtime_builds_sqlite_checkpoint():
    runtime = _runtime([_plan(1), "A", _crit(4, True)], checkpoint="sqlite")
    assert runtime._checkpointer is not None
    db_path = Path("/Users/bytedance/Desktop/syzf项目/cousre_agent/data/langgraph_checkpoint.db")
    assert db_path.parent.exists()
