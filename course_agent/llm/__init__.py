"""LLM 适配层：提供统一的 Chat 接口抽象."""

from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse, ToolCall
from course_agent.llm.factory import create_llm, get_default_llm, reset_default_llm
from course_agent.llm.mock import MockLLM

__all__ = [
    "BaseLLM",
    "LLMMessage",
    "LLMResponse",
    "ToolCall",
    "MockLLM",
    "create_llm",
    "get_default_llm",
    "reset_default_llm",
]
