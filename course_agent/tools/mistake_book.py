"""错题本工具（Task 010）.

三个 @tool 入口：
    - add_mistake      记入一道错题
    - list_mistakes    列出错题（可过滤 tag / 仅今日待复习）
    - review_mistake   对错题打分（SM-2 更新下次复习时间）
"""

from __future__ import annotations

import json
from typing import Any

from course_agent.logger import get_logger
from course_agent.storage.mistake_db import (
    count_due_today,
    insert_mistake,
    list_mistakes_db,
    review_mistake_db,
)
from course_agent.tools.registry import tool

_log = get_logger("mistake_book")

_QUALITY_LABEL = {
    0: "😵 完全不会",
    1: "😣 想起来但错",
    2: "🤔 错但有印象",
    3: "😐 磕巴对",
    4: "🙂 流畅对",
    5: "😎 秒答",
}


def _format_row(row: dict[str, Any]) -> str:
    tags = row.get("tags") or "-"
    q = row.get("question", "") or ""
    if len(q) > 60:
        q = q[:57] + "..."
    return (
        f"| {row['id']:>3} | {q} | {tags} | "
        f"复习 × {row['repetitions']} | 下次 {row['next_review_at'][:10]} |"
    )


@tool(
    name="add_mistake",
    description=(
        "把一道做错的题目记入错题本（本地 SQLite）。"
        "字段：question（题目原文，必填）/ correct_answer（正确答案或解析）/ "
        "wrong_answer（当时的错答，可选）/ tags（逗号分隔，如 '线代,特征值'）/ "
        "source（来源，如 'image_ocr' 或 'homework_ch3.pdf P.42'）。"
    ),
)
def add_mistake(
    question: str,
    correct_answer: str = "",
    wrong_answer: str = "",
    tags: str = "",
    source: str = "",
) -> str:
    if not isinstance(question, str) or not question.strip():
        return json.dumps(
            {"error": "question 不能为空"}, ensure_ascii=False
        )
    try:
        mid = insert_mistake(
            question=question.strip(),
            correct_answer=correct_answer.strip() if isinstance(correct_answer, str) else "",
            wrong_answer=wrong_answer.strip() if isinstance(wrong_answer, str) else "",
            tags=tags.strip() if isinstance(tags, str) else "",
            source=source.strip() if isinstance(source, str) else "",
        )
    except Exception as e:  # noqa: BLE001
        _log.warning(f"add_mistake 失败：{type(e).__name__}: {e}")
        return json.dumps(
            {"error": f"写入错题库失败：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )
    return (
        f"✅ 已记入错题本（#{mid}）。"
        f"题目：{question[:40]}{'...' if len(question) > 40 else ''}；"
        f"标签：{tags or '-'}；"
        "默认 1 天后复习。"
    )


@tool(
    name="list_mistakes",
    description=(
        "列出错题。参数：tag（按标签过滤，如 '线代'；留空=全部）；"
        "due_only（true=仅列今日待复习）；limit（默认 20，最大 200）。"
    ),
)
def list_mistakes(
    tag: str = "",
    due_only: bool = False,
    limit: int = 20,
) -> str:
    try:
        rows = list_mistakes_db(tag=tag or "", due_only=bool(due_only), limit=int(limit))
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"error": f"读取错题库失败：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    if not rows:
        if due_only:
            return "📭 今天没有待复习的错题，继续加油！"
        return "📭 错题本还是空的——做错题时可调用 add_mistake 记进来。"

    due_n = count_due_today()
    header = (
        f"📓 错题本（共 {len(rows)} 条；今日待复习：{due_n}）\n"
        "| ID | 题目（截断 60） | 标签 | 复习次数 | 下次复习 |\n"
        "|---|---|---|---|---|"
    )
    body = "\n".join(_format_row(r) for r in rows)
    return header + "\n" + body


@tool(
    name="review_mistake",
    description=(
        "对一道错题的掌握情况打分（0-5），系统用 SM-2 算法计算下次复习时间。"
        "0=完全不会 / 1=想起来但错 / 2=错但有印象 / 3=磕巴对 / 4=流畅对 / 5=秒答。"
    ),
)
def review_mistake(mistake_id: int, quality: int) -> str:
    try:
        mid = int(mistake_id)
        q = int(quality)
    except (ValueError, TypeError):
        return json.dumps(
            {"error": "mistake_id 与 quality 必须是整数"},
            ensure_ascii=False,
        )
    if q < 0 or q > 5:
        return json.dumps(
            {"error": "quality 必须在 0-5 之间"},
            ensure_ascii=False,
        )
    try:
        row = review_mistake_db(mid, q)
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"error": f"打分失败：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )
    if row is None:
        return json.dumps(
            {"error": f"找不到错题 #{mid}"},
            ensure_ascii=False,
        )
    return (
        f"✅ 已对 #{mid} 打分 {q}（{_QUALITY_LABEL[q]}）。"
        f"下次复习：{row['next_review_at'][:10]}；"
        f"当前间隔 {row['interval_days']} 天；"
        f"easiness={row['easiness']:.2f}；"
        f"连续答对 {row['repetitions']} 次。"
    )
