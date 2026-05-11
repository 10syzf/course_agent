"""Task 010：错题本工具（add_mistake / list_mistakes / review_mistake）测试."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from course_agent.storage import mistake_db as mdb
from course_agent.tools.mistake_book import (
    add_mistake,
    list_mistakes,
    review_mistake,
)


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "mistakes.db"
    monkeypatch.setattr(mdb, "_DB_PATH", db)
    yield db


def test_add_mistake_rejects_empty_question():
    out = add_mistake(question="   ")
    payload = json.loads(out)
    assert "error" in payload


def test_add_mistake_basic_path():
    out = add_mistake(
        question="什么是 RSA？",
        correct_answer="非对称加密……",
        tags="密码学",
        source="textbook P.42",
    )
    assert out.startswith("✅ 已记入错题本")
    rows = mdb.list_mistakes_db()
    assert len(rows) == 1
    assert rows[0]["tags"] == "密码学"


def test_list_mistakes_empty():
    out = list_mistakes()
    assert "📭" in out


def test_list_mistakes_with_chinese_tag():
    add_mistake(question="题1", tags="线代")
    add_mistake(question="题2", tags="概率")
    out = list_mistakes(tag="线代")
    assert "题1" in out
    assert "题2" not in out
    assert "📓" in out


def test_review_mistake_invalid_quality_returns_error():
    add_mistake(question="抽样题")
    out = review_mistake(mistake_id=1, quality=99)
    payload = json.loads(out)
    assert "error" in payload


def test_review_mistake_unknown_id_returns_error():
    out = review_mistake(mistake_id=99999, quality=5)
    payload = json.loads(out)
    assert "error" in payload


def test_full_flow_add_review_progress():
    add_mistake(question="DP 题")
    rows = mdb.list_mistakes_db()
    mid = rows[0]["id"]
    out = review_mistake(mistake_id=mid, quality=5)
    assert "✅" in out
    rows = mdb.list_mistakes_db()
    assert rows[0]["repetitions"] == 1
