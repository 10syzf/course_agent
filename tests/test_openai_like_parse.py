"""OpenAILLM 离线解析测试：Mock openai client 验证解析逻辑."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from course_agent.llm.base import LLMMessage
from course_agent.llm.openai_like import OpenAILLM


def _make_resp(content: str | None, tool_calls: list[dict] | None = None,
               finish_reason: str = "stop"):
    """构造 OpenAI SDK 风格的 ChatCompletion 响应对象."""
    tc_objs = []
    for tc in tool_calls or []:
        tc_objs.append(
            SimpleNamespace(
                id=tc["id"],
                function=SimpleNamespace(
                    name=tc["name"],
                    arguments=tc["arguments"],
                ),
            )
        )
    message = SimpleNamespace(content=content, tool_calls=tc_objs or None)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def test_parse_simple_text():
    resp = _make_resp(content="你好世界", finish_reason="stop")
    out = OpenAILLM._parse_response(resp)
    assert out.content == "你好世界"
    assert out.tool_calls == []
    assert out.finish_reason == "stop"


def test_parse_tool_call():
    resp = _make_resp(
        content=None,
        tool_calls=[
            {
                "id": "call_123",
                "name": "calculator",
                "arguments": '{"expression": "(3+5)*2"}',
            }
        ],
        finish_reason="tool_calls",
    )
    out = OpenAILLM._parse_response(resp)
    assert len(out.tool_calls) == 1
    tc = out.tool_calls[0]
    assert tc.id == "call_123"
    assert tc.name == "calculator"
    assert tc.arguments == {"expression": "(3+5)*2"}
    assert out.finish_reason == "tool_calls"


def test_parse_tool_call_invalid_json():
    """无效 JSON 应降级为空 dict 而不是崩溃."""
    resp = _make_resp(
        content=None,
        tool_calls=[
            {"id": "call_x", "name": "web_search", "arguments": "{not json}"}
        ],
        finish_reason="tool_calls",
    )
    out = OpenAILLM._parse_response(resp)
    assert out.tool_calls[0].arguments == {}


def test_parse_empty_arguments():
    resp = _make_resp(
        content=None,
        tool_calls=[{"id": "call_y", "name": "tool_a", "arguments": ""}],
        finish_reason="tool_calls",
    )
    out = OpenAILLM._parse_response(resp)
    assert out.tool_calls[0].arguments == {}


def test_chat_end_to_end_with_mock_client():
    """端到端：mock client 返回一个工具调用，验证 chat 正常解析."""
    llm = OpenAILLM(model="qwen-plus", api_key="sk-test", base_url="https://example.com")

    mock_resp = _make_resp(
        content=None,
        tool_calls=[
            {
                "id": "c1",
                "name": "calculator",
                "arguments": '{"expression": "1+1"}',
            }
        ],
        finish_reason="tool_calls",
    )
    llm._client = MagicMock()
    llm._client.chat.completions.create = MagicMock(return_value=mock_resp)

    out = llm.chat([LLMMessage(role="user", content="1+1=?")], tools=[])

    assert out.tool_calls[0].name == "calculator"
    assert out.tool_calls[0].arguments == {"expression": "1+1"}
    llm._client.chat.completions.create.assert_called_once()


def test_chat_without_api_key_raises():
    llm = OpenAILLM(model="qwen-plus", api_key=None, base_url="https://example.com")
    with pytest.raises(ValueError, match="api_key"):
        llm._get_client()


def test_handle_error_wraps_exception():
    err = RuntimeError("something broken")
    out = OpenAILLM._handle_error(err)
    assert out.finish_reason == "error"
    assert "LLM 调用失败" in (out.content or "")
