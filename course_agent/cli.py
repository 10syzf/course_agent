"""Course Agent CLI 入口."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from course_agent.config import get_config
from course_agent.context import (
    compile_context,
    context_to_markdown,
    latest_context_path,
    load_context_artifact,
    profile_context,
    save_context_artifact,
)
from course_agent.llm import create_llm
from course_agent.logger import setup_logger
from course_agent.prompt import (
    compile_prompt,
    latest_prompt_path,
    load_prompt_artifact,
    profile_prompt,
    prompt_to_markdown,
    save_prompt_artifact,
)
from course_agent.runtime import (
    create_chat_runtime,
    create_runtime,
    create_session_runtime,
)
from course_agent.tools import get_registry

app = typer.Typer(help="Course Agent - 帮助学生完成课程作业的智能 Agent (MVP)")
console = Console()

# Task 010：错题本 CLI 子命令
mistakes_app = typer.Typer(help="错题本管理（Task 010）")
app.add_typer(mistakes_app, name="mistakes")

# Task 018：context CLI 子命令
context_app = typer.Typer(help="Context Inspect / Profile（Task 018）")
app.add_typer(context_app, name="context")


@mistakes_app.command("list")
def mistakes_list(
    tag: str = typer.Option("", "--tag", help="按标签过滤，例如 '线代'"),
    limit: int = typer.Option(20, "--limit", help="最多显示多少条（上限 200）"),
) -> None:
    """列出错题（按创建或下次复习时间升序）."""
    setup_logger()
    from course_agent.storage.mistake_db import list_mistakes_db

    rows = list_mistakes_db(tag=tag, due_only=False, limit=limit)
    if not rows:
        console.print("📭 错题本还是空的，去 Chainlit 或用工具写入第一道错题吧～")
        return
    table = Table(title=f"📓 错题本（共 {len(rows)} 条）", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("题目（截断 60）", style="white")
    table.add_column("标签", style="yellow")
    table.add_column("复习次数", style="magenta")
    table.add_column("下次复习", style="green")
    for r in rows:
        q = r["question"]
        q = q if len(q) <= 60 else q[:57] + "..."
        table.add_row(
            str(r["id"]),
            q,
            r.get("tags") or "-",
            str(r["repetitions"]),
            r["next_review_at"][:10],
        )
    console.print(table)


@mistakes_app.command("due")
def mistakes_due(
    limit: int = typer.Option(20, "--limit", help="最多显示多少条"),
) -> None:
    """列出今日待复习的错题."""
    setup_logger()
    from course_agent.storage.mistake_db import count_due_today, list_mistakes_db

    rows = list_mistakes_db(tag="", due_only=True, limit=limit)
    n = count_due_today()
    if not rows:
        console.print(f"🎉 今天暂无待复习错题（total due={n}）。")
        return
    table = Table(title=f"📅 今日待复习（共 {n} 道）", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("题目", style="white")
    table.add_column("标签", style="yellow")
    table.add_column("下次复习", style="green")
    for r in rows:
        q = r["question"]
        q = q if len(q) <= 80 else q[:77] + "..."
        table.add_row(str(r["id"]), q, r.get("tags") or "-", r["next_review_at"][:10])
    console.print(table)


@mistakes_app.command("review")
def mistakes_review(
    mistake_id: int = typer.Argument(..., help="错题 ID"),
    quality: int = typer.Argument(..., help="0-5：0=完全不会 / 5=秒答"),
) -> None:
    """对一道错题打分，更新 SM-2 间隔."""
    setup_logger()
    from course_agent.storage.mistake_db import review_mistake_db

    if quality < 0 or quality > 5:
        console.print("[bold red]quality 必须在 0-5 之间[/bold red]")
        raise typer.Exit(code=1)
    row = review_mistake_db(mistake_id, quality)
    if row is None:
        console.print(f"[bold red]找不到错题 #{mistake_id}[/bold red]")
        raise typer.Exit(code=1)
    console.print(
        Panel.fit(
            f"已对 #{mistake_id} 打分 {quality}。\n"
            f"下次复习：[bold green]{row['next_review_at'][:10]}[/bold green]\n"
            f"当前间隔：{row['interval_days']} 天\n"
            f"easiness：{row['easiness']:.2f}\n"
            f"连续答对：{row['repetitions']} 次",
            title="✅ 复习完成",
        )
    )


@app.command()
def chat(
    query: str = typer.Argument(..., help="学生提出的问题或作业描述"),
    show_trace: bool = typer.Option(False, "--trace", help="显示 Agent 执行 trace"),
    max_steps: int | None = typer.Option(None, "--max-steps", help="覆盖最大步数"),
    backend: str | None = typer.Option(
        None,
        "--backend",
        help="单 Agent chat backend：legacy | langgraph",
    ),
) -> None:
    """单轮对话：发送一个问题，Agent 返回答案."""
    setup_logger()
    cfg = get_config()

    llm = create_llm(cfg.llm)
    loop = create_chat_runtime(
        cfg,
        llm=llm,
        max_steps=max_steps or cfg.agent.max_steps,
        backend=backend,
    )

    console.print(
        Panel.fit(
            f"[bold cyan]Provider[/bold cyan]: {cfg.llm.provider}  "
            f"[bold cyan]Model[/bold cyan]: {cfg.llm.model}  "
            f"[bold cyan]Backend[/bold cyan]: {getattr(loop, 'backend', 'legacy')}  "
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
            title=(
                f"[bold green]回答[/bold green]（共 {result.steps} 步）"
                f"｜{getattr(result, 'runtime_kind', 'legacy_react')}"
            ),
        )
    )


replay_app = typer.Typer(help="Replay / Trace（Task 015）")
app.add_typer(replay_app, name="replay")


@replay_app.command("latest")
def replay_latest() -> None:
    """显示最近一次 replay 文件路径与摘要."""
    setup_logger()
    cfg = get_config()
    from course_agent.runtime.replay import latest_replay_path, load_replay_artifact

    path = latest_replay_path(cfg.runtime.trace_dir)
    if path is None:
        console.print("暂无 replay 文件。")
        raise typer.Exit(code=1)
    artifact = load_replay_artifact(path)
    console.print(
        Panel.fit(
            f"path={path}\nbackend={artifact.get('backend')}\n"
            f"runtime={artifact.get('runtime_kind')}\nsteps={artifact.get('steps')}\n"
            f"final={artifact.get('final_answer_summary', '')}",
            title="🔁 Latest Replay",
        )
    )


@replay_app.command("show")
def replay_show(path: str = typer.Argument(..., help="replay.json 路径")) -> None:
    """读取并展示指定 replay."""
    setup_logger()
    from course_agent.runtime.replay import artifact_to_markdown, load_replay_artifact

    artifact = load_replay_artifact(path)
    console.print(artifact_to_markdown(artifact))


@replay_app.command("export")
def replay_export(
    format: str = typer.Option("json", "--format", help="json | md"),
) -> None:
    """把最近一次 replay 再导出一份 JSON 或 Markdown."""
    setup_logger()
    cfg = get_config()
    from course_agent.runtime.replay import (
        export_replay_markdown,
        latest_replay_path,
        load_replay_artifact,
        save_replay_artifact,
    )

    latest = latest_replay_path(cfg.runtime.trace_dir)
    if latest is None:
        console.print("暂无 replay 文件。")
        raise typer.Exit(code=1)
    artifact = load_replay_artifact(latest)
    if format == "md":
        out = export_replay_markdown(artifact, trace_dir=cfg.runtime.trace_dir)
    else:
        out = save_replay_artifact(artifact, trace_dir=cfg.runtime.trace_dir)
    console.print(str(out))


benchmark_app = typer.Typer(help="Benchmark / Compare（Task 015）")
app.add_typer(benchmark_app, name="benchmark")

session_app = typer.Typer(help="Session / Resume（Task 016）")
app.add_typer(session_app, name="session")

prompt_app = typer.Typer(help="Prompt Inspect / Profile（Task 017）")
app.add_typer(prompt_app, name="prompt")


@benchmark_app.command("runtime")
def benchmark_runtime(
    backend: str = typer.Option("langgraph", "--backend", help="legacy | langgraph"),
    query: str = typer.Option("帮我算一下 (3+5)*2", "--query", help="benchmark query"),
) -> None:
    """跑一次单 backend runtime benchmark."""
    setup_logger()
    cfg = get_config()
    from course_agent.runtime.benchmark import run_runtime_benchmark

    row = run_runtime_benchmark(cfg, backend=backend, query=query)
    table = Table(title=f"Benchmark · {backend}", show_lines=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    for key in (
        "backend",
        "runtime_kind",
        "latency_ms",
        "steps",
        "tool_calls",
        "node_count",
        "replay_path",
    ):
        table.add_row(key, str(row.get(key)))
    console.print(table)


@benchmark_app.command("compare")
def benchmark_compare(
    query: str = typer.Option("帮我算一下 (3+5)*2", "--query", help="benchmark query"),
) -> None:
    """比较 legacy 与 langgraph chat runtime."""
    setup_logger()
    cfg = get_config()
    from course_agent.runtime.benchmark import compare_runtime_benchmarks

    rows = compare_runtime_benchmarks(cfg, query=query)
    table = Table(title="Runtime Compare", show_lines=False)
    table.add_column("Backend", style="cyan")
    table.add_column("Runtime", style="blue")
    table.add_column("Latency", justify="right")
    table.add_column("Steps", justify="right")
    table.add_column("Tool Calls", justify="right")
    table.add_column("Trace Count", justify="right")
    for row in rows:
        table.add_row(
            row["backend"],
            row["runtime_kind"],
            f"{row['latency_ms']}ms",
            str(row["steps"]),
            str(row["tool_calls"]),
            str(row["node_count"]),
        )
    console.print(table)


def _session_runtime():
    cfg = get_config()
    llm = create_llm(cfg.llm)
    return create_session_runtime(
        cfg,
        llm=llm,
        backend="langgraph",
    )


def _print_session_detail(session) -> None:
    status = getattr(getattr(session, "status", None), "value", session.status)
    console.print(
        Panel.fit(
            f"session_id={session.session_id}\n"
            f"title={session.title}\n"
            f"status={status}\n"
            f"runtime={session.runtime_kind}\n"
            f"backend={session.backend}\n"
            f"waiting_reason={session.waiting_reason or '-'}\n"
            f"replay={session.latest_replay_path or '-'}\n"
            f"answer={session.latest_answer or '-'}",
            title="Session Detail",
        )
    )


@session_app.command("start")
def session_start(
    query: str = typer.Argument(..., help="要启动的任务"),
) -> None:
    """创建并运行一个 stateful session."""
    setup_logger()
    import asyncio

    runtime = _session_runtime()
    result = asyncio.run(runtime.start(query))
    _print_session_detail(result.session)


@session_app.command("list")
def session_list() -> None:
    """列出全部 session."""
    setup_logger()
    runtime = _session_runtime()
    rows = runtime.list_sessions()
    if not rows:
        console.print("暂无 session。")
        return
    table = Table(title="Sessions", show_lines=False)
    table.add_column("ID", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Title", style="white")
    table.add_column("Updated", style="green")
    for row in rows:
        table.add_row(
            row.session_id,
            row.status.value if hasattr(row.status, "value") else str(row.status),
            row.title,
            row.updated_at,
        )
    console.print(table)


@session_app.command("show")
def session_show(
    session_id: str = typer.Argument(..., help="session id"),
) -> None:
    """查看某个 session 详情."""
    setup_logger()
    runtime = _session_runtime()
    session = runtime.get_session(session_id)
    if session is None:
        console.print("session 不存在。")
        raise typer.Exit(code=1)
    _print_session_detail(session)


@session_app.command("resume")
def session_resume(
    session_id: str = typer.Argument(..., help="session id"),
) -> None:
    """恢复一个等待审批的 session."""
    setup_logger()
    import asyncio

    runtime = _session_runtime()
    try:
        result = asyncio.run(runtime.resume(session_id))
    except Exception as e:  # noqa: BLE001
        console.print(f"resume 失败：{e}")
        raise typer.Exit(code=1) from e
    _print_session_detail(result.session)


@session_app.command("continue")
def session_continue(
    session_id: str = typer.Argument(..., help="session id"),
    user_input: str = typer.Option(..., "--input", help="补充信息"),
) -> None:
    """给 waiting session 追加人工输入后继续."""
    setup_logger()
    import asyncio

    runtime = _session_runtime()
    try:
        result = asyncio.run(runtime.continue_session(session_id, user_input))
    except Exception as e:  # noqa: BLE001
        console.print(f"continue 失败：{e}")
        raise typer.Exit(code=1) from e
    _print_session_detail(result.session)


@session_app.command("cancel")
def session_cancel(
    session_id: str = typer.Argument(..., help="session id"),
) -> None:
    """取消一个 session."""
    setup_logger()
    runtime = _session_runtime()
    try:
        session = runtime.cancel(session_id)
    except Exception as e:  # noqa: BLE001
        console.print(f"cancel 失败：{e}")
        raise typer.Exit(code=1) from e
    _print_session_detail(session)


def _resolve_role_prompt(role: str) -> str:
    role = role.strip().lower()
    if role == "planner":
        from course_agent.agent.planner import PLANNER_SYSTEM_PROMPT

        return PLANNER_SYSTEM_PROMPT
    if role == "solver":
        from course_agent.agent.solver import SOLVER_SYSTEM_PROMPT

        return SOLVER_SYSTEM_PROMPT
    if role == "critic":
        from course_agent.agent.critic import CRITIC_SYSTEM_PROMPT

        return CRITIC_SYSTEM_PROMPT
    if role == "examiner":
        from course_agent.agent.examiner import EXAMINER_SYSTEM_PROMPT

        return EXAMINER_SYSTEM_PROMPT
    return "你是 Course Agent，一个帮助学生完成课程作业的智能助手。"


def _build_prompt_envelope_for_cli(role: str, query: str):
    cfg = get_config()
    return compile_prompt(
        role=role,
        role_prompt=_resolve_role_prompt(role),
        user_input=query,
        mcp_notes={"enabled": cfg.mcp.enabled},
        task_notes={"source": "cli_prompt_command"},
    )


async def _build_context_envelope_for_cli(role: str, query: str):
    cfg = get_config()
    return await compile_context(
        role=role,
        role_prompt=_resolve_role_prompt(role),
        user_input=query,
        mcp_notes={"enabled": cfg.mcp.enabled},
        task_notes={"source": "cli_context_command"},
    )


@prompt_app.command("inspect")
def prompt_inspect(
    role: str = typer.Option("react", "--role", help="react | planner | solver | critic | examiner"),
    query: str = typer.Option("你好，请介绍一下你的能力", "--query", help="本次要编译的 query"),
) -> None:
    """查看当前完整 prompt 与分层内容."""
    setup_logger()
    cfg = get_config()
    envelope = _build_prompt_envelope_for_cli(role, query)
    path = save_prompt_artifact(envelope, prompt_dir=cfg.runtime.prompt_dir)
    console.print(
        Panel.fit(
            f"role={envelope.role}\n"
            f"static_hash={envelope.static_hash}\n"
            f"dynamic_hash={envelope.dynamic_hash}\n"
            f"path={path}",
            title="Prompt Inspect",
        )
    )
    console.print("## Static Prefix\n")
    console.print(envelope.static_prefix)
    console.print("\n## Dynamic Tail\n")
    console.print(envelope.dynamic_tail)


@prompt_app.command("latest")
def prompt_latest() -> None:
    """查看最近一次 prompt artifact."""
    setup_logger()
    cfg = get_config()
    path = latest_prompt_path(cfg.runtime.prompt_dir)
    if path is None:
        console.print("暂无 prompt artifact。")
        raise typer.Exit(code=1)
    envelope = load_prompt_artifact(path)
    console.print(prompt_to_markdown(envelope))


@prompt_app.command("profile")
def prompt_profile(
    role: str = typer.Option("react", "--role", help="react | planner | solver | critic | examiner"),
    query: str = typer.Option("你好，请介绍一下你的能力", "--query", help="本次要编译的 query"),
) -> None:
    """输出 static / dynamic prompt 占比."""
    setup_logger()
    envelope = _build_prompt_envelope_for_cli(role, query)
    row = profile_prompt(envelope)
    table = Table(title=f"Prompt Profile · {role}", show_lines=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    for key in (
        "role",
        "static_chars",
        "dynamic_chars",
        "full_chars",
        "static_ratio",
        "dynamic_ratio",
    ):
        table.add_row(key, str(row[key]))
    console.print(table)


@context_app.command("inspect")
def context_inspect(
    role: str = typer.Option("react", "--role", help="react | planner | solver | critic | examiner"),
    query: str = typer.Option("你好，请介绍一下你的能力", "--query", help="本次要编译的 query"),
) -> None:
    """查看当前 context section 与压缩结果."""
    setup_logger()
    cfg = get_config()
    import asyncio

    _, envelope = asyncio.run(_build_context_envelope_for_cli(role, query))
    path = save_context_artifact(envelope, context_dir=cfg.runtime.context_dir)
    console.print(
        Panel.fit(
            f"role={envelope.role}\n"
            f"total_chars={envelope.total_chars}\n"
            f"selected_chars={envelope.selected_chars}\n"
            f"path={path}",
            title="Context Inspect",
        )
    )
    console.print(context_to_markdown(envelope))


@context_app.command("latest")
def context_latest() -> None:
    """查看最近一次 context artifact."""
    setup_logger()
    cfg = get_config()
    path = latest_context_path(cfg.runtime.context_dir)
    if path is None:
        console.print("暂无 context artifact。")
        raise typer.Exit(code=1)
    envelope = load_context_artifact(path)
    console.print(context_to_markdown(envelope))


@context_app.command("profile")
def context_profile(
    role: str = typer.Option("react", "--role", help="react | planner | solver | critic | examiner"),
    query: str = typer.Option("你好，请介绍一下你的能力", "--query", help="本次要编译的 query"),
) -> None:
    """输出 context 长度、section 与来源占比."""
    setup_logger()
    import asyncio

    _, envelope = asyncio.run(_build_context_envelope_for_cli(role, query))
    row = profile_context(envelope)
    table = Table(title=f"Context Profile · {role}", show_lines=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    for key in (
        "role",
        "total_chars",
        "selected_chars",
        "section_count",
        "dropped_sections",
        "compression_saved_chars",
    ):
        table.add_row(key, str(row[key]))
    console.print(table)


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
def metrics(
    limit: int = typer.Option(50, "--limit", help="查询最近 N 次 LLM 调用（上限 500）"),
    show_raw: bool = typer.Option(
        False, "--raw", help="同时显示原始 N 条记录（按时间倒序）"
    ),
) -> None:
    """📊 可观测面板（Task 012/013）：展示 LLM + capability 调用统计."""
    setup_logger()
    from course_agent.observability.metrics import (
        aggregate_by_agent,
        aggregate_capabilities,
        get_db_path,
        load_recent,
        load_recent_capabilities,
    )

    limit = max(1, min(int(limit), 500))
    rows = aggregate_by_agent(limit)
    cap_rows = aggregate_capabilities(limit)
    if not rows and not cap_rows:
        console.print(
            Panel.fit(
                f"📭 暂无 metrics 数据（db={get_db_path()}）。\n"
                "跑几轮 Orchestrator / chat 后再来看。",
                title="📊 Course Agent Metrics",
            )
        )
    else:
        if rows:
            table = Table(
                title=f"📊 最近 {limit} 次 LLM 调用按 Agent 聚合",
                show_lines=False,
            )
            table.add_column("Agent", style="cyan", no_wrap=True)
            table.add_column("Backend", style="blue")
            table.add_column("调用数", style="magenta", justify="right")
            table.add_column("Tokens (in/out)", style="yellow", justify="right")
            table.add_column("平均时延", style="green", justify="right")
            table.add_column("错误率", style="red", justify="right")
            for r in rows:
                table.add_row(
                    r["agent_name"],
                    r.get("runtime_backend", "legacy"),
                    str(r["calls"]),
                    f"{r['prompt_tokens']}/{r['completion_tokens']}",
                    f"{r['avg_latency_ms']}ms",
                    f"{r['error_rate'] * 100:.1f}%",
                )
            console.print(table)

        if cap_rows:
            table2 = Table(
                title=f"🔌 最近 {limit} 次 Capability 调用聚合",
                show_lines=False,
            )
            table2.add_column("Name", style="cyan", no_wrap=True)
            table2.add_column("Kind", style="yellow")
            table2.add_column("Provider", style="blue")
            table2.add_column("调用数", style="magenta", justify="right")
            table2.add_column("平均时延", style="green", justify="right")
            table2.add_column("错误率", style="red", justify="right")
            for r in cap_rows:
                table2.add_row(
                    r["capability_name"],
                    r["capability_kind"],
                    r["provider_name"],
                    str(r["calls"]),
                    f"{r['avg_latency_ms']}ms",
                    f"{r['error_rate'] * 100:.1f}%",
                )
            console.print(table2)

    if show_raw:
        raw = load_recent(limit)
        t2 = Table(title=f"🧾 原始记录（最近 {len(raw)} 条）", show_lines=False)
        t2.add_column("#", style="dim")
        t2.add_column("Agent", style="cyan")
        t2.add_column("Backend", style="blue")
        t2.add_column("Model", style="blue")
        t2.add_column("in", justify="right")
        t2.add_column("out", justify="right")
        t2.add_column("latency", justify="right")
        t2.add_column("status")
        for i, r in enumerate(raw, 1):
            t2.add_row(
                str(i),
                r["agent_name"],
                r.get("runtime_backend", "legacy"),
                r["model"],
                str(r["prompt_tokens"]),
                str(r["completion_tokens"]),
                f"{r['latency_ms']}ms",
                r["status"],
            )
        console.print(t2)
        cap_raw = load_recent_capabilities(limit)
        if cap_raw:
            t3 = Table(title=f"🧩 Capability 原始记录（最近 {len(cap_raw)} 条）", show_lines=False)
            t3.add_column("#", style="dim")
            t3.add_column("Name", style="cyan")
            t3.add_column("Kind", style="yellow")
            t3.add_column("Provider", style="blue")
            t3.add_column("latency", justify="right")
            t3.add_column("status")
            for i, r in enumerate(cap_raw, 1):
                t3.add_row(
                    str(i),
                    r["capability_name"],
                    r["capability_kind"],
                    r["provider_name"],
                    f"{r['latency_ms']}ms",
                    r["status"],
                )
            console.print(t3)


def _build_capability_registry(cfg: Any):
    from course_agent.capabilities.adapters import build_default_capability_registry

    return build_default_capability_registry(
        tool_registry=get_registry(),
        mcp_cfg=cfg.mcp,
    )


@app.command()
def capabilities() -> None:
    """列出统一能力层中的全部能力（internal_tool / skill / mcp）."""
    setup_logger()
    cfg = get_config()
    reg = _build_capability_registry(cfg)
    rows = reg.list_all()
    table = Table(title="统一 Capability 列表", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Kind", style="yellow")
    table.add_column("Source", style="blue")
    table.add_column("Enabled", style="green")
    table.add_column("Description", style="white")
    for r in rows:
        table.add_row(
            r.name,
            r.kind.value,
            r.source,
            "yes" if r.enabled else "no",
            r.description[:80],
        )
    console.print(table)


skills_app = typer.Typer(help="Skill Runtime（Task 013）")
app.add_typer(skills_app, name="skills")


@skills_app.command("list")
def skills_list() -> None:
    """列出本地 Skill Runtime 中的所有 skill."""
    setup_logger()
    from course_agent.skills import get_skill_registry

    reg = get_skill_registry()
    table = Table(title="已注册 Skills", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Parameters", style="yellow")
    for sk in reg.all():
        params = ", ".join(sk.parameters.get("properties", {}).keys())
        table.add_row(sk.name, sk.description, params)
    console.print(table)


mcp_app = typer.Typer(help="MCP Adapter（Task 013）")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("list")
def mcp_list() -> None:
    """列出当前可见的 MCP 能力；未开启时友好提示."""
    setup_logger()
    cfg = get_config()
    if not cfg.mcp.enabled:
        console.print(
            Panel.fit(
                "MCP 当前未启用（`mcp.enabled=false`）。\n"
                "开启后可通过 `course-agent mcp list` 查看 mock / 真实 server 的工具。",
                title="🔌 MCP",
            )
        )
        return
    reg = _build_capability_registry(cfg)
    rows = [r for r in reg.list_all() if r.kind.value == "mcp"]
    table = Table(title="MCP 能力列表", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Source", style="blue")
    table.add_column("Description", style="white")
    for r in rows:
        table.add_row(r.name, r.source, r.description[:80])
    console.print(table)


@app.command()
def runtime(
    backend: str | None = typer.Option(None, "--backend", help="临时覆盖 backend：legacy | langgraph"),
) -> None:
    """显示当前 runtime backend / checkpoint / draw_graph 配置."""
    setup_logger()
    cfg = copy.deepcopy(get_config())
    if backend:
        cfg.runtime.backend = backend.strip().lower()
    console.print(
        Panel.fit(
            f"backend={cfg.runtime.backend}\ncheckpoint={cfg.runtime.checkpoint}\ndraw_graph={cfg.runtime.draw_graph}",
            title="🕸️ Runtime",
        )
    )


@app.command()
def graph(
    backend: str = typer.Option("langgraph", "--backend", help="导出哪种 runtime 的图，默认 langgraph"),
) -> None:
    """导出 Orchestrator graph 的 Mermaid 文本."""
    setup_logger()
    cfg = copy.deepcopy(get_config())
    cfg.runtime.backend = backend.strip().lower()
    runtime_obj = create_runtime(cfg, enable_capabilities=True)
    if not hasattr(runtime_obj, "get_graph_mermaid"):
        console.print("当前 runtime 不支持图导出。")
        raise typer.Exit(code=1)
    console.print(runtime_obj.get_graph_mermaid())


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


def _check_mistake_kb() -> tuple[str, str, str]:
    """第 9 项：错题本 SQLite 可读写 + 教材库 Chroma collection 状态（Task 010）."""
    try:
        from course_agent.storage.mistake_db import (
            count_due_today,
            ensure_schema,
            get_db_path,
        )

        db_path = get_db_path()
        ensure_schema()
        n_due = count_due_today()
        kb_path = "—"
        kb_n = 0
        try:
            from course_agent.tools.kb import _kb_count, _kb_persist_dir

            kb_n = _kb_count()
            kb_path = str(_kb_persist_dir())
        except Exception as e:  # noqa: BLE001
            return (
                "⚠️",
                "教材库不可用",
                f"错题本 OK（待复习 {n_due}）；教材库初始化失败：{type(e).__name__}: {e}",
            )
        return (
            "✅",
            f"待复习 {n_due} ｜ 教材库 {kb_n} chunks",
            f"db={db_path}；kb_dir={kb_path}",
        )
    except Exception as e:  # noqa: BLE001
        return ("❌", type(e).__name__, str(e)[:200])


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


def _check_streaming_and_examiner(cfg: Any) -> tuple[str, str, str]:
    """第 10 项（Task 011）：探活 LLM 流式接口 + Examiner Agent 可实例化.

    - LLM 流式：发一个最短消息，只读 1 个有效 chunk 即 break；
      provider=mock 或未配置 key 时跳过为 ⚠️
    - Examiner：只验证可实例化与限定工具集是否生效
    """
    import asyncio as _asyncio

    if cfg.llm.provider == "mock" or not cfg.llm.api_key:
        # 还是把 examiner 实例化部分跑一下（这部分不依赖网络）
        try:
            from course_agent.agent.examiner import ExaminerAgent
            from course_agent.llm import create_llm

            llm = create_llm(cfg.llm)
            ex = ExaminerAgent(llm=llm)
            return (
                "⚠️",
                "stream 跳过",
                f"provider=mock 或未配 key；examiner 工具集 OK：{ex.allowed_tools}",
            )
        except Exception as e:  # noqa: BLE001
            return ("❌", type(e).__name__, str(e)[:200])

    try:
        from course_agent.agent.examiner import ExaminerAgent
        from course_agent.llm import create_llm
        from course_agent.llm.base import LLMMessage

        llm = create_llm(cfg.llm)

        async def _probe() -> str | None:
            n = 0
            last_finish: str | None = None
            async for chunk in llm.astream([LLMMessage(role="user", content="hi")]):
                if chunk.finish_reason == "error":
                    return f"err:{chunk.error or '?'}"
                n += 1
                if chunk.finish_reason:
                    last_finish = chunk.finish_reason
                if n >= 3:
                    break
            return last_finish or "streaming"

        result = _asyncio.run(_probe())
        if result and result.startswith("err:"):
            return ("⚠️", "stream 不可用", result[:200])

        ex = ExaminerAgent(llm=llm)
        return (
            "✅",
            f"stream OK ({result})",
            f"examiner.allowed_tools={ex.allowed_tools}",
        )
    except Exception as e:  # noqa: BLE001
        return ("⚠️", type(e).__name__, str(e)[:200])


def _check_multi_agent(cfg: Any) -> tuple[str, str, str]:
    """第 11 项（Task 012）：探活 4 个 Agent 可实例化 + Orchestrator hello + metrics.db 可写.

    - provider=mock / 未配 key：只做"实例化 + metrics.db 可读写"，不跑真实 LLM 环路
    - 真实 LLM：跑一个 max_sub_tasks=1 / max_refine=0 的最小闭环（1 Plan + 1 Solve + 1 Critic）
    """
    try:
        from course_agent.agent import (
            CriticAgent,
            Orchestrator,
            PlannerAgent,
            SolverAgent,
        )
        from course_agent.observability.metrics import ensure_schema

        db_path = ensure_schema()
        db_ok = db_path.exists()

        if cfg.llm.provider == "mock" or not cfg.llm.api_key:
            llm = create_llm(cfg.llm)
            for agent_cls in (PlannerAgent, SolverAgent, CriticAgent):
                agent_cls(llm=llm)
            Orchestrator(llm=llm)
            return (
                "⚠️",
                "orch 跳过 hello 探活",
                f"4 agents OK；metrics.db={'存在' if db_ok else '缺失'} ({db_path})",
            )

        import asyncio as _asyncio

        llm = create_llm(cfg.llm)
        orch = Orchestrator(
            llm=llm,
            max_sub_tasks=1,
            max_refine_per_task=0,
            max_total_llm_calls=8,
        )
        result = _asyncio.run(orch.arun("请直接回复 hello，不用调任何工具。"))
        return (
            "✅",
            f"hello roundtrip OK ({result.total_llm_calls} llm calls)",
            f"4 agents ready；metrics.db OK ({db_path})",
        )
    except Exception as e:  # noqa: BLE001
        return ("⚠️", type(e).__name__, str(e)[:200])


def _check_capabilities_and_mcp(cfg: Any) -> tuple[str, str, str]:
    """第 12 项（Task 013）：Skill runtime + capability registry + MCP mock 探活."""
    try:
        reg = _build_capability_registry(cfg)
        all_caps = reg.list_all()
        n_skill = len([c for c in all_caps if c.kind.value == "skill"])
        n_tool = len([c for c in all_caps if c.kind.value == "internal_tool"])
        n_mcp = len([c for c in all_caps if c.kind.value == "mcp"])
        if not cfg.mcp.enabled:
            return (
                "⚠️",
                f"tools={n_tool}, skills={n_skill}, mcp=skip",
                "MCP 未启用；Skill runtime 与 capability registry 已就绪",
            )
        return (
            "✅",
            f"tools={n_tool}, skills={n_skill}, mcp={n_mcp}",
            "Skill runtime OK；MCP mock/provider 可枚举",
        )
    except Exception as e:  # noqa: BLE001
        return ("⚠️", type(e).__name__, str(e)[:200])


def _check_langgraph_runtime(cfg: Any) -> tuple[str, str, str]:
    """第 13 项（Task 014）：LangGraph runtime 可导入 / 可实例化 / mock roundtrip / graph 导出."""
    try:
        import asyncio as _asyncio

        runtime_cfg = copy.deepcopy(cfg)
        runtime_cfg.runtime.backend = "langgraph"
        llm = None
        if runtime_cfg.llm.provider != "mock" and not runtime_cfg.llm.api_key:
            runtime_cfg.llm.provider = "mock"
            llm = create_llm(runtime_cfg.llm)
        runtime_obj = create_runtime(runtime_cfg, llm=llm, enable_capabilities=True)
        mermaid = runtime_obj.get_graph_mermaid()
        if cfg.llm.provider == "mock" or not cfg.llm.api_key:
            result = _asyncio.run(runtime_obj.arun("请直接回复 hello，不用调任何工具。"))
            return (
                "⚠️",
                f"graph OK ({result.total_llm_calls} calls)",
                f"provider=mock 或未配 key；Mermaid {len(mermaid)} chars",
            )
        result = _asyncio.run(runtime_obj.arun("请直接回复 hello，不用调任何工具。"))
        return (
            "✅",
            f"langgraph roundtrip OK ({result.total_llm_calls} calls)",
            f"checkpoint={runtime_cfg.runtime.checkpoint}；Mermaid {len(mermaid)} chars",
        )
    except Exception as e:  # noqa: BLE001
        return ("⚠️", type(e).__name__, str(e)[:200])


@app.command()
def doctor() -> None:
    """启动自检：Python / 依赖 / .env / Key / LLM / Embedding / VL / Tools / 错题本+教材库 / 流式+Examiner / 多 Agent / Skill+MCP / LangGraph Runtime 十三项检查."""
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
        ("错题本 + 教材库", lambda: _check_mistake_kb()),
        ("流式 + Examiner Agent", lambda: _check_streaming_and_examiner(cfg)),
        ("多 Agent + Orchestrator", lambda: _check_multi_agent(cfg)),
        ("Skill + MCP 能力层", lambda: _check_capabilities_and_mcp(cfg)),
        ("LangGraph Runtime", lambda: _check_langgraph_runtime(cfg)),
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
