"""doctor CLI 测试：mock 失败场景验证 7 项检查输出."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from course_agent.cli import (
    _check_api_key,
    _check_deps,
    _check_env_file,
    _check_python_version,
    _check_tools,
    app,
)

runner = CliRunner()


def test_doctor_command_runs_without_crash():
    """doctor 命令必须能跑完所有 7 项，不抛未捕获异常."""
    result = runner.invoke(app, ["doctor"])
    # 退出码 0（全过）或 1（有失败）都接受；关键是必须有输出且不崩溃
    assert result.exit_code in (0, 1)
    out = result.stdout
    assert "Course Agent 健康检查" in out
    assert "Python 版本" in out
    assert "工具注册" in out


def test_check_python_version_unit():
    status, ver, hint = _check_python_version()
    assert status in ("✅", "⚠️", "❌")
    assert "." in ver  # 看起来像版本号


def test_check_deps_unit():
    status, detail, hint = _check_deps()
    # 当前环境一定都装了 → 必须 ✅
    assert status == "✅"


def test_check_env_file_when_missing(monkeypatch, tmp_path):
    """伪装 .env 不存在 → 应返回 ⚠️ 而不是 ❌."""
    fake_root = tmp_path / "fake_pkg"
    fake_root.mkdir()
    # _check_env_file 用的是 cli.py 文件路径推 root，无法直接 monkeypatch；
    # 改测它内部行为：直接测一个不存在的目录场景
    from pathlib import Path

    with patch.object(Path, "exists", return_value=False):
        status, detail, hint = _check_env_file()
    assert status == "⚠️"
    assert ".env.example" in hint


def test_check_api_key_missing():
    cfg = type("C", (), {"llm": type("L", (), {"api_key": None})()})()
    status, detail, hint = _check_api_key(cfg)
    assert status == "❌"
    assert "未配置" in detail


def test_check_api_key_present():
    cfg = type("C", (), {"llm": type("L", (), {"api_key": "sk-abc123def456ghi"})()})()
    status, detail, hint = _check_api_key(cfg)
    assert status == "✅"
    assert "..." in detail
    assert "len=" in detail


def test_check_api_key_warns_when_os_env_differs(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-different-key-from-env")
    cfg = type("C", (), {"llm": type("L", (), {"api_key": "sk-abc123def456ghi"})()})()
    status, detail, hint = _check_api_key(cfg)
    assert status == "✅"
    assert "shell" in hint
    assert "override" in hint


def test_check_tools_unit():
    status, count, names = _check_tools()
    assert status == "✅"
    # Task 008 后至少 9 个工具
    assert "python_exec" in names
    assert "pdf_read" in names
