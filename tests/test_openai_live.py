"""OpenAILLM 在线集成测试：仅在 RUN_LIVE_LLM=1 时运行.

使用方式:
    RUN_LIVE_LLM=1 uv run pytest tests/test_openai_live.py -v -s

依赖 .env 中的 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL。
"""

from __future__ import annotations

import os

import pytest

from course_agent.config import load_config
from course_agent.core import AgentLoop
from course_agent.llm import create_llm
from course_agent.llm.base import LLMMessage

LIVE = os.getenv("RUN_LIVE_LLM") == "1"
pytestmark = pytest.mark.skipif(
    not LIVE, reason="需要真实 LLM Key，通过 RUN_LIVE_LLM=1 启用"
)


@pytest.fixture(scope="module")
def live_llm():
    cfg = load_config()
    if cfg.llm.provider != "openai":
        cfg.llm.provider = "openai"
    assert cfg.llm.api_key, "请在 .env 中配置 OPENAI_API_KEY"
    return create_llm(cfg.llm)


def test_live_simple_chat(live_llm):
    resp = live_llm.chat([LLMMessage(role="user", content="回复“pong”，不要多说")])
    assert resp.finish_reason != "error"
    assert resp.content


def test_live_agent_loop_calculator(live_llm):
    loop = AgentLoop(llm=live_llm, max_steps=5)
    result = loop.run("帮我用计算工具算一下 (12+8)*5 等于多少，用工具算")
    trace_kinds = [t["kind"] for t in result.trace]
    assert "tool_call" in trace_kinds
    assert "100" in result.answer


def test_live_agent_loop_direct_answer(live_llm):
    loop = AgentLoop(llm=live_llm, max_steps=3)
    result = loop.run("用一句话简要介绍牛顿第二定律")
    assert result.answer
    assert result.steps <= 3
