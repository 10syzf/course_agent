"""题目生成器工具（Task 011）.

`generate_question(tag, question_type, difficulty, n_refs)`：
    - 若 tag 非空，先查错题本拿到该 tag 下学生答错过的题目，作为「避免出重」的参考
    - 调 kb_search(tag) 拿 n_refs 段教材作为素材
    - 拼 prompt 让 LLM 出一道结构化的新题，**强制 JSON 输出**：
        {question, correct_answer, explanation, source, based_on_mistakes, type, difficulty}
    - 校验 JSON schema，失败重试 1 次；仍失败则降级为「LLM 自由发挥」+ ⚠️ 标注

返回值：markdown 字符串（题面 + 出处 + correct_answer 内嵌为不可见字段以便 Examiner 自批改）。
为了让上层 Examiner Agent 能拿到 correct_answer 做判分，我们把 correct_answer / explanation
**显式包含**在返回的 markdown 末尾的 ```correct``` 代码块里——Examiner 的 system_prompt
会指导它"读到 correct 块后不要把里面的内容直接展示给学生，先等学生作答"。

设计上故意不让 generate_question 写错题本（写不写由 Examiner 判分后决定），保证工具单一职责。
"""

from __future__ import annotations

import json
from typing import Any

from course_agent.llm import get_default_llm
from course_agent.llm.base import LLMMessage
from course_agent.logger import get_logger
from course_agent.tools.kb import _is_hash_embedder, kb_search
from course_agent.tools.registry import tool

_log = get_logger("generator")

_VALID_TYPES = ("选择题", "填空题", "解答题", "证明题", "判断题")
_VALID_DIFFICULTY = ("简单", "中", "难")
_MAX_REFS = 6
_MAX_PAST_MISTAKES = 5

_GENERATOR_SYSTEM_PROMPT = """你是 Course Agent 题目生成器（Question Generator）。
你的任务：根据用户给的知识点 tag、题型、难度，**生成一道全新的练习题**，并严格输出 JSON。

【输入】用户消息里包含三类素材：
  1. 知识点 tag（如「线代,特征值」）
  2. 教材参考片段（带来源标注）
  3. 学生过去做错的题目列表（avoid_repeat：避免与下列题目雷同）

【输出】**只输出一个 JSON 对象**（不要 markdown 代码块包裹），字段如下：
{
  "question": "<题目原文，含必要的数据/条件>",
  "correct_answer": "<标准答案，要点齐全>",
  "explanation": "<两三句话的解题思路>",
  "source": "<引用了哪段教材，例如 '线代教材 P.83'；若没参考教材则填 '原创'>",
  "based_on_mistakes": [<整数 ID 列表，引用了哪些 past_mistakes 的影子>],
  "type": "<题型：选择题/填空题/解答题/证明题/判断题>",
  "difficulty": "<简单/中/难>"
}

【硬约束】
- question 必须与 avoid_repeat 中任何一题**字面/结构都不同**
- correct_answer 必须与 question 自洽
- 中文输出
- 不要附加 ```json``` 或多余说明，**只输出 JSON 本体**
"""


def _query_past_mistakes(tag: str) -> list[dict[str, Any]]:
    """从错题本拿同 tag 的过往错题（最多 _MAX_PAST_MISTAKES 条）."""
    if not tag.strip():
        return []
    try:
        from course_agent.storage.mistake_db import list_mistakes_db

        rows = list_mistakes_db(tag=tag, due_only=False, limit=_MAX_PAST_MISTAKES)
    except Exception as e:  # noqa: BLE001
        _log.warning(f"读取过往错题失败：{type(e).__name__}: {e}")
        return []
    return [{"id": r["id"], "question": r["question"][:120]} for r in rows]


def _build_user_prompt(
    tag: str,
    question_type: str,
    difficulty: str,
    refs: str,
    past_mistakes: list[dict[str, Any]],
    fallback_note: str = "",
) -> str:
    past_lines = "\n".join(
        f"  - #{m['id']}: {m['question']}" for m in past_mistakes
    )
    if not past_lines:
        past_lines = "  （暂无过往错题）"
    return (
        f"知识点 tag: {tag or '（未指定，请你按你认为合适的常见知识点出题）'}\n"
        f"题型: {question_type}\n"
        f"难度: {difficulty}\n\n"
        f"教材参考片段（仅供参考，不必照抄）：\n{refs or '（暂无可用教材片段）'}\n\n"
        f"avoid_repeat（学生过去做错过这些题，请生成不同的新题）：\n{past_lines}\n"
        f"{fallback_note}"
        "\n请按系统提示要求，**仅输出一个 JSON 对象**。"
    )


