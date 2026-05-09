"""PDF 阅读工具：基于 pypdf 的纯文本快速路径.

不做的事（留 Task 009 OCR）：
- 扫描件 / 纯图像 PDF 的 OCR
- 复杂版式还原 / LaTeX 公式精准识别
- 表格结构化抽取
"""

from __future__ import annotations

import json
from pathlib import Path

from course_agent.logger import get_logger
from course_agent.tools.registry import tool

_log = get_logger("pdf_tools")

_DEFAULT_MAX_CHARS = 8000
_HARD_MAX_CHARS = 64 * 1024
# 扫描件判别：所有处理过的页面**最长**那一页的文本长度都 < 阈值时，认定为扫描件 / 纯图像 PDF。
# 用 max-per-page 而不是 total，避免短 PDF（如 "Hello world"）被误判。
_SCAN_PER_PAGE_THRESHOLD = 10


def _parse_page_range(spec: str, total: int) -> list[int]:
    """解析 page_range 字符串到 1-based 页码列表.

    支持："1-3" / "1,3,5" / "1-" / "-3" / "2"。
    """
    if not spec or not spec.strip():
        return list(range(1, total + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            start = int(left) if left.strip() else 1
            end = int(right) if right.strip() else total
        else:
            start = end = int(part)
        if start < 1 or end < 1 or start > end:
            raise ValueError(f"非法的页码区间：{part}")
        for p in range(start, min(end, total) + 1):
            pages.add(p)
    return sorted(pages)


@tool(
    name="pdf_read",
    description=(
        "读取本地 PDF 文件并提取纯文本。"
        "适合：作业题目 PDF / 教材章节 / 论文。"
        "返回格式：每页前加 [Page N] 标记。"
        "扫描件（无可抽取文本）会返回明确提示而不是空字符串。"
    ),
)
def pdf_read(
    path: str,
    page_range: str = "",
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str:
    """读取 PDF 抽取文本.

    :param path: PDF 文件路径（绝对或相对工作目录）.
    :param page_range: 页码范围，默认全部。示例 "1-3" / "1,3,5" / "2-".
    :param max_chars: 累计字符数上限（默认 8000，硬上限 65536）.
    """
    if not isinstance(path, str) or not path.strip():
        return json.dumps({"error": "path 不能为空"}, ensure_ascii=False)
    p = Path(path).expanduser()
    if not p.exists():
        return json.dumps(
            {"error": f"PDF 文件不存在：{path}"}, ensure_ascii=False
        )
    if not p.is_file():
        return json.dumps({"error": f"不是文件：{path}"}, ensure_ascii=False)

    if not isinstance(max_chars, int) or max_chars < 1:
        max_chars = _DEFAULT_MAX_CHARS
    max_chars = min(max_chars, _HARD_MAX_CHARS)

    try:
        from pypdf import PdfReader
    except ImportError:
        return json.dumps(
            {"error": "未安装 pypdf，请执行: uv add pypdf"}, ensure_ascii=False
        )

    try:
        reader = PdfReader(str(p))
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"error": f"PDF 解析失败：{type(e).__name__}: {e}"}, ensure_ascii=False
        )

    total = len(reader.pages)
    if total == 0:
        return json.dumps({"error": "PDF 没有页面"}, ensure_ascii=False)

    try:
        pages = _parse_page_range(page_range, total)
    except (ValueError, TypeError) as e:
        return json.dumps(
            {"error": f"page_range 解析失败：{e}"}, ensure_ascii=False
        )

    parts: list[str] = []
    accumulated = 0
    truncated = False
    max_page_chars = 0
    for idx in pages:
        try:
            page_text = (reader.pages[idx - 1].extract_text() or "").strip()
        except Exception as e:  # noqa: BLE001
            page_text = f"[页面 {idx} 解析失败：{e}]"
        max_page_chars = max(max_page_chars, len(page_text))

        block = f"[Page {idx}]\n{page_text}\n"
        remaining = max_chars - accumulated
        if remaining <= 0:
            truncated = True
            break
        if len(block) > remaining:
            parts.append(block[:remaining] + "\n...[truncated]")
            truncated = True
            break
        parts.append(block)
        accumulated += len(block)

    if max_page_chars < _SCAN_PER_PAGE_THRESHOLD:
        return (
            f"[pdf_read] 该 PDF（共 {total} 页，已扫描页 {len(pages)}）"
            f"几乎抽不到文字（最大单页 {max_page_chars} 字符），"
            "看起来是扫描件 / 纯图像 PDF。\n"
            "请等待 Task 009 的 image_ocr 工具支持，或先用其它 OCR 工具转成纯文本 PDF。"
        )

    header = (
        f"[pdf_read] 文件：{p.name} ｜ 共 {total} 页 ｜ "
        f"本次返回页：{','.join(str(i) for i in pages)} ｜ "
        f"截断：{'是' if truncated else '否'}\n\n"
    )
    _log.info(
        f"pdf_read: {p.name} pages={len(pages)}/{total} chars={accumulated} truncated={truncated}"
    )
    return header + "".join(parts)
