"""最小 ReAct Agent Loop 实现."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from course_agent.core.state import AgentCallbacks, AgentState
from course_agent.llm.base import BaseLLM, LLMMessage
from course_agent.logger import get_logger
from course_agent.tools.registry import ToolRegistry, get_registry

_DEFAULT_SYSTEM_PROMPT = (
    "你是 Course Agent，一个帮助学生完成课程作业的智能助手。\n"
    "你可以通过调用工具来完成任务。请遵循以下原则：\n"
    "1. 分析学生的问题，思考需要哪些步骤。\n"
    "2. 若需要信息或计算，优先调用工具而不是凭记忆回答。\n"
    "3. 工具结果返回后，判断是否已经足够回答，是则给出最终答案。\n"
    "4. 回答要清晰、有条理，必要时给出步骤或引用。"
)


class AgentResult(BaseModel):
    """Agent 最终执行结果."""

    answer: str
    steps: int
    trace: list[dict[str, Any]]


class AgentLoop:
    """ReAct 风格的最小 Agent Loop.

    每一轮：LLM 产出消息 -> 若有 tool_call 则执行并把结果回传 -> 否则结束。
    """

    def __init__(
        self,
        llm: BaseLLM,
        registry: ToolRegistry | None = None,
        tool_names: list[str] | None = None,
        max_steps: int = 8,
        system_prompt: str | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry or get_registry()
        self.tool_names = tool_names or self.registry.list_names()
        self.max_steps = max_steps
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.log = get_logger("AgentLoop")

    def run(self, user_input: str) -> AgentResult:
        state = AgentState()
        state.add_message(LLMMessage(role="system", content=self.system_prompt))
        state.add_message(LLMMessage(role="user", content=user_input))

        tool_schemas = self.registry.to_openai_schemas(self.tool_names)

        while not state.done and state.step < self.max_steps:
            state.step += 1
            self.log.debug(f"Step {state.step}: calling LLM")

            response = self.llm.chat(messages=state.messages, tools=tool_schemas)

            if response.tool_calls:
                state.add_message(
                    LLMMessage(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )
                state.add_trace(
                    "think",
                    response.content or "(no thought)",
                    {"tool_calls": [tc.model_dump() for tc in response.tool_calls]},
                )

                for call in response.tool_calls:
                    self.log.info(f"Tool call: {call.name}({call.arguments})")
                    state.add_trace("tool_call", call.name, call.arguments)

                    try:
                        tool = self.registry.get(call.name)
                        result = tool.run(**call.arguments)
                    except Exception as e:  # noqa: BLE001
                        result = f"[工具 {call.name} 执行异常] {e}"
                        self.log.warning(result)

                    result_str = str(result)
                    state.add_message(
                        LLMMessage(
                            role="tool",
                            name=call.name,
                            tool_call_id=call.id,
                            content=result_str,
                        )
                    )
                    state.add_trace("tool_result", result_str[:500])
                continue

            final = response.content or ""
            state.final_answer = final
            state.add_message(LLMMessage(role="assistant", content=final))
            state.add_trace("final", final)
            state.done = True

        if not state.done:
            state.final_answer = (
                f"[已达最大步数 {self.max_steps}，任务未完成] "
                f"最近一次状态：{state.messages[-1].content if state.messages else ''}"
            )
            state.add_trace("final", state.final_answer)

        return AgentResult(
            answer=state.final_answer or "",
            steps=state.step,
            trace=[t.model_dump() for t in state.trace],
        )

    async def arun(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: AgentCallbacks | None = None,
    ) -> AgentResult:
        """异步版 Agent Loop，支持回调和多轮历史.

        Args:
            user_input: 本轮用户输入
            history: 之前的对话历史（system + user/assistant 交替），不含当前 user_input
            callbacks: UI 层回调钩子；None 时等同纯运算
        """
        state = AgentState()
        if history:
            state.messages.extend(history)
        else:
            state.add_message(LLMMessage(role="system", content=self.system_prompt))
        state.add_message(LLMMessage(role="user", content=user_input))

        tool_schemas = self.registry.to_openai_schemas(self.tool_names)

        while not state.done and state.step < self.max_steps:
            state.step += 1
            self.log.debug(f"Step {state.step}: calling LLM (async)")

            response = await self.llm.achat(messages=state.messages, tools=tool_schemas)

            if response.tool_calls:
                state.add_message(
                    LLMMessage(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )
                state.add_trace(
                    "think",
                    response.content or "(no thought)",
                    {"tool_calls": [tc.model_dump() for tc in response.tool_calls]},
                )
                await self._emit(callbacks, "on_thought", state.step, response.content or "")

                for call in response.tool_calls:
                    self.log.info(f"Tool call: {call.name}({call.arguments})")
                    state.add_trace("tool_call", call.name, call.arguments)
                    await self._emit(
                        callbacks, "on_tool_call", state.step, call.name, call.arguments
                    )

                    is_error = False
                    try:
                        tool = self.registry.get(call.name)
                        result = await asyncio.to_thread(tool.run, **call.arguments)
                    except Exception as e:  # noqa: BLE001
                        result = f"[工具 {call.name} 执行异常] {e}"
                        self.log.warning(result)
                        is_error = True

                    result_str = str(result)
                    state.add_message(
                        LLMMessage(
                            role="tool",
                            name=call.name,
                            tool_call_id=call.id,
                            content=result_str,
                        )
                    )
                    state.add_trace("tool_result", result_str[:500])
                    await self._emit(
                        callbacks,
                        "on_tool_result",
                        state.step,
                        call.name,
                        result_str,
                        is_error,
                    )
                continue

            final = response.content or ""
            state.final_answer = final
            state.add_message(LLMMessage(role="assistant", content=final))
            state.add_trace("final", final)
            state.done = True
            await self._emit(callbacks, "on_final", final)

        if not state.done:
            state.final_answer = (
                f"[已达最大步数 {self.max_steps}，任务未完成] "
                f"最近一次状态：{state.messages[-1].content if state.messages else ''}"
            )
            state.add_trace("final", state.final_answer)
            await self._emit(callbacks, "on_final", state.final_answer)

        return AgentResult(
            answer=state.final_answer or "",
            steps=state.step,
            trace=[t.model_dump() for t in state.trace],
        )

    @staticmethod
    async def _emit(
        callbacks: AgentCallbacks | None, method: str, *args: Any
    ) -> None:
        """安全地触发一个回调方法；未定义时跳过，异常只打 warning 不影响主流程."""
        if callbacks is None:
            return
        fn = getattr(callbacks, method, None)
        if fn is None:
            return
        try:
            await fn(*args)
        except Exception as e:  # noqa: BLE001
            get_logger("AgentLoop").warning(f"callback {method} 异常: {e}")
