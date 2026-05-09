"""OpenAI 兼容 LLM 真实实现.

通过 `openai` SDK + 自定义 `base_url` 兼容：
- OpenAI 官方
- 阿里云百炼 (DashScope) compatible-mode
- DeepSeek / 豆包(Ark) / Qwen / 智谱 等
"""

from __future__ import annotations

import json
import time
from typing import Any

from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse, ToolCall
from course_agent.logger import get_logger

_log = get_logger("OpenAILLM")


class OpenAILLM(BaseLLM):
    """基于 openai SDK 的真实实现，支持 tool-calling."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        max_retries: int = 2,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, **kwargs)
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self._client: Any = None
        self._async_client: Any = None

    def _get_client(self) -> Any:
        """懒加载 OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise RuntimeError(
                    "未安装 openai SDK，请执行: uv add openai 或 pip install openai"
                ) from e

            if not self.api_key:
                raise ValueError(
                    "未配置 api_key，请在 .env 或环境变量中设置 OPENAI_API_KEY"
                )

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=60.0,
            )
        return self._client

    def _get_async_client(self) -> Any:
        """懒加载异步 OpenAI client."""
        if self._async_client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as e:
                raise RuntimeError(
                    "未安装 openai SDK，请执行: uv add openai"
                ) from e

            if not self.api_key:
                raise ValueError(
                    "未配置 api_key，请在 .env 或环境变量中设置 OPENAI_API_KEY"
                )

            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=60.0,
            )
        return self._async_client

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """发起一次 chat 请求并解析结果."""
        client = self._get_client()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_openai() for m in messages],
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        try:
            resp = self._with_retry(lambda: client.chat.completions.create(**payload))
        except Exception as e:
            return self._handle_error(e)

        return self._parse_response(resp)

    async def achat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """异步版本：使用 AsyncOpenAI，避免在事件循环中阻塞."""
        client = self._get_async_client()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_openai() for m in messages],
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        try:
            resp = await self._awith_retry(client, payload)
        except Exception as e:
            return self._handle_error(e)

        return self._parse_response(resp)

    async def _awith_retry(self, client: Any, payload: dict[str, Any]) -> Any:
        """异步版本的重试逻辑."""
        import asyncio

        try:
            from openai import APITimeoutError, RateLimitError
        except ImportError:
            return await client.chat.completions.create(**payload)

        last_exc: Exception | None = None
        delays = [1.0, 3.0]
        attempts = self.max_retries + 1
        for i in range(attempts):
            try:
                return await client.chat.completions.create(**payload)
            except RateLimitError as e:
                last_exc = e
                if i < attempts - 1:
                    wait = delays[min(i, len(delays) - 1)]
                    _log.warning(f"限流(429)，{wait}s 后重试 ({i + 1}/{attempts - 1})")
                    await asyncio.sleep(wait)
                    continue
                raise
            except APITimeoutError as e:
                last_exc = e
                if i < attempts - 1:
                    _log.warning(f"请求超时，重试 ({i + 1}/{attempts - 1})")
                    await asyncio.sleep(1.0)
                    continue
                raise
        if last_exc:
            raise last_exc

    def _with_retry(self, fn: Any) -> Any:
        """指数退避重试：仅对限流/超时做重试."""
        try:
            from openai import APITimeoutError, RateLimitError
        except ImportError:
            return fn()

        last_exc: Exception | None = None
        delays = [1.0, 3.0]
        attempts = self.max_retries + 1
        for i in range(attempts):
            try:
                return fn()
            except RateLimitError as e:
                last_exc = e
                if i < attempts - 1:
                    wait = delays[min(i, len(delays) - 1)]
                    _log.warning(f"限流(429)，{wait}s 后重试 ({i + 1}/{attempts - 1})")
                    time.sleep(wait)
                    continue
                raise
            except APITimeoutError as e:
                last_exc = e
                if i < attempts - 1:
                    _log.warning(f"请求超时，重试 ({i + 1}/{attempts - 1})")
                    time.sleep(1.0)
                    continue
                raise
        if last_exc:
            raise last_exc

    @staticmethod
    def _parse_response(resp: Any) -> LLMResponse:
        """将 OpenAI ChatCompletion 响应解析为 LLMResponse."""
        choice = resp.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        raw_tool_calls = getattr(msg, "tool_calls", None) or []
        for tc in raw_tool_calls:
            try:
                args_raw = tc.function.arguments or "{}"
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                if not isinstance(args, dict):
                    args = {}
            except (json.JSONDecodeError, AttributeError) as e:
                _log.warning(f"解析 tool_call arguments 失败: {e}，已降级为空 dict")
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                )
            )

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            raw=None,
        )

    @staticmethod
    def _handle_error(e: Exception) -> LLMResponse:
        """把非重试的异常转换成优雅的错误响应.

        细分 6 类：
          - AuthenticationError (401)               → [LLM 认证失败]
          - RateLimitError (429)                    → [LLM 限流]
          - APITimeoutError / APIConnectionError    → [LLM 网络异常]
          - BadRequestError + context_length_exceeded → [LLM 上下文超限]
          - NotFoundError (404 model)               → [LLM 模型不存在]
          - 其它                                     → [LLM 调用失败]
        """
        # noqa: N806 — 这些名字必须保留 PascalCase 以便 isinstance 与 openai SDK 类对齐
        _Auth = _Rate = _Timeout = _Conn = _Bad = _NotFound = _APIErr = None  # noqa: N806
        try:
            from openai import (
                APIConnectionError as _Conn,  # noqa: N812
            )
            from openai import (
                APIError as _APIErr,  # noqa: N812
            )
            from openai import (
                APITimeoutError as _Timeout,  # noqa: N812
            )
            from openai import (
                AuthenticationError as _Auth,  # noqa: N812
            )
            from openai import (
                BadRequestError as _Bad,  # noqa: N812
            )
            from openai import (
                NotFoundError as _NotFound,  # noqa: N812
            )
            from openai import (
                RateLimitError as _Rate,  # noqa: N812
            )
        except ImportError:
            pass

        detail = str(e)
        detail_short = detail[:300]

        msg: str
        if _Auth is not None and isinstance(e, _Auth):
            msg = (
                "[LLM 认证失败] 请检查 OPENAI_API_KEY 是否正确、"
                "以及 OPENAI_BASE_URL 是否与该 key 匹配。\n"
                "⚠️ 常见原因：你 shell 里 export 了一个旧的 OPENAI_API_KEY，"
                "导致 .env 中的正确值被覆盖。可执行 `unset OPENAI_API_KEY` 后重启。\n"
                f"🔍 服务端原始错误：{detail_short}"
            )
        elif _Rate is not None and isinstance(e, _Rate):
            msg = (
                "[LLM 限流] 触发了上游 429（请求过于频繁或配额耗尽）。\n"
                "建议：等待几秒后重试 / 切换到更便宜的模型 / 检查账户配额。\n"
                f"🔍 服务端原始错误：{detail_short}"
            )
        elif (_Timeout is not None and isinstance(e, _Timeout)) or (
            _Conn is not None and isinstance(e, _Conn)
        ):
            msg = (
                "[LLM 网络异常] 与 LLM 服务通信超时或连接失败。\n"
                "建议：检查代理 / VPN / 切换 OPENAI_BASE_URL / 稍后重试。\n"
                f"🔍 异常类型：{type(e).__name__}｜原文：{detail_short}"
            )
        elif (
            _Bad is not None
            and isinstance(e, _Bad)
            and "context_length_exceeded" in detail.lower()
        ):
            msg = (
                "[LLM 上下文超限] 本轮消息加上历史已超过模型最大上下文。\n"
                "建议：开启短期记忆压缩 / 清理历史 / 换更大上下文窗口的模型。\n"
                f"🔍 服务端原始错误：{detail_short}"
            )
        elif _NotFound is not None and isinstance(e, _NotFound):
            msg = (
                f"[LLM 模型不存在] 当前 base_url 找不到模型 `{getattr(e, 'model', '')}`。\n"
                "建议：确认 OPENAI_MODEL 拼写正确；DashScope 常见可用："
                "qwen-plus / qwen-max / qwen-turbo；DeepSeek 常见：deepseek-chat。\n"
                f"🔍 服务端原始错误：{detail_short}"
            )
        elif _APIErr is not None and isinstance(e, _APIErr):
            msg = f"[LLM 调用失败] {type(e).__name__}: {detail_short}"
        else:
            msg = f"[LLM 调用失败] {type(e).__name__}: {detail_short}"

        _log.error(msg)
        return LLMResponse(content=msg, tool_calls=[], finish_reason="error")
