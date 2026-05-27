"""Task 014：现有抽象到 LangChain 的桥接层."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool, StructuredTool

from course_agent.capabilities.base import CapabilitySpec
from course_agent.capabilities.registry import CapabilityRegistry
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse, ToolCall
from course_agent.tools.registry import Tool, ToolRegistry


def llm_message_to_langchain(message: LLMMessage) -> BaseMessage:
    """把项目内消息转成 LangChain message."""
    if message.role == "system":
        return SystemMessage(content=message.content or "", name=message.name)
    if message.role == "user":
        return HumanMessage(content=message.content or "", name=message.name)
    if message.role == "tool":
        return ToolMessage(
            content=message.content or "",
            name=message.name,
            tool_call_id=message.tool_call_id or "tool-call",
        )
    return AIMessage(
        content=message.content or "",
        name=message.name,
        tool_calls=[
            {
                "id": tc.id,
                "name": tc.name,
                "args": tc.arguments,
                "type": "tool_call",
            }
            for tc in (message.tool_calls or [])
        ],
    )


def langchain_message_to_llm(message: BaseMessage) -> LLMMessage:
    """把 LangChain message 转回项目内消息."""
    if isinstance(message, SystemMessage):
        return LLMMessage(role="system", content=_stringify_content(message.content), name=message.name)
    if isinstance(message, HumanMessage):
        return LLMMessage(role="user", content=_stringify_content(message.content), name=message.name)
    if isinstance(message, ToolMessage):
        return LLMMessage(
            role="tool",
            content=_stringify_content(message.content),
            name=message.name,
            tool_call_id=message.tool_call_id,
        )
    tool_calls = []
    for tc in getattr(message, "tool_calls", []) or []:
        tool_calls.append(
            ToolCall(
                id=str(tc.get("id", "tool-call")),
                name=str(tc.get("name", "")),
                arguments=dict(tc.get("args", {}) or {}),
            )
        )
    return LLMMessage(
        role="assistant",
        content=_stringify_content(getattr(message, "content", "")),
        name=getattr(message, "name", None),
        tool_calls=tool_calls or None,
    )


def llm_messages_to_langchain(messages: list[LLMMessage]) -> list[BaseMessage]:
    return [llm_message_to_langchain(message) for message in messages]


def langchain_messages_to_llm(messages: list[BaseMessage]) -> list[LLMMessage]:
    return [langchain_message_to_llm(message) for message in messages]


def tool_to_langchain(tool: Tool) -> BaseTool:
    """把项目内 Tool 暴露为 LangChain StructuredTool."""

    def _runner(**kwargs: Any) -> Any:
        return tool.run(**kwargs)

    return StructuredTool.from_function(
        func=_runner,
        name=tool.name,
        description=tool.description,
        args_schema=None,
    ).model_copy(
        update={
            "args_schema": None,
            "description": tool.description,
            "name": tool.name,
            "func": _runner,
        }
    )


def registry_to_langchain_tools(registry: ToolRegistry) -> list[BaseTool]:
    return [tool_to_langchain(tool) for tool in registry.all()]


def capability_to_langchain_tool(
    spec: CapabilitySpec,
    *,
    runtime_call: Any,
) -> BaseTool:
    """把 Capability 包装为 LangChain Tool."""

    def _runner(**kwargs: Any) -> Any:
        result = runtime_call(spec.name, kwargs)
        if hasattr(result, "__await__"):
            import asyncio

            result = asyncio.run(result)
        if getattr(result, "ok", True) is False:
            raise RuntimeError(getattr(result, "error", None) or f"{spec.name} 执行失败")
        return getattr(result, "output", result)

    return StructuredTool.from_function(
        func=_runner,
        name=spec.name,
        description=spec.description or spec.name,
        args_schema=None,
    ).model_copy(
        update={
            "args_schema": None,
            "description": spec.description or spec.name,
            "name": spec.name,
            "func": _runner,
        }
    )


def capability_registry_to_langchain_tools(
    registry: CapabilityRegistry,
) -> list[BaseTool]:
    return [
        capability_to_langchain_tool(spec, runtime_call=registry.call)
        for spec in registry.list_enabled()
    ]


def llm_response_to_ai_message(response: LLMResponse) -> AIMessage:
    """把项目内 LLMResponse 转成 LangChain AIMessage."""
    return AIMessage(
        content=response.content or "",
        tool_calls=[
            {
                "id": tc.id,
                "name": tc.name,
                "args": tc.arguments,
                "type": "tool_call",
            }
            for tc in response.tool_calls
        ],
        response_metadata={"finish_reason": response.finish_reason},
    )


class LangChainChatModelAdapter(BaseChatModel):
    """把项目内 BaseLLM 适配为 LangChain BaseChatModel."""

    llm: BaseLLM

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, llm: BaseLLM) -> None:
        super().__init__(llm=llm)

    @property
    def _llm_type(self) -> str:
        return f"course-agent:{self.llm.__class__.__name__.lower()}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        response = self.llm.chat(
            langchain_messages_to_llm(messages),
            tools=kwargs.get("tools"),
            stop=stop,
            **kwargs,
        )
        message = llm_response_to_ai_message(response)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False)


__all__ = [
    "LangChainChatModelAdapter",
    "capability_registry_to_langchain_tools",
    "capability_to_langchain_tool",
    "langchain_message_to_llm",
    "langchain_messages_to_llm",
    "llm_message_to_langchain",
    "llm_messages_to_langchain",
    "llm_response_to_ai_message",
    "registry_to_langchain_tools",
    "tool_to_langchain",
]