def _parse_json_safe(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    s = raw.strip()
    # 兜底：如果 LLM 还是用了 ```json ``` 包裹，剥一下
    if s.startswith("```"):
        s = s.split("```", 2)[-1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip().rstrip("`").strip()
    # 再兜：找第一个 { 与最后一个 } 截取
    if "{" in s and "}" in s:
        s = s[s.find("{") : s.rfind("}") + 1]
    try:
        obj = json.loads(s)
        if isinstance(obj, dict) and "question" in obj:
            return obj
    except json.JSONDecodeError:
        return None
    return None


def _format_markdown(obj: dict[str, Any], hash_warning: str = "") -> str:
    q = obj.get("question", "").strip()
    src = obj.get("source", "").strip() or "原创"
    typ = obj.get("type", "").strip() or "解答题"
    diff = obj.get("difficulty", "").strip() or "中"
    bom = obj.get("based_on_mistakes") or []
    correct = obj.get("correct_answer", "").strip()
    expl = obj.get("explanation", "").strip()

    bom_line = (
        f"基于错题：{', '.join('#' + str(i) for i in bom)}" if bom else "基于错题：（无）"
    )
    head = (
        f"### 📝 新题（{typ} · 难度 {diff}）\n\n"
        f"{q}\n\n"
        f"📚 参考：{src}  ｜  {bom_line}{hash_warning}\n"
    )
    # correct 块是给 Examiner Agent 自己读的，不希望 UI 上学生先看到——
    # Examiner 的 system prompt 会引导它"先等学生答完再揭晓"。
    correct_block = (
        "\n```correct\n"
        f"correct_answer: {correct}\n"
        f"explanation: {expl}\n"
        "```\n"
    )
    return head + correct_block


@tool(
    name="generate_question",
    description=(
        "基于错题本和教材库生成一道**新**的练习题。"
        "参数：tag（知识点标签，逗号分隔，如 '线代,特征值'）；"
        "question_type（选择题/填空题/解答题/证明题/判断题，默认 解答题）；"
        "difficulty（简单/中/难，默认 中）；"
        "n_refs（检索教材 chunk 数，1-6，默认 3）。"
        "返回 markdown 题面 + 教材出处 + 内嵌的 ```correct``` 代码块（仅供 Examiner Agent 自批改用，不应直接展示给学生）。"
    ),
)
def generate_question(
    tag: str = "",
    question_type: str = "解答题",
    difficulty: str = "中",
    n_refs: int = 3,
) -> str:
    if not isinstance(tag, str):
        tag = str(tag or "")
    qt = question_type if question_type in _VALID_TYPES else "解答题"
    diff = difficulty if difficulty in _VALID_DIFFICULTY else "中"
    try:
        n = max(1, min(int(n_refs), _MAX_REFS))
    except (ValueError, TypeError):
        n = 3

    # 1. 取教材参考素材
    refs_text = ""
    hash_warning = ""
    if tag.strip():
        try:
            kb_out = kb_search(query=tag, top_k=n)
            refs_text = kb_out if isinstance(kb_out, str) else ""
        except Exception as e:  # noqa: BLE001
            _log.warning(f"kb_search 失败：{type(e).__name__}: {e}")
            refs_text = ""

    # 检测是否处于 hash 兜底（如果 kb_search 输出末尾带 ⚠️ 兜底提示）
    if "hash 兜底" in refs_text:
        hash_warning = "  \n> ⚠️ 当前 hash 兜底，参考素材召回有限"
    else:
        # 也单独探一下（即便 kb 为空也要警告 hash 兜底，提醒"为啥没素材"）
        try:
            from course_agent.tools.kb import _get_kb_collection

            _, emb = _get_kb_collection()
            if _is_hash_embedder(emb):
                hash_warning = "  \n> ⚠️ 当前 hash 兜底，参考素材召回有限"
        except Exception:  # noqa: BLE001
            pass

    # 2. 取过往错题（避免出重）
    past_mistakes = _query_past_mistakes(tag)

    # 3. 调 LLM 出题（结构化 JSON）
    try:
        llm = get_default_llm()
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"error": f"LLM 不可用：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    base_user_prompt = _build_user_prompt(
        tag, qt, diff, refs_text, past_mistakes
    )
    messages = [
        LLMMessage(role="system", content=_GENERATOR_SYSTEM_PROMPT),
        LLMMessage(role="user", content=base_user_prompt),
    ]

    obj: dict[str, Any] | None = None
    last_raw = ""
    for attempt in range(2):  # 最多 1 次重试
        try:
            resp = llm.chat(messages)
        except Exception as e:  # noqa: BLE001
            _log.warning(f"LLM 出题失败 attempt={attempt}：{type(e).__name__}: {e}")
            continue
        last_raw = resp.content or ""
        obj = _parse_json_safe(last_raw)
        if obj:
            break
        # 重试时附带上一次失败原因，强提示"输出严格 JSON"
        retry_note = (
            "\n\n⚠️ 上次输出无法解析为 JSON，请重新生成；"
            "**仅输出 JSON 本体**，不要任何 ``` 代码块或解释文字。"
        )
        messages = [
            LLMMessage(role="system", content=_GENERATOR_SYSTEM_PROMPT),
            LLMMessage(role="user", content=base_user_prompt + retry_note),
        ]

    if not obj:
        return (
            "⚠️ 题目生成失败：LLM 未返回合法 JSON。原始响应（截断 200 字）：\n"
            f"{last_raw[:200]}\n\n请稍后重试，或尝试更具体的 tag。"
        )

    # 兜底字段
    obj.setdefault("type", qt)
    obj.setdefault("difficulty", diff)
    obj.setdefault("source", "原创")
    obj.setdefault("based_on_mistakes", [])

    # 去重校验：question 与 past 的字面命中过高时，强提示警告（不阻断）
    question = obj.get("question", "")
    if past_mistakes and any(
        question and m["question"].strip() and m["question"].strip()[:30] in question
        for m in past_mistakes
    ):
        hash_warning += "  \n> ⚠️ 与历史错题相似度较高，可让 Examiner 重新出题"

    return _format_markdown(obj, hash_warning=hash_warning)
