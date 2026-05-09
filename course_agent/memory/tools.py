"""把 MemoryManager 暴露为 Agent 工具.

设计：用 module-level "active manager" 单例，每个 session 启动时通过
set_active_manager() 注入；这样 @tool 装饰器在导入时就能注册到全局 registry，
而不必把 manager 作为参数传给每个工具调用。

注意：这是单进程内的全局单例，多用户场景下需要在 on_message 前调用
set_active_manager() 切换到当前 session 的 manager；Chainlit on_message
里我们是顺序串行执行的，所以这种模式是安全的。
"""

from __future__ import annotations

import asyncio
import threading

from course_agent.logger import get_logger
from course_agent.memory.manager import MemoryManager
from course_agent.tools.registry import tool

_log = get_logger("MemoryTools")
_lock = threading.Lock()
_active_manager: MemoryManager | None = None


def set_active_manager(manager: MemoryManager | None) -> None:
    """绑定当前会话的 MemoryManager（None 表示禁用记忆工具）."""
    global _active_manager
    with _lock:
        _active_manager = manager


def get_active_manager() -> MemoryManager | None:
    return _active_manager


def _run(coro):
    """在没有事件循环的同步上下文里运行协程；有循环时用 run_until_complete."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # 有运行中的 loop（实际上 AgentLoop.arun 里走 to_thread，所以这里通常没有 running loop）
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result()


@tool(name="recall", description="从长期记忆中检索与 query 相关的历史片段（语义检索）")
def recall(query: str, k: int = 3) -> str:
    """recall 工具：让 Agent 能主动查"上次我们聊到什么"."""
    mgr = get_active_manager()
    if mgr is None or mgr.long is None:
        return "[memory disabled] 长期记忆未启用，无法 recall。"

    records = _run(mgr.recall(query, k=k))
    if not records:
        return f"没有找到与「{query}」相关的记忆。"

    lines = []
    for i, r in enumerate(records):
        score_str = f"{r.score:.2f}" if r.score is not None else "n/a"
        lines.append(f"{i + 1}. [{r.role}, score={score_str}] {r.content}")
    return "\n".join(lines)


@tool(
    name="remember",
    description="主动把一条重要信息写入长期记忆（如用户偏好、关键结论、约定）",
)
def remember(content: str, tag: str = "note") -> str:
    """remember 工具：让 Agent 能主动持久化重要信息."""
    mgr = get_active_manager()
    if mgr is None or mgr.long is None:
        return "[memory disabled] 长期记忆未启用，无法 remember。"
    return _run(mgr.remember(content, tag=tag))
