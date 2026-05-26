"""Orchestrator 单测（Task 012）.

覆盖：
- happy path：plan→1 solve→pass
- 多 sub_task 依次执行 + synthesize 标题
- refine 路径：critic fail → solver 重跑 → 第二轮 pass
- refine 硬上限：critic 每轮都 fail，达到 max_refine_per_task 后强制 break
- planner 两次 JSON 失败 → 单段降级
- OrchestratorResult 字段完整（plan / sub_results / total_llm_calls）
- max_total_llm_calls 超限抛 RuntimeError
- accumulated_context 注入：后一个 sub_task 的 history 里包含前一个 sub_task 的摘要
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from course_agent.agent import Orchestrator
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse
from course_agent.tools.registry import ToolRegistry


class _ScriptLLM(BaseLLM):
    """按调用顺序播放脚本；记录每次收到的 messages 以便断言."""

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


@pytest.mark.asyncio
async def test_orchestrator_happy_path_single_subtask():
    llm = _ScriptLLM(
        [
            _plan(1),
            "答案 A",
            _crit(4, True, "不错"),
        ]
    )
    orch = Orchestrator(
        llm=llm,
        registry=ToolRegistry(),
        max_refine_per_task=2,
        max_total_llm_calls=10,
    )
    result = await orch.arun("执行一个简单任务")
    assert len(result.sub_results) == 1
    assert result.sub_results[0].solver_output == "答案 A"
    assert result.sub_results[0].critic["pass"] is True
    # 单 sub_task 模式：final_answer 等于 solver 输出
    assert result.final_answer == "答案 A"
    assert result.total_llm_calls == 3


@pytest.mark.asyncio
async def test_orchestrator_multi_subtask_synthesize():
    llm = _ScriptLLM(
        [
            _plan(2),
            "Sol1",
            _crit(4, True),
            "Sol2",
            _crit(5, True),
        ]
    )
    orch = Orchestrator(llm=llm, registry=ToolRegistry(), max_total_llm_calls=20)
    result = await orch.arun("两步任务")
    assert len(result.sub_results) == 2
    assert "最终答案" in result.final_answer
    assert "Sub-Task #1" in result.final_answer
    assert "Sub-Task #2" in result.final_answer
    assert "Sol1" in result.final_answer
    assert "Sol2" in result.final_answer


@pytest.mark.asyncio
async def test_orchestrator_refine_path_critic_fail_then_pass():
    llm = _ScriptLLM(
        [
            _plan(1),
            "bad attempt",
            _crit(1, False, "方向错了"),
            "good attempt",
            _crit(4, True, "好多了"),
        ]
    )
    orch = Orchestrator(
        llm=llm,
        registry=ToolRegistry(),
        max_refine_per_task=2,
        max_total_llm_calls=20,
    )
    result = await orch.arun("T")
    sr = result.sub_results[0]
    assert sr.solver_output == "good attempt"
    assert sr.critic["pass"] is True
    assert sr.refine_rounds == 1


@pytest.mark.asyncio
async def test_orchestrator_refine_limit_hits_hard_cap():
    # max_refine_per_task=1 → 循环 2 次（round 0, round 1），都 fail 后 break
    llm = _ScriptLLM(
        [
            _plan(1),
            "try1",
            _crit(1, False, "no"),
            "try2",
            _crit(1, False, "still no"),
        ]
    )
    orch = Orchestrator(
        llm=llm,
        registry=ToolRegistry(),
        max_refine_per_task=1,
        max_total_llm_calls=20,
    )
    result = await orch.arun("T")
    sr = result.sub_results[0]
    # refine 已达上限；最终保留最后一次 solver 输出（未通过也要返回）
    assert sr.solver_output == "try2"
    assert sr.critic["pass"] is False
    assert sr.refine_rounds == 1


@pytest.mark.asyncio
async def test_orchestrator_planner_failure_falls_back_to_single_subtask():
    llm = _ScriptLLM(
        [
            "乱码 1",
            "还是乱码",
            "直接回答",
            _crit(4, True),
        ]
    )
    orch = Orchestrator(
        llm=llm, registry=ToolRegistry(), max_total_llm_calls=20
    )
    result = await orch.arun("一个简单的任务")
    # Planner 降级为 1 个 sub_task
    assert len(result.plan) == 1
    assert len(result.sub_results) == 1
    # 单 sub_task → final_answer 直接是 solver 输出
    assert result.final_answer == "直接回答"


@pytest.mark.asyncio
async def test_orchestrator_result_fields_complete():
    llm = _ScriptLLM(
        [
            _plan(1),
            "A",
            _crit(4, True),
        ]
    )
    orch = Orchestrator(
        llm=llm, registry=ToolRegistry(), max_total_llm_calls=10
    )
    result = await orch.arun("X")
    assert isinstance(result.plan, list)
    assert len(result.plan) == 1
    assert isinstance(result.sub_results, list)
    assert result.total_llm_calls >= 3
    assert result.final_answer


@pytest.mark.asyncio
async def test_orchestrator_raises_when_total_calls_exceed():
    # 预算设得非常小：Plan(1) + Solve(1) 后，Critic 前就应抛
    llm = _ScriptLLM([_plan(2), "A", _crit(1, False), "B", _crit(1, False)])
    orch = Orchestrator(
        llm=llm,
        registry=ToolRegistry(),
        max_refine_per_task=0,
        max_total_llm_calls=2,
    )
    with pytest.raises(RuntimeError, match="上限"):
        await orch.arun("X")


@pytest.mark.asyncio
async def test_orchestrator_injects_previous_subtask_context_into_later():
    llm = _ScriptLLM(
        [
            _plan(2),
            "这是第一段答案",
            _crit(4, True),
            "第二段答案",
            _crit(4, True),
        ]
    )
    orch = Orchestrator(llm=llm, registry=ToolRegistry(), max_total_llm_calls=20)
    await orch.arun("两步任务")
    # 第 4 次调用是第 2 个 sub_task 的 Solver 调用；messages 中应包含第 1 sub_task 摘要
    solver2_msgs = llm.calls[3]
    joined = "\n".join(m.content or "" for m in solver2_msgs)
    assert "Sub-Task #1 完成" in joined
    assert "这是第一段答案" in joined
