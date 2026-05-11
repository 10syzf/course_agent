"""Task 010：教材 RAG（kb_ingest / kb_search）测试."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from course_agent.memory.embedders import HashEmbedder
from course_agent.tools import kb as kb_mod
from course_agent.tools.kb import (
    _chunk_text,
    kb_ingest,
    kb_search,
)


@pytest.fixture(autouse=True)
def _tmp_kb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """把 kb 的持久化目录指到 tmp，确保每个用例全新 Chroma collection."""
    persist = tmp_path / "kb"
    monkeypatch.setattr(kb_mod, "_DEFAULT_PERSIST_DIR", persist)
    # 用 HashEmbedder 避免真 API 调用
    monkeypatch.setattr(
        kb_mod, "create_embedder", lambda *a, **kw: HashEmbedder()
    )
    yield persist


def test_chunk_text_basic():
    chunks = _chunk_text("0123456789" * 200, chunk_size=400, overlap=50)
    # 2000 字符，step=350，预计 6 个 chunk
    assert len(chunks) >= 5
    assert all(len(c) <= 400 for c in chunks)


def test_chunk_text_empty_returns_empty():
    assert _chunk_text("") == []


def test_chunk_text_overlap_auto_clamp():
    # overlap 大于等于 chunk_size 时自动夹回 chunk_size // 2
    chunks = _chunk_text("a" * 100, chunk_size=10, overlap=999)
    assert len(chunks) > 0
    assert all(len(c) <= 10 for c in chunks)


def test_ingest_empty_query_rejected():
    out = kb_search("   ")
    import json as _json

    assert "error" in _json.loads(out)


def test_ingest_nonexistent_file():
    out = kb_ingest("/tmp/definitely-not-exist-99999.md")
    import json as _json

    assert "error" in _json.loads(out)


def test_ingest_markdown_then_search(tmp_path: Path):
    md = tmp_path / "textbook.md"
    md.write_text(
        "RSA 是一种非对称加密算法。\n"
        "其安全性基于大整数分解的计算困难性。\n" * 20,
        encoding="utf-8",
    )
    out = kb_ingest(str(md))
    assert "✅ 已摄入" in out
    # 带 hash 兜底警告
    assert "hash 兜底" in out

    # 搜索能命中
    hit = kb_search("RSA 加密", top_k=3)
    assert "📚" in hit
    assert "textbook.md" in hit
    assert "hash 兜底" in hit  # search 输出也应提示


def test_search_on_empty_kb():
    out = kb_search("anything")
    assert "📭" in out


def test_ingest_unsupported_extension(tmp_path: Path):
    fp = tmp_path / "file.xlsx"
    fp.write_bytes(b"fake")
    out = kb_ingest(str(fp))
    import json as _json

    assert "error" in _json.loads(out)


def test_ingest_pdf_mocked(tmp_path: Path):
    """mock pypdf 以免真跑 PDF；验证 ingest 能按页入库."""
    import types

    fake_pages = [
        types.SimpleNamespace(extract_text=lambda: "第一页内容，介绍特征值。"),
        types.SimpleNamespace(extract_text=lambda: "第二页内容，讲 RSA 加密。"),
    ]
    fake_reader = types.SimpleNamespace(pages=fake_pages)

    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")  # 占位字节

    with patch("pypdf.PdfReader", return_value=fake_reader):
        out = kb_ingest(str(pdf))
    assert "✅ 已摄入" in out
    assert "2 页" in out

    hit = kb_search("RSA")
    assert "book.pdf" in hit
    assert "P.2" in hit  # metadata 中的 page 应被展示
