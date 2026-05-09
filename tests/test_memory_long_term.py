"""LongTermMemory + Embedder 单元测试.

使用 HashEmbedder 完全离线，不依赖 OpenAI/DashScope。
对 chromadb 也是真实调用（在临时目录），这是验证 add→recall 链路最可靠的方式。
"""

from __future__ import annotations

import pytest

from course_agent.memory.embedders import HashEmbedder
from course_agent.memory.long_term import LongTermMemory


def test_hash_embedder_dim_and_norm():
    emb = HashEmbedder(dim=128)
    v = emb.embed("hello world")
    assert len(v) == 128
    norm = sum(x * x for x in v) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_hash_embedder_same_text_same_vec():
    emb = HashEmbedder()
    assert emb.embed("python is great") == emb.embed("python is great")


def test_hash_embedder_different_texts_differ():
    emb = HashEmbedder()
    assert emb.embed("python") != emb.embed("javascript")


def test_hash_embedder_empty_returns_zero_vec():
    emb = HashEmbedder(dim=8)
    assert emb.embed("") == [0.0] * 8


@pytest.mark.asyncio
async def test_long_term_add_then_recall(tmp_path):
    mem = LongTermMemory(
        embedder=HashEmbedder(),
        persist_dir=tmp_path / "chroma",
        collection="test_recall",
    )
    await mem.add("user", "我喜欢用 Python 写算法题")
    await mem.add("user", "我讨厌写 JavaScript")
    await mem.add("assistant", "好的，我会优先用 Python 给你示例")

    res = await mem.recall("Python 是我的偏好", k=2)
    assert len(res) > 0
    contents = [r.content for r in res]
    # 至少应该召回一个含 Python 的记录
    assert any("Python" in c or "python" in c.lower() for c in contents)


@pytest.mark.asyncio
async def test_long_term_recall_empty_db_returns_empty(tmp_path):
    mem = LongTermMemory(
        embedder=HashEmbedder(),
        persist_dir=tmp_path / "chroma",
        collection="empty_test",
    )
    res = await mem.recall("anything", k=3)
    assert res == []


@pytest.mark.asyncio
async def test_long_term_clear_removes_all(tmp_path):
    mem = LongTermMemory(
        embedder=HashEmbedder(),
        persist_dir=tmp_path / "chroma",
        collection="clear_test",
    )
    await mem.add("user", "foo")
    await mem.add("user", "bar")
    assert mem.count() == 2

    await mem.clear()
    # clear 后再 recall 应为空
    res = await mem.recall("foo", k=3)
    assert res == []


@pytest.mark.asyncio
async def test_long_term_persistence_across_instances(tmp_path):
    """同一 persist_dir 上重建 LongTermMemory，数据应保留."""
    persist = tmp_path / "chroma_persist"

    mem1 = LongTermMemory(
        embedder=HashEmbedder(),
        persist_dir=persist,
        collection="persist_test",
    )
    await mem1.add("user", "PersistData ABCDEFG")

    mem2 = LongTermMemory(
        embedder=HashEmbedder(),
        persist_dir=persist,
        collection="persist_test",
    )
    res = await mem2.recall("PersistData ABCDEFG", k=1)
    assert len(res) == 1
    assert "PersistData" in res[0].content


@pytest.mark.asyncio
async def test_long_term_add_batch(tmp_path):
    mem = LongTermMemory(
        embedder=HashEmbedder(),
        persist_dir=tmp_path / "chroma",
        collection="batch_test",
    )
    await mem.add_batch(
        [
            ("user", "Apple is a fruit", {"tag": "food"}),
            ("user", "Banana is yellow", {"tag": "food"}),
            ("user", "Linux is an OS", {"tag": "tech"}),
        ]
    )
    assert mem.count() == 3
    res = await mem.recall("fruit", k=2)
    assert len(res) > 0
