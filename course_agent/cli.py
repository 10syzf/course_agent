"""Course Agent CLI 入口."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from course_agent.config import get_config
from course_agent.core import AgentLoop
from course_agent.llm import create_llm
from course_agent.logger import setup_logger
from course_agent.tools import get_registry

app = typer.Typer(help="Course Agent - 帮助学生完成课程作业的智能 Agent (MVP)")
console = Console()


@app.command()
def chat(
    query: str = typer.Argument(..., help="学生提出的问题或作业描述"),
    show_trace: bool = typer.Option(False, "--trace", help="显示 Agent 执行 trace"),
    max_steps: int | None = typer.Option(None, "--max-steps", help="覆盖最大步数"),
) -> None:
    """单轮对话：发送一个问题，Agent 返回答案."""
    setup_logger()
    cfg = get_config()

    llm = create_llm(cfg.llm)
    loop = AgentLoop(
        llm=llm,
        max_steps=max_steps or cfg.agent.max_steps,
    )

    console.print(
        Panel.fit(
            f"[bold cyan]Provider[/bold cyan]: {cfg.llm.provider}  "
            f"[bold cyan]Model[/bold cyan]: {cfg.llm.model}  "
            f"[bold cyan]Tools[/bold cyan]: {', '.join(get_registry().list_names())}",
            title="Course Agent",
        )
    )
    console.print(f"[bold yellow]>>> 用户[/bold yellow] {query}\n")

    result = loop.run(query)

    if show_trace:
        table = Table(title="执行 Trace", show_lines=True)
        table.add_column("Step", style="cyan", no_wrap=True)
        table.add_column("Kind", style="magenta")
        table.add_column("Content", style="white")
        for entry in result.trace:
            table.add_row(
                str(entry["step"]),
                entry["kind"],
                entry["content"][:200],
            )
        console.print(table)

    console.print(
        Panel.fit(
            result.answer,
            title=f"[bold green]回答[/bold green]（共 {result.steps} 步）",
        )
    )


@app.command(name="tools")
def list_tools() -> None:
    """列出所有已注册的工具."""
    setup_logger()
    reg = get_registry()
    table = Table(title="已注册工具", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Parameters", style="yellow")
    for t in reg.all():
        params = ", ".join(t.parameters.get("properties", {}).keys())
        table.add_row(t.name, t.description, params)
    console.print(table)


@app.command()
def version() -> None:
    """显示版本号."""
    from course_agent import __version__

    console.print(f"course-agent [bold cyan]v{__version__}[/bold cyan]")


@app.command()
def ui(
    host: str = typer.Option("127.0.0.1", "--host", help="绑定的主机地址"),
    port: int = typer.Option(8000, "--port", "-p", help="Web UI 端口"),
    headless: bool = typer.Option(False, "--headless", help="不自动打开浏览器"),
) -> None:
    """启动浏览器 Web UI（基于 Chainlit）."""
    import subprocess
    import sys
    from pathlib import Path

    setup_logger()
    cfg = get_config()

    ui_entry = Path(__file__).resolve().parent / "ui" / "chainlit_app.py"
    if not ui_entry.exists():
        console.print(f"[bold red]找不到 UI 入口：{ui_entry}[/bold red]")
        raise typer.Exit(code=1)

    # 显示 key 尾号 + 长度，便于排查"OS env 残留旧 key 污染 .env"这类诡异 401
    key_info = "（未配置）"
    if cfg.llm.api_key:
        k = cfg.llm.api_key
        key_info = f"...{k[-6:]} (len={len(k)})"

    console.print(
        Panel.fit(
            f"[bold cyan]Provider[/bold cyan]: {cfg.llm.provider}  "
            f"[bold cyan]Model[/bold cyan]: {cfg.llm.model}\n"
            f"[bold cyan]API Key[/bold cyan]: {key_info}  "
            f"[bold cyan]Base URL[/bold cyan]: {cfg.llm.base_url or '(default)'}\n"
            f"[bold green]Web UI 地址[/bold green]: http://{host}:{port}",
            title="🚀 Course Agent Web UI",
        )
    )

    cmd = [
        sys.executable,
        "-m",
        "chainlit",
        "run",
        str(ui_entry),
        "--host",
        host,
        "--port",
        str(port),
    ]
    if headless:
        cmd.append("--headless")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        console.print("\n[yellow]已停止 Web UI[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Chainlit 启动失败：{e}[/bold red]")
        raise typer.Exit(code=e.returncode) from e


# ---------------------------------------------------------------------------
# doctor: 启动自检 —— Task 008 §4.3
# ---------------------------------------------------------------------------

_DOCTOR_REQUIRED_PKGS = (
    "openai",
    "chainlit",
    "chromadb",
    "pypdf",
    "trafilatura",
    "loguru",
    "rich",
    "typer",
    "yaml",
    "pydantic_settings",
)


def _check_python_version() -> tuple[str, str, str]:
    import sys

    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) < (3, 11):
        return ("❌", ver, "需要 Python >=3.11，请重建虚拟环境")
    if (v.major, v.minor) >= (3, 14):
        return ("⚠️", ver, "Python 3.14 与 chainlit/anyio 已知不兼容；建议锁 3.13")
    return ("✅", ver, "")


def _check_deps() -> tuple[str, str, str]:
    import importlib

    missing: list[str] = []
    for name in _DOCTOR_REQUIRED_PKGS:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        return ("❌", f"缺少 {len(missing)} 个", f"请执行 `uv sync` 后重试，缺失：{', '.join(missing)}")
    return ("✅", f"{len(_DOCTOR_REQUIRED_PKGS)} 个就位", "")


def _check_env_file() -> tuple[str, str, str]:
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    env_file = root / ".env"
    if not env_file.exists():
        return ("⚠️", "不存在", "请 `cp .env.example .env` 后填入 OPENAI_API_KEY")
    size = env_file.stat().st_size
    return ("✅", f"存在 ({size} bytes)", "")


def _check_api_key(cfg: Any) -> tuple[str, str, str]:
    import os

    key = cfg.llm.api_key
    if not key:
        return ("❌", "未配置", "请在 .env 中设置 OPENAI_API_KEY=sk-xxx")
    tail = f"...{key[-6:]} (len={len(key)})"
    os_key = os.environ.get("OPENAI_API_KEY")
    extra = ""
    if os_key and os_key != key:
        # 因为 load_dotenv override=True，.env 已经赢了，但提示用户存在残留
        extra = "⚠️ shell 也设置了 OPENAI_API_KEY 但已被 .env override"
    return ("✅", tail, extra)


def _check_llm_chat(cfg: Any) -> tuple[str, str, str]:
    import time as _t

    if cfg.llm.provider == "mock" or not cfg.llm.api_key:
        return ("⚠️", "跳过", "provider=mock 或未配置 key，跳过真实连通性测试")
    try:
        from course_agent.llm.base import LLMMessage
        llm = create_llm(cfg.llm)
        t0 = _t.perf_counter()
        resp = llm.chat([LLMMessage(role="user", content="ping")])
        dt = int((_t.perf_counter() - t0) * 1000)
        if resp.finish_reason == "error":
            return ("❌", f"{cfg.llm.model} 失败", resp.content[:200])
        return ("✅", f"{cfg.llm.model} 200 OK ({dt}ms)", "")
    except Exception as e:  # noqa: BLE001
        return ("❌", f"{type(e).__name__}", str(e)[:200])


def _check_llm_embedding(cfg: Any) -> tuple[str, str, str]:
    import os
    import time as _t

    if not cfg.llm.api_key:
        return ("⚠️", "跳过", "未配置 key；记忆系统将自动降级为 HashEmbedder")
    try:
        from course_agent.memory.embedders import OpenAIEmbedder
        model = os.getenv("OPENAI_EMBEDDING_MODEL")
        if not model:
            base = cfg.llm.base_url or ""
            model = "text-embedding-3-small" if "openai.com" in base else "text-embedding-v3"
        emb = OpenAIEmbedder(model=model, api_key=cfg.llm.api_key, base_url=cfg.llm.base_url)
        t0 = _t.perf_counter()
        v = emb.embed("ping")
        dt = int((_t.perf_counter() - t0) * 1000)
        return ("✅", f"{model} 200 OK ({dt}ms, dim={len(v)})", "")
    except Exception as e:  # noqa: BLE001
        return ("⚠️", f"{type(e).__name__}", f"嵌入不可用，将自动降级 HashEmbedder：{str(e)[:160]}")


def _check_tools() -> tuple[str, str, str]:
    try:
        names = get_registry().list_names()
        return ("✅", f"{len(names)} 个", ", ".join(names))
    except Exception as e:  # noqa: BLE001
        return ("❌", "注册失败", str(e)[:200])


# 用 stdlib 现场合成一张 64×64 白色灰度 PNG（约 100 字节）做探活。
# 不能用 1×1：阿里百炼 Qwen-VL 等服务端对最小宽高有限制（实测拒 height:1/width:1）。
# 64×64 是各家多模态 API 都接受的安全下限，且生成成本几乎为 0。
def _make_probe_png() -> bytes:
    """用纯 stdlib（struct + zlib）合成一张 64×64 白色灰度 PNG."""
    import struct
    import zlib

    width = height = 64
    sig = b"\x89PNG\r\n\x1a\n"

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)  # 8-bit 灰度
    raw = b"".join(b"\x00" + b"\xff" * width for _ in range(height))
    idat = zlib.compress(raw, level=9)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _check_vl_chat() -> tuple[str, str, str]:
    """第 8 项：多模态 LLM 连通性（Task 009）.

    走的是 image_ocr 工具背后同一份 VL 配置；用 64×64 PNG 做最小代价探活，
    既验证 VL_MODEL / VL_API_KEY / VL_BASE_URL 三件套，又确认 base_url 支持
    多模态消息格式 (content=[{type:text}, {type:image_url}])。
    """
    import time as _t

    from course_agent.tools.image_ocr import (
        _build_data_url,
        _call_vl,
        _get_vl_config,
        _vl_configured,
    )

    if not _vl_configured():
        return (
            "⚠️",
            "跳过",
            "未配置 VL_MODEL；image_ocr 与 pdf_read 扫描兜底将自动降级",
        )
    model, base_url, api_key = _get_vl_config()
    if not api_key:
        return ("❌", "缺 API Key", "请在 .env 中配置 VL_API_KEY 或 OPENAI_API_KEY")
    try:
        data = _make_probe_png()
        data_url = _build_data_url(data, "image/png")
        t0 = _t.perf_counter()
        text = _call_vl(data_url, "describe in one word", model, base_url, api_key)
        dt = int((_t.perf_counter() - t0) * 1000)
        snippet = (text or "").strip().replace("\n", " ")[:30]
        return ("✅", f"{model} 200 OK ({dt}ms)", f"返回: {snippet!r}")
    except Exception as e:  # noqa: BLE001
        return (
            "❌",
            f"{type(e).__name__}",
            f"{str(e)[:160]}（请检查 VL_BASE_URL 是否支持多模态）",
        )


@app.command()
def doctor() -> None:
    """启动自检：Python / 依赖 / .env / Key / LLM / Embedding / VL / Tools 八项检查."""
    setup_logger()

    console.print(Panel.fit("🩺 Course Agent 健康检查", style="bold cyan"))

    cfg = get_config()

    checks: list[tuple[str, Callable[[], tuple[str, str, str]]]] = [
        ("Python 版本", lambda: _check_python_version()),
        ("关键依赖", lambda: _check_deps()),
        (".env 文件", lambda: _check_env_file()),
        ("OPENAI_API_KEY", lambda: _check_api_key(cfg)),
        ("LLM 连通性 (chat)", lambda: _check_llm_chat(cfg)),
        ("LLM 连通性 (embedding)", lambda: _check_llm_embedding(cfg)),
        ("VL 多模态连通性", lambda: _check_vl_chat()),
        ("工具注册", lambda: _check_tools()),
    ]

    table = Table(show_lines=False, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("项目", style="cyan", no_wrap=True)
    table.add_column("状态", width=4)
    table.add_column("详情", style="white")
    table.add_column("提示", style="yellow")

    pass_count = 0
    fail_count = 0
    warn_count = 0
    total = len(checks)

    for i, (label, fn) in enumerate(checks, 1):
        try:
            status, detail, hint = fn()
        except Exception as e:  # noqa: BLE001  每步独立 try，全部跑完再汇总
            status, detail, hint = ("❌", "异常", str(e)[:200])

        if status == "✅":
            pass_count += 1
        elif status == "⚠️":
            warn_count += 1
        else:
            fail_count += 1

        table.add_row(f"{i}/{total}", label, status, detail, hint)

    console.print(table)

    summary = f"通过 {pass_count}/{total}  ｜  警告 {warn_count}  ｜  失败 {fail_count}"
    if fail_count == 0:
        console.print(Panel.fit(f"✨ {summary} —— 可以开始使用", style="bold green"))
    else:
        console.print(Panel.fit(f"⛔ {summary} —— 请先按上表提示修复", style="bold red"))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
