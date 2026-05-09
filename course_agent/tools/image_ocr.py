"""图片 OCR 工具：调用多模态 LLM (Qwen-VL / GPT-4V / Claude Vision) 抽取图片中的文字.

⚠️ 当前文件为 Task 009 Step 1 提交的**骨架**，完整实现见 Step 2。
   骨架阶段：
   - 已注册 `@tool` 到全局 Registry，方便上层 (AgentLoop / 测试 / doctor) 提前感知该工具的存在
   - 实际调用会返回 `[image_ocr] (Task 009 Step 2 实现中) ...` 的占位提示
   - 不抛异常、不破坏现有 AgentLoop 行为

实现路线（Step 2 完成）：
  ① path / url 自动判别 + httpx 下载到临时文件
  ② 读字节 → base64 → data URL（OpenAI 多模态消息格式）
  ③ 调多模态 LLM（base_url + model 走 .env 的 VL_* 配置）
  ④ 失败时降级：返回 "[image_ocr] 模型未配置或调用失败：..."
  ⑤ 输出截断（≤ 16 KB）
"""

from __future__ import annotations

import os
from pathlib import Path

from course_agent.logger import get_logger
from course_agent.tools.registry import tool

_log = get_logger("image_ocr")

_DEFAULT_PROMPT = "请抽取图片中的全部文字，保留换行和公式格式；如果有手写内容请尽可能识别。"
_MAX_OUTPUT_CHARS = 16 * 1024


def _vl_configured() -> bool:
    """检测是否配置了多模态模型（VL_MODEL 至少要有）."""
    return bool(os.getenv("VL_MODEL", "").strip())


@tool(
    name="image_ocr",
    description=(
        "识别图片中的文字（含手写、板书、印刷体、公式）。"
        "输入图片本地路径或 http(s) URL，返回纯文本。"
        "适用于：学生拍的题目截图 / 板书照片 / 扫描件单页。"
    ),
)
def image_ocr(path_or_url: str, prompt: str = "") -> str:
    """图片 OCR 工具骨架（Task 009 Step 1）.

    Args:
        path_or_url: 图片本地路径或 http(s) URL。
        prompt: 给多模态模型的指令；为空时使用默认 prompt。

    Returns:
        识别出的纯文本；未配置 VL 时返回友好降级提示。
    """
    target = path_or_url.strip()
    if not target:
        return "[image_ocr] 入参 path_or_url 为空，请提供图片本地路径或 http(s) URL。"

    if not _vl_configured():
        return (
            "[image_ocr] 多模态模型未配置（缺少 VL_MODEL 环境变量），跳过 OCR。\n"
            "  → 请在 .env 中配置 VL_MODEL / VL_BASE_URL / VL_API_KEY 三项，"
            "或参考 .env.example 注释。"
        )

    is_url = target.startswith(("http://", "https://"))
    if not is_url:
        p = Path(target).expanduser()
        if not p.exists():
            return f"[image_ocr] 文件不存在：{p}"

    _ = prompt or _DEFAULT_PROMPT
    _log.warning(f"image_ocr 骨架被调用 (Task 009 Step 2 尚未实现)：target={target}")
    return (
        "[image_ocr] (Task 009 Step 2 实现中) 已定位到目标："
        f"{target}\n  → 真实多模态调用将在 Step 2 接入。"
    )
