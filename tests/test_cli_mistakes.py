"""Task 010：CLI mistakes 子命令测试."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from course_agent.cli import app
from course_agent.storage import mistake_db as mdb

runner = CliRunner()


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "mistakes.db"
    monkeypatch.setattr(mdb, "_DB_PATH", db)
    yield db


def test_mistakes_list_empty():
    result = runner.invoke(app, ["mistakes", "list"])
    assert result.exit_code == 0
    assert "📭" in result.output or "错题本" in result.output


def test_mistakes_due_empty():
    result = runner.invoke(app, ["mistakes", "due"])
    assert result.exit_code == 0
    assert "暂无" in result.output or "0" in result.output


def test_mistakes_review_not_found():
    result = runner.invoke(app, ["mistakes", "review", "99999", "5"])
    assert result.exit_code == 1


def test_mistakes_full_flow():
    # 先手动插一条
    mdb.insert_mistake(question="什么是递归？", correct_answer="自己调自己")
    # list 应显示
    result = runner.invoke(app, ["mistakes", "list"])
    assert result.exit_code == 0
    assert "递归" in result.output
    # due 应有
    result = runner.invoke(app, ["mistakes", "due"])
    assert result.exit_code == 0
    assert "递归" in result.output
    # review
    result = runner.invoke(app, ["mistakes", "review", "1", "4"])
    assert result.exit_code == 0
    assert "复习完成" in result.output or "✅" in result.output
