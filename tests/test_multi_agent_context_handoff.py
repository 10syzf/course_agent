from __future__ import annotations

import json
from typing import Any

import pytest

from course_agent.agent.orchestrator import Orchestrator
from course_agent.agent.planner import _to_subtask_briefs
from course_agent.agent.solver import _append_handoff_prompt
from course_agent.context import CriticDigest, HandoffContext
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse
from course_agent.tools.registry import ToolRegistry


class _ScriptLLM(BaseLLM):
    def __init__(self, script: list[str]) -> None:
        super().__init__(model='script')
        self._script = list(script)
        self.calls: list[list[LLMMessage]] = []

    def chat(self, messages: list[LLMMessage], tools: list[dict[str, Any]] | None = None, **kwargs: Any) -> LLMResponse:
        self.calls.append(list(messages))
        text = self._script.pop(0) if self._script else '{}'
        return LLMResponse(content=text)


def _plan() -> str:
    return json.dumps({'plan_summary': 'x', 'sub_tasks': [{'id': 1, 'title': 'step1', 'expected_output': 'out1', 'suggested_tools': []}]})


def _crit(score: int, passed: bool, fb: str) -> str:
    return json.dumps({'score': score, 'pass': passed, 'feedback': fb})


def test_append_handoff_prompt_includes_feedback_and_summary():
    prompt = _append_handoff_prompt('BASE', HandoffContext(prior_subtask_summaries=['前文'], critic_feedback='请修复', refine_round=1))
    assert '前文' in prompt
    assert '请修复' in prompt
    assert '第 1 轮' in prompt


def test_to_subtask_briefs_wraps_dicts():
    briefs = _to_subtask_briefs([{'id': 1, 'title': 't', 'expected_output': 'o', 'suggested_tools': []}])
    assert len(briefs) == 1
    assert briefs[0].sub_task['title'] == 't'


def test_critic_digest_from_result_maps_fields():
    digest = CriticDigest.from_result({'score': 2, 'pass': False, 'feedback': '缺少步骤'})
    assert digest.score == 2
    assert digest.pass_ is False
    assert digest.must_fix == ['缺少步骤']


@pytest.mark.asyncio
async def test_orchestrator_refine_feedback_reaches_second_solver_call():
    llm = _ScriptLLM([_plan(), 'bad', _crit(1, False, '方向错了'), 'good', _crit(4, True, '好了')])
    orch = Orchestrator(llm=llm, registry=ToolRegistry(), max_refine_per_task=1, max_total_llm_calls=10)
    await orch.arun('任务')
    solver_second_msgs = llm.calls[3]
    joined = '\n'.join(m.content or '' for m in solver_second_msgs)
    assert '方向错了' in joined
