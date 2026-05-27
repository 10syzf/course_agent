"""Task 017：Prompt profiling."""

from __future__ import annotations

from course_agent.prompt.models import PromptEnvelope


def profile_prompt(envelope: PromptEnvelope) -> dict[str, float | int | str]:
    """返回静态 / 动态 prompt 的轻量统计."""
    static_chars = len(envelope.static_prefix)
    dynamic_chars = len(envelope.dynamic_tail)
    full_chars = len(envelope.full_prompt)
    if full_chars == 0:
        static_ratio = 0.0
        dynamic_ratio = 0.0
    else:
        static_ratio = round(static_chars / full_chars, 4)
        dynamic_ratio = round(dynamic_chars / full_chars, 4)
    return {
        "role": envelope.role,
        "static_chars": static_chars,
        "dynamic_chars": dynamic_chars,
        "full_chars": full_chars,
        "static_ratio": static_ratio,
        "dynamic_ratio": dynamic_ratio,
    }


__all__ = ["profile_prompt"]
