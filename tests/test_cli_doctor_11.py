"""doctor 第 11 项检查测试（Task 012）.

覆盖：
- mock provider / 无 key → ⚠️ 但不崩；4 agents 实例化成功 + metrics.db 创建
- 真 LLM provider 但 hello roundtrip 抛异常 → ⚠️
- doctor 命令整体 11 项一次跑完不崩
- metrics.db 不存在时自动创建
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from course_agent.cli import _check_multi_agent, app
from course_agent.config import LLMConfig

runner = CliRunner()


class _Cfg:
    def __init__(self, llm_cfg: LLMConfig) -> None:
        self.llm = llm_cfg


def _mock_cfg() -> _Cfg:
    return _Cfg(LLMConfig(provider="mock", model="mock-llm", api_key=None))


def _openai_cfg(api_key: str | None = "sk-test-fake") -> _Cfg:
    return _Cfg(LLMConfig(provider="openai", model="gpt-4o-mini", api_key=api_key))


@pytest.fixture
def isolated_metrics_db(monkeypatch, tmp_path):
    db_path = tmp_path / "metrics.db"
    monkeypatch.setenv("COURSE_AGENT_METRICS_DB", str(db_path))
    return db_path


def test_check_11_mock_provider_returns_warn_with_db_created(isolated_metrics_db):
    status, detail, hint = _check_multi_agent(_mock_cfg())
    assert status == "⚠️"
    assert "跳过" in detail or "skip" in detail.lower()
    assert isolated_metrics_db.exists()
    assert "agents" in hint.lower() or "agent" in hint.lower()


def test_check_11_no_api_key_returns_warn(isolated_metrics_db):
    status, _detail, _hint = _check_multi_agent(_openai_cfg(api_key=None))
    assert status == "⚠️"


def test_check_11_orchestrator_arun_raises_returns_warn(isolated_metrics_db):
    with patch(
        "course_agent.cli.create_llm",
        side_effect=RuntimeError("network down"),
    ):
        status, detail, _hint = _check_multi_agent(_openai_cfg())
    assert status == "⚠️"
    assert "RuntimeError" in detail or "network" in detail.lower()


def test_doctor_command_still_includes_original_eleventh_check(isolated_metrics_db):
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
    out = result.stdout
    assert "多 Agent" in out or "Orchestrator" in out
    # Task 013 后总项数升到 12，但原第 11 项内容仍必须存在
    assert "11/12" in out or "12/12" in out or " 11 " in out or "12/" in out
