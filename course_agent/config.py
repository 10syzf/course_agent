"""配置加载模块：yaml 默认值 + 环境变量覆盖."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    provider: str = "mock"
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 1024
    api_key: str | None = None
    base_url: str | None = None


class AgentConfig(BaseModel):
    max_steps: int = 8
    timeout_seconds: int = 120


class LoggingConfig(BaseModel):
    level: str = "INFO"


class AppConfig(BaseSettings):
    """全局配置对象，支持 .env 覆盖."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(yaml_path: str | Path | None = None) -> AppConfig:
    """加载配置：yaml 默认值 + .env 文件 + 环境变量覆盖."""
    root = Path(__file__).resolve().parent.parent
    yaml_path = Path(yaml_path) if yaml_path else root / "config" / "default.yaml"
    data = _load_yaml(yaml_path)

    import os

    env_file = root / ".env"
    if env_file.exists():
        # ⚠️ override=True：.env 永远赢过 OS 环境变量
        # 否则如果用户 shell 里残留旧 OPENAI_API_KEY（比如之前 export 过一个错的），
        # 会污染所有子进程导致认证失败而 .env 完全无效。
        # 详见 task_007 实战教训：曾出现 .env key 正确、curl 200，但 chainlit 进程 401 的诡异现象。
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=True)
        except ImportError:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

    llm_data = data.get("llm", {})
    if os.getenv("LLM_PROVIDER"):
        llm_data["provider"] = os.getenv("LLM_PROVIDER")
    if os.getenv("OPENAI_API_KEY"):
        llm_data["api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("OPENAI_BASE_URL"):
        llm_data["base_url"] = os.getenv("OPENAI_BASE_URL")
    if os.getenv("OPENAI_MODEL"):
        llm_data["model"] = os.getenv("OPENAI_MODEL")

    agent_data = data.get("agent", {})
    if os.getenv("AGENT_MAX_STEPS"):
        agent_data["max_steps"] = int(os.getenv("AGENT_MAX_STEPS"))

    logging_data = data.get("logging", {})
    if os.getenv("AGENT_LOG_LEVEL"):
        logging_data["level"] = os.getenv("AGENT_LOG_LEVEL")

    return AppConfig(
        llm=LLMConfig(**llm_data),
        agent=AgentConfig(**agent_data),
        logging=LoggingConfig(**logging_data),
    )


_config: AppConfig | None = None


def get_config() -> AppConfig:
    """懒加载全局配置单例."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
