"""Task 014：LangChain Adapter Layer 测试."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from course_agent.capabilities.base import CapabilityCallResult, CapabilityKind, CapabilitySpec
from course_agent.capabilities.registry import CapabilityRegistry
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse, ToolCall
from course_agent.runtime.langchain_adapters import (
    LangChainChatModelAdapter,
    capability_registry_to_langchain_tools,
    capability_to_langchain_tool,
    langchain_message_to_llm,
    llm_message_to_langchain,
    llm_messages_to_langchain,
    llm_response_to_ai_message,
    registry_to_langchain_tools,
    tool_to_langchain,
)
from course_agent.tools.registry import Tool, ToolRegistry


class _EchoLLM(BaseLLM):
    def __init__(self) -> None:
        super().__init__(model="echo")
        self.calls: list[list[LLMMessage]] = []

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.calls.append(messages)
        return LLMResponse(content="hello from adapter", finish_reason="stop")


class _Provider:
    provider_name = "demo"

    def list_capabilities(self) -> list[CapabilitySpec]:
        return [
            CapabilitySpec(
                name="demo_cap",
                kind=CapabilityKind.SKILL,
                description="demo",
                parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
            )
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> CapabilityCallResult:
        return CapabilityCallResult(
            capability_name=name,
            kind=CapabilityKind.SKILL,
            ok=True,
            output=f"cap:{arguments['x']}",
        )


def test_llm_message_to_langchain_for_all_roles():
    assert isinstance(llm_message_to_langchain(LLMMessage(role="system", content="s")), SystemMessage)
    assert isinstance(llm_message_to_langchain(LLMMessage(role="user", content="u")), HumanMessage)
    assert isinstance(
        llm_message_to_langchain(
            LLMMessage(role="tool", content="t", tool_call_id="call-1")
        ),
        ToolMessage,
    )
    assert isinstance(llm_message_to_langchain(LLMMessage(role="assistant", content="a")), AIMessage)


def test_langchain_message_to_llm_roundtrip_for_tool_message():
    message = ToolMessage(content="tool out", tool_call_id="call-1")
    llm_msg = langchain_message_to_llm(message)
    assert llm_msg.role == "tool"
    assert llm_msg.tool_call_id == "call-1"
    assert llm_msg.content == "tool out"


def test_llm_messages_to_langchain_preserves_order():
    msgs = [LLMMessage(role="system", content="s"), LLMMessage(role="user", content="u")]
    out = llm_messages_to_langchain(msgs)
    assert [type(m).__name__ for m in out] == ["SystemMessage", "HumanMessage"]


def test_llm_response_to_ai_message_keeps_tool_calls():
    msg = llm_response_to_ai_message(
        LLMResponse(
            content="done",
            tool_calls=[ToolCall(id="1", name="calculator", arguments={"x": 1})],
            finish_reason="tool_calls",
        )
    )
    assert msg.content == "done"
    assert msg.tool_calls[0]["name"] == "calculator"


def test_tool_to_langchain_runs_original_tool():
    tool = Tool(
        name="echo_tool",
        description="echo",
        parameters={"type": "object", "properties": {}},
        func=lambda: "ok",
    )
    lc_tool = tool_to_langchain(tool)
    assert lc_tool.name == "echo_tool"
    assert lc_tool.invoke({}) == "ok"


def test_registry_to_langchain_tools_exports_all_tools():
    registry = ToolRegistry()
    registry.register(
        Tool(name="a", description="A", parameters={"type": "object", "properties": {}}, func=lambda: "A")
    )
    registry.register(
        Tool(name="b", description="B", parameters={"type": "object", "properties": {}}, func=lambda: "B")
    )
    tools = registry_to_langchain_tools(registry)
    assert {tool.name for tool in tools} == {"a", "b"}


def test_capability_to_langchain_tool_invokes_runtime_call():
    spec = CapabilitySpec(
        name="demo_cap",
        kind=CapabilityKind.SKILL,
        description="demo",
        parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
    )

    async def _call(name: str, arguments: dict[str, Any]) -> CapabilityCallResult:
        return CapabilityCallResult(
            capability_name=name,
            kind=CapabilityKind.SKILL,
            ok=True,
            output=f"cap:{arguments['x']}",
        )

    tool = capability_to_langchain_tool(spec, runtime_call=_call)
    assert tool.invoke({"x": 3}) == "cap:3"


def test_capability_registry_to_langchain_tools_exports_enabled_caps():
    registry = CapabilityRegistry()
    registry.register_provider(_Provider())
    tools = capability_registry_to_langchain_tools(registry)
    assert len(tools) == 1
    assert tools[0].name == "demo_cap"


def test_langchain_chat_model_adapter_invokes_base_llm():
    llm = _EchoLLM()
    adapter = LangChainChatModelAdapter(llm)
    result = adapter.invoke([HumanMessage(content="hello")])
    assert result.content == "hello from adapter"
    assert llm.calls[0][0].role == "user"
