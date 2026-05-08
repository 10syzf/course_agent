"""测试配置加载."""

from __future__ import annotations

from course_agent.config import load_config


def test_load_default_config():
    cfg = load_config()
    assert cfg.llm.provider in {"mock", "openai"}
    assert cfg.agent.max_steps >= 1
    assert cfg.logging.level in {"DEBUG", "INFO", "WARNING", "ERROR"}
