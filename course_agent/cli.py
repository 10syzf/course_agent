"""Course Agent CLI 入口."""

from __future__ import annotations

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


if __name__ == "__main__":
    app()
