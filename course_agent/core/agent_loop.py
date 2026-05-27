"""最小 ReAct Agent Loop 实现."""

from __future__ import annotations

import asyncio
import json as _json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from course_agent.core.state import AgentCallbacks, AgentState
from course_agent.llm.base import BaseLLM, LLMMessage, StreamChunk, ToolCall
from course_agent.logger import get_logger
from course_agent.prompt import PromptEnvelope, compile_prompt, save_prompt_artifact
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
    prompt_artifact_path: str | None = None


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
        prompt_role: str = "react",
        prompt_dir: str = "data/prompts",
    ) -> None:
        self.llm = llm
        self.registry = registry or get_registry()
        self.tool_names = tool_names or self.registry.list_names()
        self.max_steps = max_steps
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.prompt_role = prompt_role
        self.prompt_dir = prompt_dir
        self.project_root = Path.cwd()
        self._last_prompt: PromptEnvelope | None = None
        self._last_prompt_artifact_path: str | None = None
        self.log = get_logger("AgentLoop")

    def _build_prompt_envelope(
        self,
        *,
        user_input: str,
        history: list[LLMMessage] | None = None,
        task_notes: dict[str, Any] | None = None,
    ) -> PromptEnvelope:
        envelope = compile_prompt(
            role=self.prompt_role,
            role_prompt=self.system_prompt,
            user_input=user_input,
            history_count=len(history or []),
            project_root=self.project_root,
            task_notes=task_notes,
            metadata={
                "tool_count": len(self.tool_names),
                "max_steps": self.max_steps,
            },
        )
        self._last_prompt = envelope
        self._last_prompt_artifact_path = str(
            save_prompt_artifact(envelope, prompt_dir=self.prompt_dir)
        )
        return envelope

    @staticmethod
    def _build_prompt_messages(envelope: PromptEnvelope) -> list[LLMMessage]:
        messages = [LLMMessage(role="system", content=envelope.static_prefix)]
        if envelope.dynamic_tail:
            messages.append(LLMMessage(role="system", content=envelope.dynamic_tail))
        return messages

    @staticmethod
    def _normalize_history(history: list[LLMMessage] | None) -> list[LLMMessage]:
        return [msg for msg in (history or []) if msg.role != "system"]

    def run(self, user_input: str) -> AgentResult:
        state = AgentState()
        envelope = self._build_prompt_envelope(user_input=user_input)
        state.messages.extend(self._build_prompt_messages(envelope))
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
            prompt_artifact_path=self._last_prompt_artifact_path,
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
        envelope = self._build_prompt_envelope(
            user_input=user_input,
            history=history,
        )
        if history:
            state.messages.extend(self._build_prompt_messages(envelope))
            state.messages.extend(self._normalize_history(history))
        else:
            state.messages.extend(self._build_prompt_messages(envelope))
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
            prompt_artifact_path=self._last_prompt_artifact_path,
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

    # ------------------------------------------------------------------
    # Task 011：流式 Agent Loop
    # ------------------------------------------------------------------

    async def astream_run(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: AgentCallbacks | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """流式 ReAct 循环（Task 011）.

        每一轮：
            1. 用 ``llm.astream()`` 拉取增量；文本 chunk 实时外抛
            2. tool_call 增量内部按 index 拼装；finish_reason='tool_calls' 时停止本轮
            3. 收到 finish_reason='error' → **整体降级**到非流式 ``arun``，把整段 content
               一次性以 ``StreamChunk(delta_text=..., finish_reason='stop')`` 抛出
            4. 没有 tool_call → 结束；有则执行工具，把结果塞回 messages，进下一轮

        最终 chunk 的 finish_reason 永远非 None（'stop' / 'length' / 'error'）。
        """
        state = AgentState()
        envelope = self._build_prompt_envelope(
            user_input=user_input,
            history=history,
        )
        if history:
            state.messages.extend(self._build_prompt_messages(envelope))
            state.messages.extend(self._normalize_history(history))
        else:
            state.messages.extend(self._build_prompt_messages(envelope))
        state.add_message(LLMMessage(role="user", content=user_input))

        tool_schemas = self.registry.to_openai_schemas(self.tool_names)

        for _ in range(self.max_steps):
            state.step += 1
            self.log.debug(f"Step {state.step}: streaming LLM")

            accumulated_text = ""
            # tool_call 拼装：index -> {id, name, arguments(str)}
            accumulated_tcs: dict[int, dict[str, Any]] = {}
            stream_finish_reason: str | None = None
            stream_error: str | None = None

            try:
                aiter = self.llm.astream(state.messages, tools=tool_schemas)
                async for chunk in aiter:
                    if chunk.finish_reason == "error":
                        stream_finish_reason = "error"
                        stream_error = chunk.error or "stream error"
                        break

                    if chunk.delta_text:
                        accumulated_text += chunk.delta_text
                        yield StreamChunk(delta_text=chunk.delta_text)

                    if chunk.tool_call_delta:
                        _merge_tc_delta(accumulated_tcs, chunk.tool_call_delta)

                    if chunk.finish_reason in ("stop", "tool_calls", "length"):
                        stream_finish_reason = chunk.finish_reason
                        break
            except Exception as e:  # noqa: BLE001
                stream_finish_reason = "error"
                stream_error = f"{type(e).__name__}: {e}"

            # ---- 整体降级：流式失败 → 非流式 arun ----
            if stream_finish_reason == "error":
                self.log.warning(
                    f"流式失败，降级到非流式 achat：{stream_error}"
                )
                # 走完整一轮非流式 + 后续 ReAct（保持完整答题能力）
                fallback_history = list(state.messages[:-1])  # 去掉刚加的 user
                fallback_user = (
                    state.messages[-1].content
                    if state.messages and state.messages[-1].role == "user"
                    else user_input
                )
                result = await self.arun(
                    user_input=fallback_user,
                    history=fallback_history if fallback_history else None,
                    callbacks=callbacks,
                )
                yield StreamChunk(
                    delta_text=result.answer,
                    finish_reason="stop",
                )
                return

            # ---- tool_calls 路径 ----
            if accumulated_tcs:
                tool_calls = _materialize_tcs(accumulated_tcs, self.log)
                state.add_message(
                    LLMMessage(
                        role="assistant",
                        content=accumulated_text or None,
                        tool_calls=tool_calls,
                    )
                )
                state.add_trace(
                    "think",
                    accumulated_text or "(no thought)",
                    {"tool_calls": [tc.model_dump() for tc in tool_calls]},
                )
                await self._emit(
                    callbacks, "on_thought", state.step, accumulated_text or ""
                )

                # 给 UI 一行可见的"正在调用工具"提示（不污染最终答案 UI 区分由前端决定）
                names_preview = ", ".join(tc.name for tc in tool_calls)
                yield StreamChunk(
                    delta_text=f"\n\n🔧 正在调用工具：{names_preview} ...\n",
                )

                for call in tool_calls:
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
                continue  # 进下一轮 LLM

            # ---- 无 tool_call 即结束 ----
            final = accumulated_text
            state.final_answer = final
            state.add_message(LLMMessage(role="assistant", content=final))
            state.add_trace("final", final)
            await self._emit(callbacks, "on_final", final)
            yield StreamChunk(finish_reason=stream_finish_reason or "stop")
            return

        # 达到最大步数
        timeout_msg = (
            f"\n\n[已达最大步数 {self.max_steps}，任务未完成]"
        )
        yield StreamChunk(delta_text=timeout_msg, finish_reason="length")

    def get_last_prompt(self) -> PromptEnvelope | None:
        return self._last_prompt


def _merge_tc_delta(
    accumulated: dict[int, dict[str, Any]], delta: dict[str, Any]
) -> None:
    """将一条 tool_call_delta 累加到 ``accumulated[index]``.

    OpenAI 流式 tool_call 行为：
      - 同一 index 在多个 chunk 中陆续给 ``id`` / ``function.name`` / ``function.arguments``（按字符流）
      - id 与 name 通常只在第一次出现；arguments 则需逐 chunk 字符串拼接
    """
    idx = delta.get("index", 0) or 0
    slot = accumulated.setdefault(
        idx, {"id": None, "name": None, "arguments": ""}
    )
    if delta.get("id"):
        slot["id"] = delta["id"]
    fn = delta.get("function") or {}
    if fn.get("name"):
        slot["name"] = fn["name"]
    if fn.get("arguments"):
        slot["arguments"] += fn["arguments"]


def _materialize_tcs(
    accumulated: dict[int, dict[str, Any]], log: Any
) -> list[ToolCall]:
    """把拼装好的 tool_call dict 转成 ``ToolCall`` 列表."""
    import uuid as _uuid

    out: list[ToolCall] = []
    for idx in sorted(accumulated.keys()):
        slot = accumulated[idx]
        name = slot.get("name") or ""
        if not name:
            log.warning(f"tool_call#{idx} 缺 name，跳过")
            continue
        raw_args = slot.get("arguments") or "{}"
        try:
            args = _json.loads(raw_args) if raw_args else {}
            if not isinstance(args, dict):
                args = {}
        except _json.JSONDecodeError:
            log.warning(f"tool_call#{idx} arguments JSON 解析失败：{raw_args[:80]}")
            args = {}
        call_id = slot.get("id") or f"call_{_uuid.uuid4().hex[:8]}"
        out.append(ToolCall(id=call_id, name=name, arguments=args))
    return out
