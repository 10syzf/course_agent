"""真实 Web 检索工具.

替换 builtin.py 里 mock 的 web_search，并新增 web_fetch。

策略（自动降级）：
  优先：Tavily（需 TAVILY_API_KEY，质量最好，直接返回结构化摘要）
  次选：DuckDuckGo（用 ddgs 包，无需 Key）
  失败：返回提示信息，不抛异常

web_fetch 用 trafilatura 抽取网页正文，去广告/导航/页脚。
"""

from __future__ import annotations

import os

import httpx

from course_agent.logger import get_logger
from course_agent.tools.registry import tool

_log = get_logger("WebTools")

_DEFAULT_TIMEOUT = 10.0
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 CourseAgent/0.1"
)


def _tavily_search(query: str, k: int) -> str | None:
    """Tavily search；无 Key 时返回 None 让上层降级."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            resp = client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": k,
                    "search_depth": "basic",
                    "include_answer": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001
        _log.warning(f"Tavily 调用失败：{e}")
        return None

    results = data.get("results") or []
    if not results:
        return None
    lines = []
    for i, r in enumerate(results[:k]):
        lines.append(
            f"{i + 1}. {r.get('title', '(no title)')}\n"
            f"   {r.get('url', '')}\n"
            f"   {r.get('content', '').strip()[:300]}"
        )
    return "\n".join(lines)


def _ddg_search(query: str, k: int) -> str | None:
    """DuckDuckGo 搜索（用 ddgs 库）."""
    try:
        from ddgs import DDGS  # type: ignore
    except ImportError:
        _log.warning("未安装 ddgs 包，DuckDuckGo 不可用")
        return None

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=k))
    except Exception as e:  # noqa: BLE001
        _log.warning(f"DuckDuckGo 调用失败：{e}")
        return None

    if not results:
        return None
    lines = []
    for i, r in enumerate(results[:k]):
        title = r.get("title") or "(no title)"
        url = r.get("href") or r.get("url") or ""
        body = (r.get("body") or "").strip()
        lines.append(f"{i + 1}. {title}\n   {url}\n   {body[:300]}")
    return "\n".join(lines)


@tool(
    name="web_search",
    description=(
        "在互联网搜索关键词，返回前 k 条结果（标题 + URL + 摘要）。"
        "优先使用 Tavily（需 TAVILY_API_KEY），降级到 DuckDuckGo。"
    ),
)
def web_search(query: str, k: int = 5) -> str:
    """真实 Web 检索（自动降级）."""
    if not query or not query.strip():
        return "[web_search] query 不能为空。"
    k = max(1, min(int(k), 10))

    out = _tavily_search(query, k)
    if out:
        return f"[Tavily 搜索结果]\n{out}"

    out = _ddg_search(query, k)
    if out:
        return f"[DuckDuckGo 搜索结果]\n{out}"

    return (
        "[web_search] 暂时无法获取真实搜索结果（Tavily/DuckDuckGo 都失败）。\n"
        "建议：在 .env 中配置 TAVILY_API_KEY 以获得更稳定的检索能力。"
    )


@tool(
    name="web_fetch",
    description="抓取给定 URL 的网页内容并提取正文（去广告/导航），用于深入阅读搜索到的页面",
)
def web_fetch(url: str, max_chars: int = 4000) -> str:
    """抓取 URL 并用 trafilatura 提取正文."""
    if not url or not url.strip():
        return "[web_fetch] url 不能为空。"
    max_chars = max(500, min(int(max_chars), 20000))

    try:
        with httpx.Client(
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:  # noqa: BLE001
        return f"[web_fetch] 请求失败：{e}"

    try:
        import trafilatura  # type: ignore

        text = trafilatura.extract(html, include_comments=False, include_tables=False)
    except ImportError:
        text = None
    except Exception as e:  # noqa: BLE001
        _log.warning(f"trafilatura 解析失败：{e}")
        text = None

    if not text:
        # 退化：去 HTML 标签
        import re

        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[正文已截断]"

    return f"[来源] {url}\n\n{text}"
