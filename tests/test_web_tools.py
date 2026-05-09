"""Web 检索工具测试.

只测离线降级路径与无 Key 时的行为；真实网络请求另外通过 RUN_LIVE_WEB=1 触发。
"""

from __future__ import annotations

import os

import pytest

from course_agent.tools import get_registry
from course_agent.tools.web_tools import web_fetch, web_search


def test_web_search_registered():
    reg = get_registry()
    assert "web_search" in reg.list_names()
    assert "web_fetch" in reg.list_names()


def test_web_search_empty_query():
    out = web_search("", k=3)
    assert "不能为空" in out


def test_web_fetch_empty_url():
    out = web_fetch("", max_chars=100)
    assert "不能为空" in out


def test_web_fetch_invalid_url_returns_error():
    out = web_fetch("http://this-domain-definitely-does-not-exist-xyz123.example", max_chars=100)
    assert out.startswith("[web_fetch] 请求失败") or "[来源]" in out


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_WEB") != "1",
    reason="需要 RUN_LIVE_WEB=1 才会跑真实网络请求",
)
def test_web_search_real_duckduckgo():
    out = web_search("Python programming language", k=3)
    assert any(tag in out for tag in ("[Tavily", "[DuckDuckGo"))
    assert "http" in out


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_WEB") != "1",
    reason="需要 RUN_LIVE_WEB=1 才会跑真实网络请求",
)
def test_web_fetch_real_page():
    out = web_fetch("https://example.com/", max_chars=2000)
    assert "[来源]" in out
    assert "Example" in out or "example" in out
