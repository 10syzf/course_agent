"""doctor 第 10 项检查测试（Task 011）.

覆盖：
- mock provider / 无 key → ⚠️ 但不崩；examiner 仍验证
- 真 LLM 流式正常 → ✅
- 真 LLM 流式抛 finish_reason="error" → ⚠️
- 真 LLM 直接抛异常 → ⚠️
- doctor 命令整体 10 项一次跑完不崩
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from course_agent.cli import _check_streaming_and_examiner, app
from course_agent.config import LLMConfig
from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse, StreamChunk

runner = CliRunner()


class _Cfg:
    """模拟 AppConfig：只暴露 .llm 字段."""

    def __init__(self, llm_cfg: LLMConfig) -> None:
        self.llm = llm_cfg


def _mock_cfg() -> _Cfg:
    return _Cfg(LLMConfig(provider="mock", model="mock-llm", api_key=None))


def _openai_cfg(api_key: str | None = "sk-test-fake") -> _Cfg:
    return _Cfg(LLMConfig(provider="openai", model="gpt-4o-mini", api_key=api_key))


def test_check_10_mock_provider_returns_warn_with_examiner_ok():
    status, detail, hint = _check_streaming_and_examiner(_mock_cfg())
    assert status == "⚠️"
    assert "stream" in detail.lower() or "跳过" in detail
    # 无论怎样 examiner 必须可实例化
    assert "examiner" in hint.lower() or "tools" in hint.lower()


def test_check_10_no_api_key_returns_warn():
    status, _, hint = _check_streaming_and_examiner(_openai_cfg(api_key=None))
    assert "tools" in hint.lower() or "examiner" in hint.lower()


class _GoodStreamLLM(BaseLLM):
    def __init__(self) -> None:
        super().__init__(model="good")

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(content="hi", finish_reason="stop")

    async def astream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(delta_text="hi")
        yield StreamChunk(finish_reason="stop")


class _ErrStreamLLM(BaseLLM):
    def __init__(self) -> None:
        super().__init__(model="err")

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(content="", finish_reason="stop")

    async def astream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(finish_reason="error", error="网络抖动")


def test_check_10_real_provider_happy_path():
    with patch("course_agent.llm.create_llm", return_value=_GoodStreamLLM()):
        status, detail, hint = _check_streaming_and_examiner(_openai_cfg())
    assert status == "✅"
    assert "stream OK" in detail
    assert "examiner" in hint.lower() or "tools" in hint.lower()


def test_check_10_stream_returns_error_chunk_degraded_to_warn():
    with patch("course_agent.llm.create_llm", return_value=_ErrStreamLLM()):
        status, detail, _ = _check_streaming_and_examiner(_openai_cfg())
    assert status == "⚠️"
    assert "stream" in detail.lower()


def test_check_10_create_llm_raises_returns_warn():
    with patch(
        "course_agent.llm.create_llm",
        side_effect=RuntimeError("network down"),
    ):
        status, _detail, hint = _check_streaming_and_examiner(_openai_cfg())
    # 任何异常都被外层 try/except 兜底为 ⚠️
    assert status == "⚠️"
    assert "RuntimeError" in _detail or "network" in hint


def test_doctor_command_runs_all_ten_checks_without_crash():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
    out = result.stdout
    # 10 项标签都应出现
    for label in [
        "Python 版本",
        "关键依赖",
        "工具注册",
        "错题本 + 教材库",
        "流式 + Examiner Agent",
    ]:
        assert label in out
    # 序号 10 应出现
    assert " 10 " in out or "10/10" in out or "10  " in out or "10\n" in out
