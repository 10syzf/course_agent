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


# 进程级 LLM 单例（Task 009 引入，给 code_solve 这种「工具内部需要调 LLM」的场景用）
_default_llm: BaseLLM | None = None


def get_default_llm() -> BaseLLM:
    """返回进程级默认 LLM 单例（首次调用时按当前 .env 配置创建并缓存）.

    使用场景：code_solve / 其它「在工具内部调 LLM 写代码 / 写答案」的元工具。
    注意：不要用它替换 AgentLoop 的注入式 llm（那个仍由调用方控制）。
    """
    global _default_llm
    if _default_llm is None:
        _default_llm = create_llm()
    return _default_llm


def reset_default_llm() -> None:
    """重置默认 LLM 单例（仅测试用：换 mock 或换配置后调用）."""
    global _default_llm
    _default_llm = None
