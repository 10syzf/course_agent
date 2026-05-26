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

from course_agent.llm.base import BaseLLM, LLMMessage, LLMResponse, StreamChunk, ToolCall
from course_agent.logger import get_logger
from course_agent.observability.metrics import track_llm_call

_log = get_logger("OpenAILLM")


def _fill_usage(rec: Any, resp: Any) -> None:
    """从 OpenAI ChatCompletion 响应里把 usage 信息填到 metrics record."""
    try:
        usage = getattr(resp, "usage", None)
        if usage is None:
            return
        rec.prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        rec.completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    except Exception:  # noqa: BLE001
        pass


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
            with track_llm_call(model=self.model) as rec:
                resp = self._with_retry(lambda: client.chat.completions.create(**payload))
                _fill_usage(rec, resp)
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
            with track_llm_call(model=self.model) as rec:
                resp = await self._awith_retry(client, payload)
                _fill_usage(rec, resp)
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

    async def astream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ):
        """真流式实装（Task 011）.

        - 直接用 OpenAI SDK 的 ``stream=True``：返回的 chunk.choices[0].delta 已经是
          OpenAI 标准的流式增量 shape；我们直接转 ``StreamChunk``，不做拼装（拼装由
          上层 ``AgentLoop.astream_run()`` 负责）。
        - 任何异常都包成单条 ``finish_reason='error'`` chunk，由 AgentLoop 决定降级。
        - kwargs 与 ``achat()`` 完全对齐（temperature / max_tokens / tool_choice）。
        """
        try:
            client = self._get_async_client()
        except Exception as e:  # noqa: BLE001
            yield StreamChunk(finish_reason="error", error=f"{type(e).__name__}: {e}")
            return

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_openai() for m in messages],
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        try:
            stream = await client.chat.completions.create(**payload)
        except Exception as e:  # noqa: BLE001
            yield StreamChunk(finish_reason="error", error=f"{type(e).__name__}: {e}")
            return

        # metrics: 流式无法精确拿到 usage（多数 provider 不发），按 chunk 数估算
        from course_agent.observability.metrics import MetricRecord, _insert

        _t0 = time.perf_counter()
        _rec = MetricRecord(
            model=self.model,
            agent_name="",  # 留空让 _insert 时用 contextvar 当前值——手动填一次
        )
        from course_agent.observability.metrics import get_current_agent
        _rec.agent_name = get_current_agent()
        completion_chars = 0
        try:
            async for chunk in stream:
                try:
                    choice = chunk.choices[0]
                except (IndexError, AttributeError):
                    continue
                delta = getattr(choice, "delta", None)
                finish_reason = getattr(choice, "finish_reason", None)

                delta_text = ""
                tc_delta: dict[str, Any] | None = None
                if delta is not None:
                    delta_text = getattr(delta, "content", None) or ""
                    completion_chars += len(delta_text)
                    raw_tcs = getattr(delta, "tool_calls", None) or []
                    for raw_tc in raw_tcs:
                        # OpenAI 流式 tool_call 增量：index / id / function.name / function.arguments
                        # 一次 chunk 一般只带其中部分字段，由上层按 index 拼起来。
                        fn = getattr(raw_tc, "function", None)
                        tc_delta = {
                            "index": getattr(raw_tc, "index", 0) or 0,
                            "id": getattr(raw_tc, "id", None),
                            "function": {
                                "name": getattr(fn, "name", None) if fn else None,
                                "arguments": getattr(fn, "arguments", None) if fn else None,
                            },
                        }
                        # 一个 chunk 里若同时多 tool_call，分多次 yield
                        yield StreamChunk(
                            delta_text=delta_text if delta_text else "",
                            tool_call_delta=tc_delta,
                            finish_reason=None,
                        )
                        delta_text = ""  # 文本只在第一个 tc_delta 上挂一次，避免重复

                if delta_text or (tc_delta is None and finish_reason):
                    yield StreamChunk(
                        delta_text=delta_text,
                        finish_reason=finish_reason,
                    )
                elif finish_reason:
                    yield StreamChunk(finish_reason=finish_reason)
        except Exception as e:  # noqa: BLE001
            _rec.status = "error"
            _rec.error = f"{type(e).__name__}: {e}"
            _rec.latency_ms = int((time.perf_counter() - _t0) * 1000)
            _insert(_rec)
            yield StreamChunk(finish_reason="error", error=f"{type(e).__name__}: {e}")
            return
        _rec.completion_tokens = max(0, completion_chars // 4)  # 粗估：4 chars ≈ 1 token
        _rec.latency_ms = int((time.perf_counter() - _t0) * 1000)
        _insert(_rec)
