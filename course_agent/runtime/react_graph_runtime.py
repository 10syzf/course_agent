"""Task 015：Graph-native 单 Agent ReAct Runtime."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from course_agent.graph.react_graph import (
    build_react_graph,
    draw_react_mermaid,
    make_initial_react_state,
)
from course_agent.graph.trace import build_replay_artifact
from course_agent.llm.base import LLMMessage, StreamChunk
from course_agent.prompt import PromptEnvelope, compile_prompt, save_prompt_artifact
from course_agent.runtime.replay import save_replay_artifact
from course_agent.tools.registry import ToolRegistry


class ReactGraphResult(BaseModel):
    """Graph-native 单 Agent 运行结果."""

    answer: str
    steps: int
    trace: list[dict[str, Any]]
    runtime_kind: str = "react_graph"
    backend: str = "langgraph"
    replay_path: str | None = None
    prompt_artifact_path: str | None = None
    status: str = "completed"
    waiting_reason: str | None = None
    session_id: str | None = None


class ReactGraphRuntime:
    """单 Agent 的 LangGraph ReAct Runtime."""

    backend = "langgraph"
    runtime_kind = "react_graph"

    def __init__(
        self,
        *,
        llm: Any,
        registry: ToolRegistry,
        tool_names: list[str] | None = None,
        max_steps: int = 8,
        system_prompt: str | None = None,
        trace_dir: str = "data/replays",
        prompt_dir: str = "data/prompts",
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.tool_names = tool_names or registry.list_names()
        self.max_steps = max_steps
        self.trace_dir = trace_dir
        self.prompt_dir = prompt_dir
        self.system_prompt = system_prompt or (
            "你是 Course Agent，一个帮助学生完成课程作业的智能助手。"
        )
        self._callbacks: Any | None = None
        self._last_replay: dict[str, Any] | None = None
        self._last_prompt: PromptEnvelope | None = None
        self._last_prompt_artifact_path: str | None = None
        self._tool_schemas = self.registry.to_openai_schemas(self.tool_names)
        self._graph = build_react_graph(
            llm=self.llm,
            registry=self.registry,
            tool_schemas=self._tool_schemas,
            callbacks_getter=lambda: self._callbacks,
        )

    def _build_messages(
        self,
        *,
        user_input: str,
        history: list[LLMMessage] | None = None,
        resume_input: str | None = None,
    ) -> list[dict[str, Any]]:
        envelope = compile_prompt(
            role="react",
            role_prompt=self.system_prompt,
            user_input=user_input,
            history_count=len(history or []),
            task_notes={"resume_input": resume_input or ""},
        )
        self._last_prompt = envelope
        self._last_prompt_artifact_path = str(
            save_prompt_artifact(envelope, prompt_dir=self.prompt_dir)
        )
        messages = [LLMMessage(role="system", content=envelope.static_prefix).model_dump()]
        if envelope.dynamic_tail:
            messages.append(
                LLMMessage(role="system", content=envelope.dynamic_tail).model_dump()
            )
        if history:
            messages.extend([m.model_dump() for m in history if m.role != "system"])
        messages.append(LLMMessage(role="user", content=user_input).model_dump())
        if resume_input:
            messages.append(
                LLMMessage(
                    role="user",
                    content=f"补充信息 / 继续指令：{resume_input}",
                ).model_dump()
            )
        return messages

    async def arun(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: Any | None = None,
        *,
        session_id: str | None = None,
        resume_input: str | None = None,
    ) -> ReactGraphResult:
        self._callbacks = callbacks
        try:
            state = await self._graph.ainvoke(
                make_initial_react_state(
                    user_input,
                    messages=self._build_messages(
                        user_input=user_input,
                        history=history,
                        resume_input=resume_input,
                    ),
                    max_steps=self.max_steps,
                    backend=self.backend,
                    session_id=session_id,
                    resume_input=resume_input,
                ),
                config={"configurable": {"thread_id": session_id or str(uuid4())}},
            )
        finally:
            self._callbacks = None

        trace = list(state.get("trace", []))
        status = str(state.get("status", "completed") or "completed")
        waiting_reason = state.get("waiting_reason")
        artifact = build_replay_artifact(
            query=user_input,
            backend=self.backend,
            runtime_kind=self.runtime_kind,
            final_answer=state.get("final_answer", ""),
            steps=int(state.get("steps", 0)),
            trace=trace,
            thread_id=session_id,
            extra={
                "tool_results": state.get("tool_results", []),
                "status": status,
                "waiting_reason": waiting_reason,
                "session_id": session_id,
            },
        )
        replay_path = save_replay_artifact(artifact, trace_dir=self.trace_dir)
        self._last_replay = {**artifact, "path": str(replay_path)}
        return ReactGraphResult(
            answer=state.get("final_answer", ""),
            steps=int(state.get("steps", 0)),
            trace=trace,
            runtime_kind=self.runtime_kind,
            backend=self.backend,
            replay_path=str(replay_path),
            prompt_artifact_path=self._last_prompt_artifact_path,
            status=status,
            waiting_reason=waiting_reason,
            session_id=session_id,
        )

    def run(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        *,
        session_id: str | None = None,
        resume_input: str | None = None,
    ) -> ReactGraphResult:
        import asyncio

        return asyncio.run(
            self.arun(
                user_input=user_input,
                history=history,
                session_id=session_id,
                resume_input=resume_input,
            )
        )

    async def astream_run(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: Any | None = None,
        *,
        session_id: str | None = None,
        resume_input: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        result = await self.arun(
            user_input=user_input,
            history=history,
            callbacks=callbacks,
            session_id=session_id,
            resume_input=resume_input,
        )
        if result.answer:
            yield StreamChunk(delta_text=result.answer)
        yield StreamChunk(finish_reason="stop")

    def get_graph_mermaid(self) -> str:
        return draw_react_mermaid(self._graph)

    def get_last_replay(self) -> dict[str, Any] | None:
        return self._last_replay

    def get_last_prompt(self) -> PromptEnvelope | None:
        return self._last_prompt


__all__ = ["ReactGraphResult", "ReactGraphRuntime"]
