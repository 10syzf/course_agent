"""Task 017：prompt profiling 测试."""

from __future__ import annotations

from course_agent.prompt.compiler import compile_prompt
from course_agent.prompt.profiling import profile_prompt


def test_profile_prompt_returns_expected_keys():
    row = profile_prompt(
        compile_prompt(role="react", role_prompt="你是助手。", user_input="你好")
    )
    assert set(row) >= {
        "role",
        "static_chars",
        "dynamic_chars",
        "full_chars",
        "static_ratio",
        "dynamic_ratio",
    }


def test_profile_prompt_ratios_sum_close_to_one():
    row = profile_prompt(
        compile_prompt(role="react", role_prompt="你是助手。", user_input="你好")
    )
    assert abs((row["static_ratio"] + row["dynamic_ratio"]) - 1.0) < 0.01


def test_profile_prompt_handles_empty_prompt():
    row = profile_prompt(
        compile_prompt(role="react", role_prompt="", user_input="")
    )
    assert row["full_chars"] >= 0
