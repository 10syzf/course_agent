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
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.tool_names = tool_names or registry.list_names()
        self.max_steps = max_steps
        self.trace_dir = trace_dir
        self.system_prompt = system_prompt or (
            "你是 Course Agent，一个帮助学生完成课程作业的智能助手。"
        )
        self._callbacks: Any | None = None
        self._last_replay: dict[str, Any] | None = None
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
    ) -> list[dict[str, Any]]:
        if history:
            messages = [m.model_dump() for m in history]
        else:
            messages = [LLMMessage(role="system", content=self.system_prompt).model_dump()]
        messages.append(LLMMessage(role="user", content=user_input).model_dump())
        return messages

    async def arun(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: Any | None = None,
    ) -> ReactGraphResult:
        self._callbacks = callbacks
        try:
            state = await self._graph.ainvoke(
                make_initial_react_state(
                    user_input,
                    messages=self._build_messages(user_input=user_input, history=history),
                    max_steps=self.max_steps,
                    backend=self.backend,
                ),
                config={"configurable": {"thread_id": str(uuid4())}},
            )
        finally:
            self._callbacks = None

        trace = list(state.get("trace", []))
        artifact = build_replay_artifact(
            query=user_input,
            backend=self.backend,
            runtime_kind=self.runtime_kind,
            final_answer=state.get("final_answer", ""),
            steps=int(state.get("steps", 0)),
            trace=trace,
            extra={"tool_results": state.get("tool_results", [])},
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
        )

    def run(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
    ) -> ReactGraphResult:
        import asyncio

        return asyncio.run(self.arun(user_input=user_input, history=history))

    async def astream_run(
        self,
        user_input: str,
        history: list[LLMMessage] | None = None,
        callbacks: Any | None = None,
    ) -> AsyncIterator[StreamChunk]:
        result = await self.arun(user_input=user_input, history=history, callbacks=callbacks)
        if result.answer:
            yield StreamChunk(delta_text=result.answer)
        yield StreamChunk(finish_reason="stop")

    def get_graph_mermaid(self) -> str:
        return draw_react_mermaid(self._graph)

    def get_last_replay(self) -> dict[str, Any] | None:
        return self._last_replay


__all__ = ["ReactGraphResult", "ReactGraphRuntime"]
