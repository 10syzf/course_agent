"""错题本 SQLite 存储层（Task 010）.

设计要点：
- 路径 ~/.cache/course-agent/mistakes.db，与 python_exec 包缓存同根，便于 doctor 一并检查
- schema 幂等：每次连接前调 ensure_schema()，已存在则跳过
- SM-2 算法（SuperMemo 2 简化版）：quality 0-5 → (easiness, interval_days, repetitions)
- 不引入新三方依赖；纯 stdlib sqlite3
"""

from __future__ import annotations

import datetime as _dt
import sqlite3
from pathlib import Path
from typing import Any

_DB_DIR = Path("~/.cache/course-agent").expanduser()
_DB_PATH = _DB_DIR / "mistakes.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mistakes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question        TEXT NOT NULL,
    wrong_answer    TEXT NOT NULL DEFAULT '',
    correct_answer  TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '',
    source          TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    interval_days   REAL NOT NULL DEFAULT 1.0,
    repetitions     INTEGER NOT NULL DEFAULT 0,
    easiness        REAL NOT NULL DEFAULT 2.5,
    next_review_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_due ON mistakes(next_review_at);
CREATE INDEX IF NOT EXISTS idx_tags ON mistakes(tags);
"""


def get_db_path() -> Path:
    """返回错题库 SQLite 文件路径（不保证存在）."""
    return _DB_PATH


def _override_db_path_for_test(path: Path) -> None:
    """仅供测试使用：临时切到独立 db 文件."""
    global _DB_PATH
    _DB_PATH = path


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    """幂等建表."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def update_sm2(
    easiness: float,
    interval_days: float,
    repetitions: int,
    quality: int,
) -> tuple[float, float, int]:
    """SM-2 简化版.

    quality:
        0 = 完全不会
        1 = 想起来但错
        2 = 错但有印象
        3 = 磕巴对（最低及格线）
        4 = 流畅对
        5 = 秒答

    返回 (new_easiness, new_interval_days, new_repetitions).
    """
    if quality < 0 or quality > 5:
        raise ValueError(f"quality 必须 0-5，收到 {quality}")

    if quality < 3:
        repetitions = 0
        interval_days = 1.0
    else:
        repetitions += 1
        if repetitions == 1:
            interval_days = 1.0
        elif repetitions == 2:
            interval_days = 6.0
        else:
            interval_days = round(interval_days * easiness, 1)

    easiness = max(
        1.3,
        easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
    )
    return easiness, interval_days, repetitions


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _today_end_iso() -> str:
    """今天 23:59:59，用作"今日待复习"的上界."""
    today = _dt.date.today()
    return f"{today.isoformat()}T23:59:59"


def insert_mistake(
    question: str,
    correct_answer: str = "",
    wrong_answer: str = "",
    tags: str = "",
    source: str = "",
) -> int:
    """插入一条错题，next_review_at 设为今天（立刻进入今日待复习队列）."""
    ensure_schema()
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO mistakes
                (question, correct_answer, wrong_answer, tags, source,
                 created_at, interval_days, repetitions, easiness, next_review_at)
            VALUES (?, ?, ?, ?, ?, ?, 1.0, 0, 2.5, ?)
            """,
            (question, correct_answer, wrong_answer, tags, source, now, now),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_mistakes_db(
    tag: str = "",
    due_only: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    ensure_schema()
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    sql = "SELECT * FROM mistakes WHERE 1=1"
    args: list[Any] = []
    if tag:
        sql += " AND tags LIKE ?"
        args.append(f"%{tag}%")
    if due_only:
        sql += " AND next_review_at <= ?"
        args.append(_today_end_iso())
    sql += " ORDER BY next_review_at ASC, id DESC LIMIT ?"
    args.append(limit)

    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]


def get_mistake(mistake_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        return dict(row) if row else None


def review_mistake_db(mistake_id: int, quality: int) -> dict[str, Any] | None:
    """对一道错题打分，更新 SM-2 字段并写回，返回更新后的记录."""
    ensure_schema()
    row = get_mistake(mistake_id)
    if row is None:
        return None
    new_ef, new_iv, new_rep = update_sm2(
        float(row["easiness"]),
        float(row["interval_days"]),
        int(row["repetitions"]),
        int(quality),
    )
    next_review = (
        _dt.datetime.now() + _dt.timedelta(days=new_iv)
    ).isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """
            UPDATE mistakes
            SET interval_days = ?, repetitions = ?, easiness = ?, next_review_at = ?
            WHERE id = ?
            """,
            (new_iv, new_rep, new_ef, next_review, mistake_id),
        )
        conn.commit()
    updated = get_mistake(mistake_id)
    return updated


def count_due_today() -> int:
    """今日待复习数（next_review_at <= 今天 23:59:59）."""
    ensure_schema()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM mistakes WHERE next_review_at <= ?",
            (_today_end_iso(),),
        ).fetchone()
        return int(row["n"]) if row else 0
