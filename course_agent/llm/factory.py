"""LLM 工厂：按配置创建具体实例."""

from __future__ import annotations

from course_agent.config import LLMConfig, get_config
from course_agent.llm.base import BaseLLM


def create_llm(cfg: LLMConfig | None = None) -> BaseLLM:
    """根据配置创建 LLM 实例."""
    if cfg is None:
        cfg = get_config().llm

    provider = (cfg.provider or "mock").lower()

    if provider == "mock":
        from course_agent.llm.mock import MockLLM

        return MockLLM(model=cfg.model)

    if provider == "openai":
        from course_agent.llm.openai_like import OpenAILLM

        return OpenAILLM(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    raise ValueError(f"未知的 LLM provider: {provider}")
