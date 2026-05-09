"""LLM 错误分类细化测试（Task 008 §4.4）.

覆盖 6 类异常 → 各自独有的前缀文案：
  - AuthenticationError  → [LLM 认证失败]
  - RateLimitError       → [LLM 限流]
  - APITimeoutError      → [LLM 网络异常]
  - APIConnectionError   → [LLM 网络异常]
  - BadRequestError + context_length_exceeded → [LLM 上下文超限]
  - NotFoundError        → [LLM 模型不存在]
  - 其它                  → [LLM 调用失败]
"""

from __future__ import annotations

from course_agent.llm.openai_like import OpenAILLM


def _make_exc(cls):
    """构造一个 openai 异常实例：openai 异常签名各不相同，逐个伺候."""
    from httpx import Request, Response

    req = Request("POST", "https://example.com/v1/chat/completions")

    if cls.__name__ == "APIConnectionError":
        return cls(message="connection refused", request=req)
    if cls.__name__ in ("APITimeoutError",):
        return cls(request=req)

    # AuthenticationError / RateLimitError / BadRequestError / NotFoundError 这一脉
    # 签名是 (message, *, response, body)
    response = Response(
        status_code=cls.__name__ == "AuthenticationError" and 401
        or cls.__name__ == "RateLimitError" and 429
        or cls.__name__ == "BadRequestError" and 400
        or cls.__name__ == "NotFoundError" and 404
        or 500,
        request=req,
    )
    body = None
    if cls.__name__ == "BadRequestError":
        body = {"error": {"code": "context_length_exceeded", "message": "too long"}}
    return cls("server-side detail", response=response, body=body)


def test_authentication_error():
    from openai import AuthenticationError

    resp = OpenAILLM._handle_error(_make_exc(AuthenticationError))
    assert resp.content.startswith("[LLM 认证失败]")
    assert resp.finish_reason == "error"


def test_rate_limit_error():
    from openai import RateLimitError

    resp = OpenAILLM._handle_error(_make_exc(RateLimitError))
    assert resp.content.startswith("[LLM 限流]")


def test_api_timeout_error():
    from openai import APITimeoutError

    resp = OpenAILLM._handle_error(_make_exc(APITimeoutError))
    assert resp.content.startswith("[LLM 网络异常]")


def test_api_connection_error():
    from openai import APIConnectionError

    resp = OpenAILLM._handle_error(_make_exc(APIConnectionError))
    assert resp.content.startswith("[LLM 网络异常]")


def test_context_length_exceeded():
    from openai import BadRequestError

    e = _make_exc(BadRequestError)
    # 把 context_length_exceeded 信号塞到 str(e) 里
    object.__setattr__(e, "args", ("context_length_exceeded: too many tokens",))
    resp = OpenAILLM._handle_error(e)
    assert resp.content.startswith("[LLM 上下文超限]")


def test_not_found_model_error():
    from openai import NotFoundError

    resp = OpenAILLM._handle_error(_make_exc(NotFoundError))
    assert resp.content.startswith("[LLM 模型不存在]")


def test_unknown_error_falls_back():
    resp = OpenAILLM._handle_error(RuntimeError("weird boom"))
    assert resp.content.startswith("[LLM 调用失败]")
    assert "weird boom" in resp.content


def test_bad_request_without_context_overflow_falls_back():
    """普通 400（不是上下文超限）应进入兜底，而不是错报 [LLM 上下文超限]."""
    from openai import BadRequestError

    e = _make_exc(BadRequestError)
    object.__setattr__(e, "args", ("invalid parameter foo",))
    resp = OpenAILLM._handle_error(e)
    assert resp.content.startswith("[LLM 调用失败]")
    assert "[LLM 上下文超限]" not in resp.content
