"""pdf_read 扫描件 → image_ocr 兜底的回归测试（Task 009 Step 5）."""

from __future__ import annotations

from pathlib import Path

from course_agent.tools import pdf_tools as pdf_mod
from course_agent.tools.pdf_tools import _try_ocr_first_page, pdf_read

# 复用现有 pdf 制造工厂
from tests.test_pdf_tools import _make_pdf


def test_scan_pdf_with_ocr_fallback_success(tmp_path: Path, monkeypatch):
    """扫描件 PDF + mock 上 _try_ocr_first_page → 应在结果里看到 [Page 1 (OCR)] 段."""
    pdf = _make_pdf(tmp_path, ["", ""])  # 全空文本 → 触发扫描件分支

    monkeypatch.setattr(
        pdf_mod, "_try_ocr_first_page", lambda p: "已抽出的中文：第一题 求积分"
    )

    out = pdf_read(str(pdf))
    assert "扫描件" in out or "纯图像" in out
    assert "[Page 1 (OCR)]" in out
    assert "第一题 求积分" in out


def test_scan_pdf_with_ocr_fallback_disabled(tmp_path: Path, monkeypatch):
    """扫描件 PDF + OCR 兜底返回 None（pypdfium2 缺失或 VL 未配）→ 给出明确提示."""
    pdf = _make_pdf(tmp_path, ["", ""])

    monkeypatch.setattr(pdf_mod, "_try_ocr_first_page", lambda p: None)

    out = pdf_read(str(pdf))
    assert "扫描件" in out or "纯图像" in out
    assert "兜底 OCR 未启用" in out
    assert "[Page 1 (OCR)]" not in out


def test_try_ocr_first_page_handles_missing_pypdfium2(monkeypatch, tmp_path: Path):
    """模拟 pypdfium2 未安装 → _try_ocr_first_page 应安全返回 None，不抛异常."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pypdfium2":
            raise ImportError("module not found")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    pdf = _make_pdf(tmp_path, [""])
    result = _try_ocr_first_page(pdf)
    assert result is None


def test_normal_text_pdf_skips_ocr_branch(tmp_path: Path, monkeypatch):
    """正常文本 PDF 不应触发 OCR 兜底（_try_ocr_first_page 不应被调用）."""
    pdf = _make_pdf(tmp_path, ["This is a normal text page with some content"])

    called = {"n": 0}

    def spy(p):
        called["n"] += 1
        return "should-not-be-called"

    monkeypatch.setattr(pdf_mod, "_try_ocr_first_page", spy)

    out = pdf_read(str(pdf))
    assert called["n"] == 0
    assert "[Page 1]" in out
    assert "normal text" in out
