"""python_exec extra_packages 白名单测试（Task 009）.

注意：避免在 CI 中真实 pip install（耗时长 + 占网络），用 monkeypatch 拦截。
"""

from __future__ import annotations

import json

from course_agent.tools import python_exec as pe_mod
from course_agent.tools.python_exec import (
    _ALLOWED_PACKAGES,
    _ensure_packages,
    python_exec,
)


def _run(code: str, **kw) -> dict:
    return json.loads(python_exec(code=code, **kw))


def test_no_extra_packages_keeps_task008_behavior():
    """不传 extra_packages 时与 Task 008 一致：-I -S 隔离."""
    out = _run("print('still hello')")
    assert out["exit_code"] == 0
    assert "still hello" in out["stdout"]


def test_extra_packages_must_be_list():
    raw = python_exec(code="print(1)", extra_packages="numpy")  # 故意传 str
    out = json.loads(raw)
    assert "error" in out
    assert "字符串列表" in out["error"]


def test_extra_packages_rejects_non_whitelisted():
    """非白名单的包必须直接被拒绝，禁止任意 pip install."""
    raw = python_exec(code="print(1)", extra_packages=["pyyaml", "evil-pkg"])
    out = json.loads(raw)
    assert "error" in out
    assert "白名单" in out["error"]
    # 必须列出非法的具体包名，方便排查
    assert "pyyaml" in out["error"] or "evil-pkg" in out["error"]


def test_ensure_packages_empty_returns_none():
    pythonpath, err = _ensure_packages([])
    assert pythonpath is None
    assert err is None


def test_ensure_packages_unit_rejects_non_whitelist():
    pythonpath, err = _ensure_packages(["evil"])
    assert pythonpath is None
    assert err is not None
    assert "白名单" in err


def test_extra_packages_passes_pythonpath_to_runner(monkeypatch):
    """白名单 + mock pip install + mock _run_code_sync：验证 PYTHONPATH 真的被传进去了."""
    # 拦 _ensure_packages 直接给假目录，跳过真实 pip install
    monkeypatch.setattr(
        pe_mod, "_ensure_packages", lambda pkgs: ("/fake/cache/dir", None)
    )

    captured: dict = {}

    def fake_run(code, stdin, timeout, extra_pythonpath=None):
        captured["code"] = code
        captured["pythonpath"] = extra_pythonpath
        return {
            "exit_code": 0,
            "stdout": "OK",
            "stderr": "",
            "duration_ms": 1,
            "truncated": False,
            "timed_out": False,
        }

    monkeypatch.setattr(pe_mod, "_run_code_sync", fake_run)

    raw = python_exec(code="print('hi')", extra_packages=["numpy"])
    out = json.loads(raw)
    assert out["exit_code"] == 0
    assert captured["pythonpath"] == "/fake/cache/dir"


def test_extra_packages_install_failure_propagates(monkeypatch):
    """pip install 失败 → 工具应返回带 error 的 JSON，而非崩溃."""
    monkeypatch.setattr(
        pe_mod, "_ensure_packages", lambda pkgs: (None, "网络挂了")
    )
    raw = python_exec(code="print('hi')", extra_packages=["numpy"])
    out = json.loads(raw)
    assert "error" in out
    assert "网络挂了" in out["error"]


def test_whitelist_constant_sanity():
    """白名单契约：6 个核心数据科学/数学/网络包."""
    assert _ALLOWED_PACKAGES == {
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        "sympy",
        "requests",
    }
