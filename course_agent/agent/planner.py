"""PlannerAgent（Task 012）.

职责：拆解用户的复杂任务为有序、可独立执行的 sub-task 列表。

设计要点：
- 工具白名单：``(kb_search, list_mistakes)`` —— 只能"看资料"，不能"动手"
- 强制 JSON 输出 + 失败重试 1 次（沿用 Task 011 ``generate_question`` 模式）
- 解析失败的最终降级：返回单段 sub_task（即把原任务整段塞给 Solver），
  保证 Orchestrator 永远能跑通，不会因 Plan 失败而整体崩
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from course_agent.capabilities.router import CapabilityRouter
from course_agent.context.handoff import SubTaskBrief
from course_agent.core.agent_loop import AgentLoop, AgentResult
from course_agent.core.state import AgentCallbacks
from course_agent.llm.base import BaseLLM, LLMMessage, StreamChunk
from course_agent.logger import get_logger
from course_agent.observability.metrics import set_current_agent
from course_agent.tools.registry import ToolRegistry, get_registry

_log = get_logger("PlannerAgent")

PLANNER_SYSTEM_PROMPT = """你是 Course Agent 的 Planner——任务规划员。
你的职责：
1. 阅读用户的原始任务
2. 拆分成 1～5 个**有序、可独立执行**的 sub-task
3. 每个 sub-task 标明：标题 / 预期产出 / 推荐工具（建议而非强制）
4. 仅在需要确认知识点时调用 kb_search / list_mistakes
5. 你**不能**调用任何"动手"工具（写文件 / 跑代码 / 联网搜）

【硬约束】
- **只输出一个 JSON 对象**，不要任何 markdown 代码块包裹或解释文字
- sub_tasks 数量不超过 5
- 每个 sub_task 都要给出具体的、可执行的 expected_output

输出格式：
{
  "plan_summary": "<一句话概括整个任务>",
  "sub_tasks": [
    {"id": 1, "title": "...", "expected_output": "...", "suggested_tools": ["pdf_read"]},
    {"id": 2, "title": "...", "expected_output": "...", "suggested_tools": ["calculator"]}
  ]
}
"""

_PLANNER_ALLOWED_TOOLS = ("kb_search", "list_mistakes")
_MAX_SUB_TASKS = 5


def _parse_plan_json(raw: str) -> list[dict[str, Any]] | None:
    """解析 LLM 的 JSON 输出为 sub_tasks 列表；失败返回 None."""
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
    if not isinstance(obj, dict):
        return None
    sub_tasks = obj.get("sub_tasks")
    if not isinstance(sub_tasks, list) or not sub_tasks:
        return None
    out: list[dict[str, Any]] = []
    for i, st in enumerate(sub_tasks, 1):
        if not isinstance(st, dict):
            continue
        title = str(st.get("title", "")).strip()
        if not title:
            continue
        out.append(
            {
                "id": int(st.get("id", i)),
                "title": title,
                "expected_output": str(st.get("expected_output", "")).strip()
                or "完成上述任务并给出答案",
                "suggested_tools": st.get("suggested_tools") or [],
            }
        )
    return out or None


def _to_subtask_briefs(sub_tasks: list[dict[str, Any]]) -> list[SubTaskBrief]:
    """把 Planner 的原始 sub_task dict 转为结构化 brief."""
    return [SubTaskBrief.from_sub_task(item) for item in sub_tasks]


class PlannerAgent:
    """任务规划员 Agent：限定工具集 + JSON 输出."""

    name = "Planner"

    def __init__(
        self,
        llm: BaseLLM,
        registry: ToolRegistry | None = None,
        max_steps: int = 4,
        max_sub_tasks: int = _MAX_SUB_TASKS,
        capability_router: CapabilityRouter | None = None,
    ) -> None:
        reg = registry or get_registry()
        all_names = set(reg.list_names())
        tool_names = [n for n in _PLANNER_ALLOWED_TOOLS if n in all_names]
        self.allowed_tools = tool_names
        self.max_sub_tasks = max_sub_tasks
        self.capability_router = capability_router
        self.loop = AgentLoop(
            llm=llm,
            registry=reg,
            tool_names=tool_names,
            max_steps=max_steps,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            prompt_role="planner",
        )

    @property
    def llm(self) -> BaseLLM:
        return self.loop.llm

    async def plan(self, user_task: str) -> list[dict[str, Any]]:
        """规划任务，返回 sub_tasks 列表（结构化 dict）.

        - JSON 解析失败重试 1 次
        - 仍失败：降级为「单 sub_task 模式」（把原任务整段丢给 Solver）
        - sub_tasks 数 > max_sub_tasks 时**截断 + 警告日志**
        """
        token = set_current_agent(self.name)
        try:
            return await self._plan_impl(user_task)
        finally:
            from course_agent.observability.metrics import _CURRENT_AGENT
            _CURRENT_AGENT.reset(token)

    async def _plan_impl(self, user_task: str) -> list[dict[str, Any]]:
        capability_hint = ""
        if self.capability_router is not None:
            caps = self.capability_router.summarize_for_planner(max_items=8)
            if caps:
                lines = [
                    f"- {c['name']} ({c['kind']})：{c['description']}"
                    for c in caps
                ]
                capability_hint = (
                    "\n\n可供 Solver 后续使用的外部能力（仅供你规划时参考，"
                    "你自己不能直接调用）：\n" + "\n".join(lines)
                )
        prompt = (
            f"原始任务：\n{user_task}\n\n"
            "请按系统提示要求，输出 1～5 个 sub_tasks 的 JSON 对象。"
            f"{capability_hint}"
        )

        sub_tasks: list[dict[str, Any]] | None = None
        last_raw = ""

        for attempt in range(2):
            try:
                result = await self.loop.arun(user_input=prompt)
                last_raw = result.answer
            except Exception as e:  # noqa: BLE001
                _log.warning(f"Planner LLM 调用失败 attempt={attempt}：{e}")
                continue
            sub_tasks = _parse_plan_json(last_raw)
            if sub_tasks:
                break
            prompt = (
                f"原始任务：\n{user_task}\n\n"
                "⚠️ 上次输出无法解析为 JSON，请重新规划；"
                "**仅输出 JSON 本体**（不要任何 ``` 代码块或解释文字）。"
            )

        if not sub_tasks:
            _log.warning(
                f"Planner 解析 JSON 失败（重试已用尽），降级为单 sub_task 模式；raw[:120]={last_raw[:120]}"
            )
            return [
                {
                    "id": 1,
                    "title": user_task[:80],
                    "expected_output": "直接回答用户的原始任务",
                    "suggested_tools": [],
                }
            ]

        if len(sub_tasks) > self.max_sub_tasks:
            _log.warning(
                f"Planner 输出 {len(sub_tasks)} 个 sub_tasks 超过上限 {self.max_sub_tasks}，截断"
            )
            sub_tasks = sub_tasks[: self.max_sub_tasks]
        return sub_tasks

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
        return f"PlannerAgent(tools={self.allowed_tools}, max_sub_tasks={self.max_sub_tasks})"


__all__ = ["PlannerAgent", "PLANNER_SYSTEM_PROMPT", "_parse_plan_json", "_to_subtask_briefs"]
