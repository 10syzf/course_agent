"""Examiner Agent（Task 011）.

多 Agent 编排的第一块砖：把 ReAct AgentLoop 套上「**限定工具集 + 独立 system_prompt**」
的薄壳，扮演「出题人 + 极简 grader」的角色。

设计要点：
- 复用 ``AgentLoop``，**不额外写新的循环逻辑**——避免双份维护
- 只允许调用：generate_question / kb_search / add_mistake / list_mistakes / review_mistake
- 不允许调：python_exec / web_search / file_write 等无关工具（限定工具集生效）
- system_prompt 强引导 LLM「学生答错时自动调 add_mistake」——本期版本的极简 grader
- 同时暴露 ``arun()`` 与 ``astream_run()``（与 AgentLoop 接口对齐）
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from course_agent.core.agent_loop import AgentLoop, AgentResult
from course_agent.core.state import AgentCallbacks
from course_agent.llm.base import BaseLLM, LLMMessage, StreamChunk
from course_agent.tools.registry import ToolRegistry, get_registry

EXAMINER_SYSTEM_PROMPT = """你是 Examiner—— Course Agent 阵营中的"严格但鼓励的助教"。
你的人设与职责：

【主线流程】
1. 用户进入「出题模式」时，**先调 generate_question 出一道题**（默认 question_type="解答题"，
   difficulty="中"）。可优先选取学生错题本里出现频率高的 tag。
2. 把题目（含题面 + 教材出处）展示给学生，**不要泄露 correct_answer**。
3. 等学生作答；**根据学生回答与 generate_question 返回的 correct_answer 自我判分（0-5）**：
   - 5 = 完全正确且简洁
   - 4 = 正确但啰嗦或小瑕疵
   - 3 = 关键步骤对，结论略有偏差
   - 2 = 思路对方向，结论错
   - 1 = 答非所问/瞎蒙对部分
   - 0 = 完全不会
4. **如果 quality < 3（即学生答错），立刻调用 add_mistake 把这道题写入错题本**，
   tags 取自 generate_question 输入的 tag，source 标记为 "examiner_generated"。
5. 给学生**简短讲解**（基于 explanation 字段），并在结尾问："要再来一道同类型/进阶题吗？"

【工具白名单】
你只能调用：generate_question / kb_search / add_mistake / list_mistakes / review_mistake
**严禁调用** python_exec / web_search / web_fetch / file_write / image_ocr 等无关工具。

【风格要求】
- 中文回复，简洁不啰嗦
- 题目用 Markdown 列表/代码块；公式用 $...$ LaTeX
- 答错入库时给学生一条**可见**的"✅ 已记入错题本 #N"提示（这是 add_mistake 的返回值，照搬即可）
"""

_EXAMINER_ALLOWED_TOOLS = (
    "generate_question",
    "kb_search",
    "add_mistake",
    "list_mistakes",
    "review_mistake",
)


class ExaminerAgent:
    """出题人 Agent：限定工具集 + 独立 system_prompt 的 AgentLoop 包装."""

    def __init__(
        self,
        llm: BaseLLM,
        registry: ToolRegistry | None = None,
        max_steps: int = 6,
        system_prompt: str | None = None,
    ) -> None:
        reg = registry or get_registry()
        all_names = set(reg.list_names())
        # 仅保留白名单中且实际已注册的工具，缺哪个跳哪个（生产环境可能没装某些工具）
        tool_names = [n for n in _EXAMINER_ALLOWED_TOOLS if n in all_names]
        self.allowed_tools = tool_names
        self.loop = AgentLoop(
            llm=llm,
            registry=reg,
            tool_names=tool_names,
            max_steps=max_steps,
            system_prompt=system_prompt or EXAMINER_SYSTEM_PROMPT,
        )

    @property
    def llm(self) -> BaseLLM:
        return self.loop.llm

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

    def __repr__(self) -> str:  # noqa: D401
        return (
            f"ExaminerAgent(tools={self.allowed_tools}, "
            f"max_steps={self.loop.max_steps})"
        )


__all__: list[str] = ["ExaminerAgent", "EXAMINER_SYSTEM_PROMPT"]


_ = Any  # keep typing import alive (used in future extensions)
