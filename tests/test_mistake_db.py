"""Task 010：错题本 SQLite 层测试."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from course_agent.storage import mistake_db as mdb


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """每个用例一个独立的 SQLite 文件，避免测试间串扰."""
    db = tmp_path / "mistakes.db"
    monkeypatch.setattr(mdb, "_DB_PATH", db)
    yield db


def test_ensure_schema_is_idempotent():
    mdb.ensure_schema()
    mdb.ensure_schema()
    mdb.ensure_schema()


def test_insert_then_get_roundtrip():
    mid = mdb.insert_mistake(
        question="什么是动态规划？",
        correct_answer="一种带备忘录的递归",
        tags="算法,DP",
        source="test",
    )
    assert mid > 0
    row = mdb.get_mistake(mid)
    assert row is not None
    assert row["question"] == "什么是动态规划？"
    assert row["tags"] == "算法,DP"
    assert row["repetitions"] == 0
    assert row["easiness"] == 2.5
    assert row["interval_days"] == 1.0


def test_list_filter_by_tag():
    mdb.insert_mistake(question="Q1", tags="线代")
    mdb.insert_mistake(question="Q2", tags="概率论")
    mdb.insert_mistake(question="Q3", tags="线代,特征值")

    rows = mdb.list_mistakes_db(tag="线代")
    assert len(rows) == 2
    qs = {r["question"] for r in rows}
    assert qs == {"Q1", "Q3"}


def test_due_today_is_new_inserts():
    mdb.insert_mistake(question="今日待复习题")
    assert mdb.count_due_today() == 1
    rows = mdb.list_mistakes_db(due_only=True)
    assert len(rows) == 1


def test_sm2_quality_5_grows_interval():
    """quality=5 连续 3 轮：interval 应按 1 → 6 → 6*EF 增长."""
    ef, iv, rep = 2.5, 1.0, 0
    ef, iv, rep = mdb.update_sm2(ef, iv, rep, 5)
    assert rep == 1 and iv == 1.0
    ef, iv, rep = mdb.update_sm2(ef, iv, rep, 5)
    assert rep == 2 and iv == 6.0
    ef, iv, rep = mdb.update_sm2(ef, iv, rep, 5)
    assert rep == 3 and iv > 6.0  # 6 * ef (>=2.5)


def test_sm2_quality_0_resets():
    ef, iv, rep = 2.5, 10.0, 5
    new_ef, new_iv, new_rep = mdb.update_sm2(ef, iv, rep, 0)
    assert new_rep == 0
    assert new_iv == 1.0
    assert new_ef < ef  # easiness 会降低


def test_sm2_invalid_quality():
    with pytest.raises(ValueError):
        mdb.update_sm2(2.5, 1.0, 0, -1)
    with pytest.raises(ValueError):
        mdb.update_sm2(2.5, 1.0, 0, 6)


def test_review_mistake_updates_row_and_pushes_next_review():
    mid = mdb.insert_mistake(question="复习测试")
    row = mdb.review_mistake_db(mid, 5)
    assert row is not None
    # 打 5 分后下次复习应在未来
    next_dt = _dt.datetime.fromisoformat(row["next_review_at"])
    assert next_dt >= _dt.datetime.now() - _dt.timedelta(seconds=5)
    assert row["repetitions"] == 1


def test_review_unknown_id_returns_none():
    assert mdb.review_mistake_db(99999, 5) is None
