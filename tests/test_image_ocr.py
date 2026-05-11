"""image_ocr 工具测试：路径 / URL / 未配置降级 / mock VL / 边界与错误."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from course_agent.tools import image_ocr as ocr_mod
from course_agent.tools.image_ocr import (
    _build_data_url,
    _read_image_bytes,
    image_ocr,
)

# 1x1 PNG（67 bytes）
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
)


@pytest.fixture(autouse=True)
def _clean_vl_env(monkeypatch):
    """每个测试都从干净 VL 环境开始；测试自己 setenv."""
    for k in ("VL_MODEL", "VL_BASE_URL", "VL_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    yield


def test_image_ocr_empty_input_returns_friendly_hint():
    out = image_ocr("")
    assert "[image_ocr]" in out
    assert "为空" in out


def test_image_ocr_no_vl_config_degrades_gracefully(tmp_path: Path):
    """没配 VL_MODEL 时不应抛异常，而是返回友好降级提示."""
    img = tmp_path / "tiny.png"
    img.write_bytes(_TINY_PNG)
    out = image_ocr(str(img))
    assert "[image_ocr]" in out
    assert "VL_MODEL" in out


def test_image_ocr_path_not_found(monkeypatch):
    """配置了 VL 但文件不存在 → 走读图失败分支."""
    monkeypatch.setenv("VL_MODEL", "qwen-vl-plus")
    monkeypatch.setenv("VL_API_KEY", "sk-fake")
    out = image_ocr("/tmp/definitely-not-exist-image-99999.png")
    assert "[image_ocr]" in out
    assert "读取图片失败" in out or "文件不存在" in out


def test_image_ocr_calls_vl_with_mock(monkeypatch, tmp_path: Path):
    """正常路径：mock _call_vl 验证参数透传 + 返回拼装."""
    monkeypatch.setenv("VL_MODEL", "qwen-vl-mock")
    monkeypatch.setenv("VL_API_KEY", "sk-fake")
    monkeypatch.setenv("VL_BASE_URL", "https://example.com/v1")

    img = tmp_path / "tiny.png"
    img.write_bytes(_TINY_PNG)

    captured: dict[str, object] = {}

    def fake_call(data_url, prompt, model, base_url, api_key):
        captured["data_url_prefix"] = data_url[:30]
        captured["prompt"] = prompt
        captured["model"] = model
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        return "OCR 抽到的中文文字\n第二行"

    monkeypatch.setattr(ocr_mod, "_call_vl", fake_call)

    out = image_ocr(str(img), prompt="只抽汉字")
    assert "OCR 抽到的中文文字" in out
    assert captured["model"] == "qwen-vl-mock"
    assert captured["api_key"] == "sk-fake"
    assert captured["base_url"] == "https://example.com/v1"
    assert captured["prompt"] == "只抽汉字"
    assert str(captured["data_url_prefix"]).startswith("data:image/")


def test_image_ocr_truncates_huge_output(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("VL_MODEL", "qwen-vl-mock")
    monkeypatch.setenv("VL_API_KEY", "sk-fake")
    img = tmp_path / "tiny.png"
    img.write_bytes(_TINY_PNG)

    huge = "x" * (32 * 1024)  # 32KB > 16KB 上限
    monkeypatch.setattr(ocr_mod, "_call_vl", lambda *a, **k: huge)

    out = image_ocr(str(img))
    assert "[truncated]" in out
    assert len(out) < 17 * 1024


def test_image_ocr_empty_response(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("VL_MODEL", "qwen-vl-mock")
    monkeypatch.setenv("VL_API_KEY", "sk-fake")
    img = tmp_path / "tiny.png"
    img.write_bytes(_TINY_PNG)

    monkeypatch.setattr(ocr_mod, "_call_vl", lambda *a, **k: "")
    out = image_ocr(str(img))
    assert "[image_ocr]" in out
    assert "空文本" in out


def test_image_ocr_vl_call_failure_degrades(monkeypatch, tmp_path: Path):
    """VL 调用抛异常 → 不应崩溃，返回友好错误."""
    monkeypatch.setenv("VL_MODEL", "qwen-vl-mock")
    monkeypatch.setenv("VL_API_KEY", "sk-fake")
    img = tmp_path / "tiny.png"
    img.write_bytes(_TINY_PNG)

    def boom(*a, **k):
        raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(ocr_mod, "_call_vl", boom)
    out = image_ocr(str(img))
    assert "[image_ocr]" in out
    assert "多模态调用失败" in out
    assert "401" in out


def test_build_data_url_format():
    url = _build_data_url(_TINY_PNG, "image/png")
    assert url.startswith("data:image/png;base64,")
    # base64 round-trip
    payload = url.split(",", 1)[1]
    assert base64.b64decode(payload) == _TINY_PNG


def test_read_image_bytes_local_path(tmp_path: Path):
    img = tmp_path / "tiny.png"
    img.write_bytes(_TINY_PNG)
    data, mime = _read_image_bytes(str(img))
    assert data == _TINY_PNG
    assert mime == "image/png"
