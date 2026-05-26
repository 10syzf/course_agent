"""doctor 第 12 项检查测试（Task 013）."""

from __future__ import annotations

from typer.testing import CliRunner

from course_agent import config as cfgmod
from course_agent.cli import _check_capabilities_and_mcp, app
from course_agent.mcp.config import MCPConfig, MCPServerConfig

runner = CliRunner()


class _Cfg:
    def __init__(self, enabled: bool) -> None:
        self.mcp = MCPConfig(
            enabled=enabled,
            servers=[MCPServerConfig(name="demo", transport="mock")],
        )


def test_check_12_skip_when_mcp_disabled():
    status, detail, hint = _check_capabilities_and_mcp(_Cfg(False))
    assert status == "⚠️"
    assert "skills" in detail
    assert "MCP 未启用" in hint


def test_check_12_ok_when_mcp_enabled():
    status, detail, hint = _check_capabilities_and_mcp(_Cfg(True))
    assert status == "✅"
    assert "mcp=" in detail
    assert "Skill runtime OK" in hint


def test_doctor_command_runs_twelve_checks(monkeypatch):
    cfgmod._config = None
    monkeypatch.setenv("MCP_ENABLED", "true")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
    out = result.stdout
    assert "Skill + MCP" in out or "能力层" in out
    assert "12/" in out or " 12 " in out or "12\n" in out


def test_doctor_command_when_mcp_disabled_still_not_crash(monkeypatch):
    cfgmod._config = None
    monkeypatch.setenv("MCP_ENABLED", "false")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
