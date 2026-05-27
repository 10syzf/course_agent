"""CriticAgent（Task 012）.

独立 LLM-as-judge：评审 Solver 的输出是否满足 sub-task 的预期产出。

设计要点：
- **独立 LLM 实例**（避免单 Agent 自评的"自我合理化"偏差）
- 工具白名单：``(kb_search,)`` —— 仅可核对教材，不能"动手"
- 强制 JSON 输出：``{score, pass, feedback}``；失败重试 1 次；
  仍失败则降级为 ``score=3, pass=True, feedback="critic JSON 解析失败，默认通过"``
  （**保守策略**：宁可放过、不可阻塞主流程）
- score 越界（< 0 / > 5）时裁剪到 [0, 5]
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from course_agent.context.handoff import CriticDigest
from course_agent.core.agent_loop import AgentLoop, AgentResult
from course_agent.core.state import AgentCallbacks
from course_agent.llm.base import BaseLLM, LLMMessage, StreamChunk
from course_agent.logger import get_logger
from course_agent.observability.metrics import set_current_agent
from course_agent.tools.registry import ToolRegistry, get_registry

_log = get_logger("CriticAgent")

CRITIC_SYSTEM_PROMPT = """你是 Course Agent 的 Critic——独立评审员。
你会收到 (sub_task, solver_output)，需要客观评分：
- score: 0-5（5=完美 / 4=合格 / 3=有瑕疵但可用 / 2=方向对但结论错 / 1=偏题 / 0=完全不会）
- pass: 当 score >= 3 时为 true，否则为 false
- feedback: 一句话指出问题或亮点（≤ 100 字）

你**只能**调用 kb_search 用于核对教材；不能调用任何"动手"工具。

【硬约束】
- **只输出一个 JSON 对象**，不要任何 markdown 代码块包裹或解释文字
- score 必须是整数；pass 必须是布尔值；feedback 必须是字符串

输出格式：
{"score": 3, "pass": true, "feedback": "答对了但缺步骤说明"}
"""

_CRITIC_ALLOWED_TOOLS = ("kb_search",)


def _parse_critic_json(raw: str) -> dict[str, Any] | None:
    """解析 Critic 的 JSON 输出；失败返回 None."""
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[-1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip().rstrip("`").strip()
    if "{" in s and "}" in s:
        s = s[s.find("{") : s.rfind("}") + 1]
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict) or "score" not in obj:
        return None
    try:
        score = int(obj.get("score", 0))
    except (ValueError, TypeError):
        return None
    score = max(0, min(5, score))
    pass_ = obj.get("pass")
    if not isinstance(pass_, bool):
        pass_ = score >= 3
    feedback = str(obj.get("feedback", "")).strip() or "（无反馈）"
    if len(feedback) > 200:
        feedback = feedback[:200] + "..."
    return {"score": score, "pass": pass_, "feedback": feedback}


def _build_critic_prompt(sub_task: dict[str, Any], solver_output: str) -> str:
    title = sub_task.get("title", "")
    expected = sub_task.get("expected_output", "")
    return (
        f"## Sub-Task\n"
        f"**标题**：{title}\n"
        f"**预期产出**：{expected}\n\n"
        f"## Solver 的回答\n{solver_output}\n\n"
        "请按系统提示要求评分，**仅输出 JSON 本体**。"
    )


class CriticAgent:
    """独立评审员 Agent：限定工具集 + JSON 输出."""

    name = "Critic"

    def __init__(
        self,
        llm: BaseLLM,
        registry: ToolRegistry | None = None,
        max_steps: int = 3,
    ) -> None:
        reg = registry or get_registry()
        all_names = set(reg.list_names())
        tool_names = [n for n in _CRITIC_ALLOWED_TOOLS if n in all_names]
        self.allowed_tools = tool_names
        self.loop = AgentLoop(
            llm=llm,
            registry=reg,
            tool_names=tool_names,
            max_steps=max_steps,
            system_prompt=CRITIC_SYSTEM_PROMPT,
            prompt_role="critic",
        )

    @property
    def llm(self) -> BaseLLM:
        return self.loop.llm

    async def critique(
        self, sub_task: dict[str, Any], solver_output: str
    ) -> dict[str, Any]:
        """评审一个 sub_task 的 solver_output；返回 ``{score, pass, feedback}``.

        - JSON 解析失败重试 1 次
        - 仍失败：保守降级（score=3, pass=True）以免阻塞主流程
        """
        token = set_current_agent(self.name)
        try:
            return await self._critique_impl(sub_task, solver_output)
        finally:
            from course_agent.observability.metrics import _CURRENT_AGENT
            _CURRENT_AGENT.reset(token)

    async def _critique_impl(
        self, sub_task: dict[str, Any], solver_output: str
    ) -> dict[str, Any]:
        prompt = _build_critic_prompt(sub_task, solver_output)
        last_raw = ""
        for attempt in range(2):
            try:
                result = await self.loop.arun(user_input=prompt)
                last_raw = result.answer
            except Exception as e:  # noqa: BLE001
                _log.warning(f"Critic LLM 调用失败 attempt={attempt}：{e}")
                continue
            parsed = _parse_critic_json(last_raw)
            if parsed:
                digest = CriticDigest.from_result(parsed)
                return {
                    "score": digest.score,
                    "pass": digest.pass_,
                    "feedback": digest.feedback,
                    "must_fix": digest.must_fix,
                    "optional_suggestions": digest.optional_suggestions,
                    "evidence": digest.evidence,
                }
            prompt = (
                _build_critic_prompt(sub_task, solver_output)
                + "\n\n⚠️ 上次输出无法解析为 JSON，请重新评审；"
                "**仅输出 JSON 本体**（不要任何 ``` 或解释文字）。"
            )

        _log.warning(
            f"Critic 解析 JSON 失败（重试已用尽），降级为保守通过；raw[:120]={last_raw[:120]}"
        )
        digest = CriticDigest.from_result(
            {
                "score": 3,
                "pass": True,
                "feedback": "⚠️ Critic JSON 解析失败，默认通过",
            }
        )
        return {
            "score": digest.score,
            "pass": digest.pass_,
            "feedback": digest.feedback,
            "must_fix": digest.must_fix,
            "optional_suggestions": digest.optional_suggestions,
            "evidence": digest.evidence,
        }

    async def arun(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: AgentCallbacks | None = None,
    ) -> AgentResult:
        return await self.loop.arun(
            user_input=user_input, history=history, callbacks=callbacks
        )

    def astream_run(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: AgentCallbacks | None = None,
    ) -> AsyncIterator[StreamChunk]:
        return self.loop.astream_run(
            user_input=user_input, history=history, callbacks=callbacks
        )

    def __repr__(self) -> str:
        return f"CriticAgent(tools={self.allowed_tools}, max_steps={self.loop.max_steps})"


__all__ = ["CriticAgent", "CRITIC_SYSTEM_PROMPT", "_parse_critic_json"]
