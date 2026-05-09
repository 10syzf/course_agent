"""pdf_read 工具测试：单页 / 多页 / 范围 / 截断 / 扫描件 / 错误路径."""

from __future__ import annotations

from pathlib import Path

import pytest

from course_agent.tools.pdf_tools import _parse_page_range, pdf_read


def _make_pdf(tmp_path: Path, pages: list[str], name: str = "t.pdf") -> Path:
    """生成一个最小可被 pypdf 解析的多页 PDF."""
    objects: list[bytes] = []

    def add(b: bytes) -> int:
        objects.append(b)
        return len(objects)  # 1-based id

    # 占位 catalog / pages 节点，先放后面回填 kids
    catalog_id = add(b"")
    pages_id = add(b"")
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids: list[int] = []
    for text in pages:
        # 转义文本中的特殊字符
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = f"BT /F1 14 Tf 72 720 Td ({safe}) Tj ET".encode()
        content_id = add(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
        page_obj = (
            b"<< /Type /Page /Parent " + str(pages_id).encode() + b" 0 R "
            b"/MediaBox [0 0 612 792] "
            b"/Contents " + str(content_id).encode() + b" 0 R "
            b"/Resources << /Font << /F1 " + str(font_id).encode() + b" 0 R >> >> >>"
        )
        page_ids.append(add(page_obj))

    kids_str = b" ".join(f"{pid} 0 R".encode() for pid in page_ids)
    objects[pages_id - 1] = (
        b"<< /Type /Pages /Kids [" + kids_str + b"] /Count " + str(len(page_ids)).encode() + b" >>"
    )
    objects[catalog_id - 1] = b"<< /Type /Catalog /Pages " + str(pages_id).encode() + b" 0 R >>"

    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_pos = len(buf)
    buf += f"xref\n0 {len(objects) + 1}\n".encode()
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode()
    buf += (
        b"trailer\n<< /Size " + str(len(objects) + 1).encode()
        + b" /Root " + str(catalog_id).encode() + b" 0 R >>\n"
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    )

    p = tmp_path / name
    p.write_bytes(bytes(buf))
    return p


# ---------------------- _parse_page_range 单元测试 ----------------------

def test_parse_range_simple():
    assert _parse_page_range("1-3", 10) == [1, 2, 3]


def test_parse_range_open_ended():
    assert _parse_page_range("1-", 5) == [1, 2, 3, 4, 5]
    assert _parse_page_range("-3", 10) == [1, 2, 3]


def test_parse_range_comma_list():
    assert _parse_page_range("1,3,5", 10) == [1, 3, 5]


def test_parse_range_empty_means_all():
    assert _parse_page_range("", 4) == [1, 2, 3, 4]


def test_parse_range_invalid():
    with pytest.raises(ValueError):
        _parse_page_range("3-1", 10)


# ---------------------- pdf_read 集成测试 ----------------------

def test_read_single_page(tmp_path):
    pdf = _make_pdf(tmp_path, ["This is a binary search homework"])
    out = pdf_read(str(pdf))
    assert "[Page 1]" in out
    assert "binary search" in out
    assert "共 1 页" in out


def test_read_multi_page(tmp_path):
    pdf = _make_pdf(
        tmp_path,
        [
            "Question 1: implement bubble sort",
            "Question 2: prove worst case complexity",
            "Question 3: write unit tests",
        ],
    )
    out = pdf_read(str(pdf))
    assert "[Page 1]" in out
    assert "[Page 2]" in out
    assert "[Page 3]" in out
    assert "bubble sort" in out
    assert "complexity" in out


def test_read_page_range(tmp_path):
    pdf = _make_pdf(tmp_path, [f"Question {i}" for i in range(1, 6)])
    out = pdf_read(str(pdf), page_range="2-3")
    assert "[Page 2]" in out and "[Page 3]" in out
    assert "[Page 1]" not in out
    assert "[Page 5]" not in out


def test_read_truncation(tmp_path):
    pdf = _make_pdf(tmp_path, ["A short page"])
    out = pdf_read(str(pdf), max_chars=10)
    assert "截断：是" in out
    assert "[truncated]" in out


def test_read_scan_pdf_friendly_hint(tmp_path):
    """全部页面都是空文本（模拟扫描件）→ 应给友好提示."""
    pdf = _make_pdf(tmp_path, ["", ""])
    out = pdf_read(str(pdf))
    assert "扫描件" in out or "纯图像" in out
    assert "Task 009" in out


def test_read_file_not_exist():
    out = pdf_read("/tmp/not-exist-pdf-12345.pdf")
    assert "不存在" in out


def test_read_empty_path():
    out = pdf_read("")
    assert "不能为空" in out


def test_read_invalid_range(tmp_path):
    pdf = _make_pdf(tmp_path, ["Hello world this is page one"])
    out = pdf_read(str(pdf), page_range="3-1")
    assert "解析失败" in out
