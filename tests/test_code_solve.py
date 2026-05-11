"""code_solve 自批改闭环测试：mock LLM 验证多轮收敛 / 失败 / 边界."""

from __future__ import annotations

import json

import pytest

from course_agent.tools import code_solve as cs_mod
from course_agent.tools.code_solve import code_solve


class _ScriptedLLM:
    """脚本化 LLM：按调用次序返回预设回复，方便测试多轮."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[list] = []

    def chat(self, messages, tools=None):  # noqa: ARG002
        self.calls.append(messages)
        if not self._replies:
            raise RuntimeError("脚本回复用完了")
        text = self._replies.pop(0)

        class _Resp:
            content = text
            finish_reason = "stop"
            tool_calls: list = []

        return _Resp()


@pytest.fixture
def patch_llm(monkeypatch):
    """注入脚本化 LLM 替换 get_default_llm."""

    def _patch(replies: list[str]) -> _ScriptedLLM:
        scripted = _ScriptedLLM(replies)

        # code_solve 内部用 from course_agent.llm.factory import get_default_llm
        from course_agent.llm import factory as factory_mod

        monkeypatch.setattr(factory_mod, "get_default_llm", lambda: scripted)
        return scripted

    return _patch


def test_code_solve_empty_task_returns_error():
    raw = code_solve(task="")
    out = json.loads(raw)
    assert out["success"] is False
    assert out["rounds"] == 0
    assert "为空" in out["last_error"]


def test_code_solve_first_round_pass(patch_llm):
    """第 1 轮 LLM 就给出正确代码 → 立刻通过."""
    code_block = "```python\ndef add(a, b):\n    return a + b\n```"
    scripted = patch_llm([code_block])

    raw = code_solve(
        task="写一个加法函数 add(a,b)",
        tests="assert add(1, 2) == 3\nassert add(-1, 1) == 0",
        max_rounds=3,
    )
    out = json.loads(raw)
    assert out["success"] is True
    assert out["rounds"] == 1
    assert "def add" in out["code"]
    assert "auto tests" in out["code"]  # 测试代码已自动追加
    assert len(out["attempts"]) == 1
    assert out["attempts"][0]["exit_code"] == 0
    assert len(scripted.calls) == 1  # 没浪费第二次调用


def test_code_solve_self_critique_recovers(patch_llm):
    """第 1 轮故意写错 → 第 2 轮根据 stderr 改对."""
    bad = "```python\ndef add(a, b):\n    return a - b  # bug\n```"
    good = "```python\ndef add(a, b):\n    return a + b\n```"
    scripted = patch_llm([bad, good])

    raw = code_solve(
        task="写一个加法函数 add(a,b)",
        tests="assert add(1, 2) == 3",
        max_rounds=3,
    )
    out = json.loads(raw)
    assert out["success"] is True
    assert out["rounds"] == 2
    assert len(out["attempts"]) == 2
    assert out["attempts"][0]["exit_code"] != 0  # 第 1 轮失败
    assert out["attempts"][1]["exit_code"] == 0  # 第 2 轮成功
    # 第 2 轮的 user message 应该带上 stderr feedback
    second_user = scripted.calls[1][-1].content
    assert "stderr" in second_user


def test_code_solve_exhausts_rounds_and_fails(patch_llm):
    """连续 3 轮都给错的代码 → 应返回 success=False + rounds==3."""
    bad = "```python\nraise ValueError('always fails')\n```"
    patch_llm([bad, bad, bad])

    raw = code_solve(task="写一个永远失败的代码", tests="", max_rounds=3)
    out = json.loads(raw)
    assert out["success"] is False
    assert out["rounds"] == 3
    assert len(out["attempts"]) == 3
    assert all(a["exit_code"] != 0 for a in out["attempts"])
    assert "已尝试 3 轮" in out["last_error"]


def test_code_solve_max_rounds_capped_at_5(patch_llm):
    """max_rounds=99 应被压到硬上限 5."""
    bad = "```python\nraise ValueError('x')\n```"
    patch_llm([bad] * 10)

    raw = code_solve(task="任意", tests="", max_rounds=99)
    out = json.loads(raw)
    assert out["rounds"] == 5  # _HARD_MAX_ROUNDS


def test_code_solve_extracts_code_without_fence(patch_llm):
    """LLM 没用三引号包裹 → 兜底把整段当代码."""
    raw_code = "print('no fence but still works')"
    patch_llm([raw_code])

    raw = code_solve(task="打印一行字", tests="", max_rounds=1)
    out = json.loads(raw)
    assert out["success"] is True
    assert "no fence" in out["code"]


def test_code_solve_llm_init_failure(monkeypatch):
    """get_default_llm 抛异常 → 友好降级."""
    from course_agent.llm import factory as factory_mod

    def boom():
        raise RuntimeError("missing OPENAI_API_KEY")

    monkeypatch.setattr(factory_mod, "get_default_llm", boom)

    raw = code_solve(task="任意", tests="")
    out = json.loads(raw)
    assert out["success"] is False
    assert "初始化 LLM 失败" in out["last_error"]


def test_code_solve_constants_sanity():
    """硬上限 5、默认 3、stderr 截断 1KB——这些是契约，不能被偶然改坏."""
    assert cs_mod._HARD_MAX_ROUNDS == 5
    assert cs_mod._DEFAULT_MAX_ROUNDS == 3
    assert cs_mod._STDERR_FEEDBACK_LIMIT == 1024
