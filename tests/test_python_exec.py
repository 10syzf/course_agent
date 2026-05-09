"""python_exec 沙箱测试：覆盖正常 / 超时 / 内存 / 禁网 / 截断 / 黑名单."""

from __future__ import annotations

import json
import sys

import pytest

from course_agent.tools import python_exec as pe_mod
from course_agent.tools.python_exec import python_exec


def _run(code: str, stdin: str = "", timeout: int = 5) -> dict:
    raw = python_exec(code=code, stdin=stdin, timeout=timeout)
    return json.loads(raw)


def test_normal_print_hello():
    out = _run("print('hello sandbox')")
    assert out["exit_code"] == 0
    assert "hello sandbox" in out["stdout"]
    assert out["timed_out"] is False
    assert out["truncated"] is False


def test_stdin_passthrough():
    out = _run("import sys; print(sys.stdin.read().upper())", stdin="abc")
    assert out["exit_code"] == 0
    assert "ABC" in out["stdout"]


def test_timeout_kills_infinite_loop():
    out = _run("while True: pass", timeout=2)
    assert out["timed_out"] is True
    assert out["exit_code"] != 0
    assert "TIMEOUT" in out["stderr"]
    assert out["duration_ms"] >= 1000


def test_blacklist_subprocess_import_rejected():
    raw = python_exec(code="import subprocess; subprocess.run(['ls'])")
    out = json.loads(raw)
    assert "error" in out
    assert "subprocess" in out["error"]


def test_blacklist_socket_rejected():
    raw = python_exec(code="import socket")
    out = json.loads(raw)
    assert "error" in out
    assert "socket" in out["error"]


def test_blacklist_os_system_rejected():
    raw = python_exec(code="import os\nos.system('ls')")
    out = json.loads(raw)
    assert "error" in out
    assert "os.system" in out["error"]


def test_stdout_truncation_when_huge_output():
    code = "print('x' * 100000)"
    out = _run(code, timeout=10)
    assert out["truncated"] is True
    assert "[truncated]" in out["stdout"]
    assert len(out["stdout"]) < 16 * 1024


def test_code_too_long_rejected():
    big = "a = 1\n" * 5000  # > 16KB
    raw = python_exec(code=big)
    out = json.loads(raw)
    assert "error" in out
    assert "16384" in out["error"] or "上限" in out["error"]


def test_empty_code_rejected():
    raw = python_exec(code="")
    out = json.loads(raw)
    assert "error" in out


def test_invalid_timeout_rejected():
    raw = python_exec(code="print(1)", timeout=999)
    out = json.loads(raw)
    assert "error" in out


def test_syntax_error_caught_in_audit():
    raw = python_exec(code="def broken(:")
    out = json.loads(raw)
    assert "error" in out


def test_clean_env_strips_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-leak-12345")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-secret")
    out = _run(
        "import os\n"
        "print('OPENAI=', os.environ.get('OPENAI_API_KEY'))\n"
        "print('TAVILY=', os.environ.get('TAVILY_API_KEY'))"
    )
    assert out["exit_code"] == 0
    assert "sk-should-not-leak-12345" not in out["stdout"]
    assert "tvly-secret" not in out["stdout"]
    assert "OPENAI= None" in out["stdout"]


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="RLIMIT_AS 在 macOS / Windows 上行为不一致，仅在 Linux 上做硬性内存上限验证",
)
def test_memory_limit_blocks_huge_alloc():
    out = _run("a = 'x' * (512 * 1024 * 1024)", timeout=10)
    # 256MB rlimit 下分配 512MB 应该会失败 → 非 0 退出 + stderr 有 MemoryError
    assert out["exit_code"] != 0
    assert "MemoryError" in out["stderr"] or "Cannot" in out["stderr"]


def test_audit_unit():
    """直接测试 _audit 内部函数."""
    assert pe_mod._audit("print(1)") is None
    assert "subprocess" in (pe_mod._audit("import subprocess") or "")
    assert "from-import" in (pe_mod._audit("from socket import socket") or "")
    assert "os.popen" in (pe_mod._audit("import os; os.popen('ls')") or "")
