"""recall / remember 工具的单元测试."""

from __future__ import annotations

import pytest

from course_agent.memory.embedders import HashEmbedder
from course_agent.memory.long_term import LongTermMemory
from course_agent.memory.manager import MemoryManager
from course_agent.memory.short_term import ShortTermMemory
from course_agent.memory.tools import recall, remember, set_active_manager


@pytest.fixture
def manager(tmp_path):
    short = ShortTermMemory(llm=None)
    long_mem = LongTermMemory(
        embedder=HashEmbedder(),
        persist_dir=tmp_path / "chroma",
        collection="memtools",
    )
    mgr = MemoryManager(short=short, long=long_mem, recall_min_score=0.0)
    set_active_manager(mgr)
    yield mgr
    set_active_manager(None)


def test_remember_then_recall(manager):
    msg = remember("用户偏好 Python 解题", tag="preference")
    assert "已记住" in msg

    res = recall("Python 偏好", k=3)
    assert "Python" in res or "python" in res.lower()


def test_recall_when_disabled():
    set_active_manager(None)
    out = recall("anything")
    assert "memory disabled" in out


def test_remember_when_disabled():
    set_active_manager(None)
    out = remember("anything")
    assert "memory disabled" in out


def test_recall_no_match(manager):
    out = recall("a query that has no match xyzpdq")
    assert "没有找到" in out or "RELEVANT" not in out
