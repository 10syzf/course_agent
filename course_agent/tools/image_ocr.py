"""图片 OCR 工具：调用多模态 LLM (Qwen-VL / GPT-4V / Claude Vision) 抽取图片中的文字.

实现要点：
  ① path / url 自动判别：URL 用 httpx 下载到内存；本地路径直接读字节
  ② 字节 → base64 → data URL（OpenAI 多模态消息格式）
  ③ 调多模态 LLM（base_url + model 走 .env 的 VL_* 配置；缺什么就回退到 OPENAI_*）
  ④ 失败时降级：返回 "[image_ocr] 模型未配置或调用失败：..."，**不抛异常**
  ⑤ 输出截断（≤ 16 KB）

兼容性：用 `from openai import OpenAI` 而非 `OpenAILLM`，
       因为多模态消息格式（content 是 list 而非 str）当前我们的 LLMMessage 没有原生支持。
       走 SDK 直调，base_url 兼容 DashScope / OpenAI / DeepSeek-VL 等。
"""

from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path

from course_agent.logger import get_logger
from course_agent.tools.registry import tool

_log = get_logger("image_ocr")

_DEFAULT_PROMPT = "请抽取图片中的全部文字，保留换行和公式格式；如果有手写内容请尽可能识别。"
_MAX_OUTPUT_CHARS = 16 * 1024
_DOWNLOAD_TIMEOUT = 30.0
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB 上限，防止把超大图整张塞给 LLM


def _get_vl_config() -> tuple[str, str | None, str | None]:
    """读取多模态模型配置：(model, base_url, api_key)，VL_* 优先 OPENAI_* 兜底."""
    model = os.getenv("VL_MODEL", "").strip()
    base_url = (os.getenv("VL_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").strip() or None
    api_key = (os.getenv("VL_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip() or None
    return model, base_url, api_key


def _vl_configured() -> bool:
    """检测是否配置了多模态模型（VL_MODEL 至少要有）."""
    model, _, _ = _get_vl_config()
    return bool(model)


def _read_image_bytes(target: str) -> tuple[bytes, str]:
    """读图片字节 + 推断 MIME。失败抛 ValueError."""
    if target.startswith(("http://", "https://")):
        try:
            import httpx
        except ImportError as e:
            raise ValueError(f"未安装 httpx：{e}") from e
        with httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(target)
            resp.raise_for_status()
            data = resp.content
            mime = resp.headers.get("content-type", "").split(";")[0].strip() or "image/png"
    else:
        p = Path(target).expanduser()
        if not p.exists():
            raise ValueError(f"文件不存在：{p}")
        data = p.read_bytes()
        mime = mimetypes.guess_type(str(p))[0] or "image/png"

    if len(data) == 0:
        raise ValueError("图片为空字节")
    if len(data) > _MAX_IMAGE_BYTES:
        raise ValueError(
            f"图片过大 ({len(data) / 1024 / 1024:.1f}MB > {_MAX_IMAGE_BYTES // 1024 // 1024}MB)"
        )
    return data, mime


def _build_data_url(data: bytes, mime: str) -> str:
    """字节 → data URL（OpenAI 多模态消息格式）."""
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _call_vl(
    data_url: str,
    prompt: str,
    model: str,
    base_url: str | None,
    api_key: str | None,
) -> str:
    """调多模态 LLM；失败抛原生异常，由上层 try."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("未安装 openai SDK") from e

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        max_tokens=2048,
        temperature=0.0,  # OCR 走确定性输出
    )
    text = (resp.choices[0].message.content or "").strip()
    return text


@tool(
    name="image_ocr",
    description=(
        "识别图片中的文字（含手写、板书、印刷体、公式）。"
        "输入图片本地路径或 http(s) URL，返回纯文本。"
        "适用于：学生拍的题目截图 / 板书照片 / 扫描件单页。"
    ),
)
def image_ocr(path_or_url: str, prompt: str = "") -> str:
    """图片 OCR 工具.

    Args:
        path_or_url: 图片本地路径或 http(s) URL。
        prompt: 给多模态模型的指令；为空时使用默认 prompt。

    Returns:
        识别出的纯文本（最长 16 KB）；未配置 VL 或调用失败时返回友好降级提示。
    """
    target = (path_or_url or "").strip()
    if not target:
        return "[image_ocr] 入参 path_or_url 为空，请提供图片本地路径或 http(s) URL。"

    if not _vl_configured():
        return (
            "[image_ocr] 多模态模型未配置（缺少 VL_MODEL 环境变量），跳过 OCR。\n"
            "  → 请在 .env 中配置 VL_MODEL / VL_BASE_URL / VL_API_KEY 三项，"
            "或参考 .env.example 注释。"
        )

    model, base_url, api_key = _get_vl_config()
    used_prompt = (prompt or "").strip() or _DEFAULT_PROMPT

    # ① 读字节
    try:
        data, mime = _read_image_bytes(target)
    except ValueError as e:
        return f"[image_ocr] 读取图片失败：{e}"
    except Exception as e:  # noqa: BLE001  网络错误等
        return f"[image_ocr] 下载图片失败：{type(e).__name__}: {str(e)[:200]}"

    _log.info(
        f"image_ocr: target={target[:60]!r} bytes={len(data)} mime={mime} model={model}"
    )

    # ② 转 data URL
    data_url = _build_data_url(data, mime)

    # ③ 调多模态 LLM
    try:
        text = _call_vl(data_url, used_prompt, model, base_url, api_key)
    except Exception as e:  # noqa: BLE001  覆盖 401/超时/网络等
        _log.warning(f"image_ocr 多模态调用失败：{type(e).__name__}: {e}")
        return (
            f"[image_ocr] 多模态调用失败（{type(e).__name__}）：{str(e)[:300]}\n"
            "  → 请检查 VL_MODEL / VL_API_KEY / VL_BASE_URL 是否匹配；"
            "也可以先用 `course-agent doctor` 自检。"
        )

    if not text:
        return "[image_ocr] 模型返回空文本，可能图片质量过低或不含可识别文字。"

    # ④ 截断
    if len(text) > _MAX_OUTPUT_CHARS:
        text = text[:_MAX_OUTPUT_CHARS] + "\n...[truncated]"

    return text
