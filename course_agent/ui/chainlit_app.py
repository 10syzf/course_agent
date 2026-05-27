"""Chainlit 应用入口：浏览器访问的 Course Agent Web UI."""

from __future__ import annotations

import copy
from pathlib import Path

import chainlit as cl
from chainlit.input_widget import Slider, Switch, TextInput

from course_agent.agent import ExaminerAgent
from course_agent.capabilities.adapters import build_default_capability_registry
from course_agent.config import get_config
from course_agent.core import AgentLoop
from course_agent.llm import create_llm
from course_agent.llm.base import LLMMessage
from course_agent.logger import get_logger, setup_logger
from course_agent.memory import (
    LongTermMemory,
    MemoryManager,
    ShortTermMemory,
    create_embedder,
)
from course_agent.memory.tools import set_active_manager
from course_agent.runtime import create_chat_runtime, create_runtime, create_session_runtime
from course_agent.tools import get_registry
from course_agent.ui.adapters import ChainlitCallbacks

setup_logger()
_log = get_logger("ChainlitApp")


# ---------------------------------------------------------------------------
# Task 012：Chainlit data layer 持久化（消息 / Steps / Threads 落地到 SQLite）
# ---------------------------------------------------------------------------
_DATA_DIR = Path("data")
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CHAINLIT_DB_PATH = (_DATA_DIR / "chainlit.db").resolve()


def _try_register_data_layer() -> None:
    """注册 Chainlit data layer（失败时静默——不阻断 UI 启动）.

    注意：``cl_data.data_layer`` 是 chainlit 提供的装饰器，必须在 ``on_chat_start``
    之前调用，所以放到模块顶层。失败时只 log warning，让 UI 仍能跑（无持久化）。
    """
    try:
        import chainlit.data as cl_data
        from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

        @cl_data.data_layer
        def _get_data_layer() -> SQLAlchemyDataLayer:  # noqa: D401
            return SQLAlchemyDataLayer(
                conninfo=f"sqlite+aiosqlite:///{_CHAINLIT_DB_PATH}",
            )

        _log.info(f"Chainlit data layer 已启用：{_CHAINLIT_DB_PATH}")
    except Exception as e:  # noqa: BLE001
        _log.warning(
            f"Chainlit data layer 启用失败（{type(e).__name__}: {e}），"
            "UI 仍可用但消息不会持久化"
        )


_try_register_data_layer()


_WELCOME = (
    "### 👋 你好，我是 Course Agent\n\n"
    "我可以帮你完成各种课程作业：**数学计算 / 代码编写 / 知识问答 / 资料检索**。\n\n"
    "- 💡 试试问我：**帮我算一下 (12+8)*5 等于多少**\n"
    "- 📘 或者：**用三句话解释动态规划**\n"
    "- 🔬 再或者：**写一个 Python 的二分查找**\n\n"
    "---\n"
    "界面支持 Markdown、LaTeX（`$...$`）、代码高亮与可折叠的「工具调用」步骤。\n\n"
    "👉 也可以点击下方 **作业场景快捷按钮** 一键切换专属提示词，或在右上角 ⚙️ 调整模型参数。"
)


_SCENE_PROMPTS: dict[str, tuple[str, str]] = {
    "math": (
        "📐 数学作业模式",
        (
            "你是 Course Agent · 数学作业辅导专家。\n"
            "面对学生的数学题目，请遵循：\n"
            "1. 先复述题意，明确已知与所求；\n"
            "2. 分步骤推导，关键公式使用 LaTeX `$...$` 或 `$$...$$`；\n"
            "3. 涉及数值计算时，必须调用 `calculator` 工具核对；\n"
            "4. 最后给出「最终答案」与「解题要点总结」。"
        ),
    ),
    "code": (
        "💻 编程作业模式",
        (
            "你是 Course Agent · 编程作业辅导专家。\n"
            "面对学生的编程题目，请遵循：\n"
            "1. 先用自然语言说明解题思路与复杂度；\n"
            "2. 给出完整可运行的代码，使用合适语言的 Markdown 代码块；\n"
            "3. 关键行加注释，便于学生理解；\n"
            "4. 最后给出 1~2 个测试用例演示预期输出。"
        ),
    ),
    "write": (
        "📝 写作作业模式",
        (
            "你是 Course Agent · 写作作业辅导专家。\n"
            "面对学生的写作任务，请遵循：\n"
            "1. 先帮学生梳理文章结构（引言/正文/结论 或 总-分-总）；\n"
            "2. 给出可直接使用的范文或段落初稿；\n"
            "3. 指出易错点与可优化处；\n"
            "4. 鼓励学生在此基础上改写，而非直接抄袭。"
        ),
    ),
    "research": (
        "🔍 资料检索模式",
        (
            "你是 Course Agent · 资料检索与文献综述助手。\n"
            "面对学生的查资料请求，请遵循：\n"
            "1. 主动调用 `web_search` 工具获取信息；\n"
            "2. 把检索到的要点整理成条目列表，每条注明来源；\n"
            "3. 在最后用 2~3 句话做综合总结；\n"
            "4. 提醒学生以第一手资料为准、引用时规范标注。"
        ),
    ),
}


def _build_history(history: list[dict]) -> list[LLMMessage]:
    """把 user_session 里存的 dict 历史转成 LLMMessage 列表."""
    return [LLMMessage(**h) for h in history]


def _extract_image_paths(message: cl.Message) -> list[str]:
    """从 Chainlit 消息附件中提取本地图片路径（Task 009）.

    Chainlit 把用户拖拽 / 上传的图片包装为 `cl.Image` 元素，落地后通过
    `.path` 暴露本地临时路径，agent 可以直接传给 `image_ocr` 工具。
    """
    paths: list[str] = []
    elements = getattr(message, "elements", None) or []
    for el in elements:
        if not isinstance(el, cl.Image):
            continue
        path = getattr(el, "path", None)
        if path:
            paths.append(str(path))
    return paths


def _reset_history(system_prompt: str) -> list[dict]:
    return [LLMMessage(role="system", content=system_prompt).model_dump()]


def _scene_actions() -> list[cl.Action]:
    """生成起始屏幕的场景快捷按钮（Task 011 加 examiner，Task 012 加 orchestrator）."""
    labels = {
        "math": "📐 数学作业",
        "code": "💻 编程作业",
        "write": "📝 写作作业",
        "research": "🔍 资料检索",
        "examiner": "📝 出题模式",
        "orchestrator": "🧩 复杂任务模式",
    }
    tooltips = {
        "math": "切换到「数学作业」提示词模板",
        "code": "切换到「编程作业」提示词模板",
        "write": "切换到「写作作业」提示词模板",
        "research": "切换到「资料检索」提示词模板",
        "examiner": "进入 Examiner Agent：基于错题本和教材库出题陪练（Task 011）",
        "orchestrator": "进入多 Agent 编排：Plan→Solve→Critique→Refine 闭环（Task 012）",
    }
    return [
        cl.Action(
            name="scene",
            payload={"scene": key},
            label=labels[key],
            tooltip=tooltips[key],
        )
        for key in ("math", "code", "write", "research", "examiner", "orchestrator")
    ]


def _build_settings_widgets(cfg, *, memory_enabled: bool) -> list:
    """ChatSettings 面板控件."""
    return [
        TextInput(
            id="model",
            label="模型名称",
            initial=cfg.llm.model,
            description="OpenAI 兼容模型名，如 qwen-plus / qwen-turbo / qwen-max / gpt-4o-mini",
        ),
        Slider(
            id="temperature",
            label="Temperature（创造性）",
            initial=cfg.llm.temperature,
            min=0.0,
            max=1.5,
            step=0.1,
            description="越低越稳定、越高越发散",
        ),
        Slider(
            id="max_steps",
            label="Max Agent Steps（最大思考步数）",
            initial=float(cfg.agent.max_steps),
            min=1,
            max=16,
            step=1,
            description="单轮最多允许的工具调用轮数",
        ),
        Switch(
            id="memory_enabled",
            label="启用长期记忆",
            initial=memory_enabled,
            description="开启后跨会话也能记住关键信息（基于 Chroma 向量库 + DashScope embedding）",
        ),
    ]


def _build_memory(llm, *, enable_long: bool, persist_dir: Path) -> MemoryManager:
    """构造 MemoryManager.

    Args:
        llm: 用于短期记忆摘要压缩的 LLM
        enable_long: 是否启用长期向量记忆（Chroma）
        persist_dir: 长期记忆持久化目录
    """
    short = ShortTermMemory(llm=llm, max_turns=20, compress_trigger=16)
    long_mem: LongTermMemory | None = None
    if enable_long:
        try:
            embedder = create_embedder()  # 自动选 openai/hash
            long_mem = LongTermMemory(embedder=embedder, persist_dir=persist_dir)
            _log.info(f"长期记忆已启用，persist_dir={persist_dir}")
        except Exception as e:  # noqa: BLE001
            _log.warning(f"长期记忆初始化失败，回退到仅短期记忆：{e}")
            long_mem = None
    return MemoryManager(short=short, long=long_mem)


def _build_agent(cfg, system_prompt: str | None = None) -> AgentLoop:
    """按当前 cfg 构建一个全新的 Agent."""
    llm = create_llm(cfg.llm)
    return create_chat_runtime(
        cfg,
        llm=llm,
        max_steps=cfg.agent.max_steps,
        system_prompt=system_prompt,
    )


def _build_session_runtime(cfg, agent):
    """仅在 react graph runtime 下创建 session runtime."""
    if getattr(agent, "runtime_kind", "") != "react_graph":
        return None
    try:
        return create_session_runtime(
            cfg,
            llm=agent.llm,
            max_steps=cfg.agent.max_steps,
            system_prompt=getattr(agent, "system_prompt", None),
        )
    except Exception as e:  # noqa: BLE001
        _log.warning(f"构建 SessionRuntime 失败，回退到普通 react graph：{e}")
        return None


@cl.on_chat_start
async def on_chat_start() -> None:
    """每个浏览器会话启动时初始化."""
    cfg = copy.deepcopy(get_config())

    try:
        agent = _build_agent(cfg)
    except Exception as e:  # noqa: BLE001
        await cl.Message(
            content=(
                f"❌ 初始化 LLM 失败：{e}\n\n"
                "请检查 `.env` 中的 `OPENAI_API_KEY` / `OPENAI_BASE_URL` 是否正确。"
            ),
            author="System",
        ).send()
        return

    # 默认启用长期记忆（持久化到 data/memory/<session_id>）
    session_id = cl.user_session.get("id") or "default"
    persist_dir = Path("data/memory") / str(session_id)
    memory = _build_memory(agent.llm, enable_long=True, persist_dir=persist_dir)
    set_active_manager(memory)

    history = _reset_history(agent.system_prompt)

    cl.user_session.set("cfg", cfg)
    cl.user_session.set("agent", agent)
    cl.user_session.set("session_runtime", _build_session_runtime(cfg, agent))
    cl.user_session.set("task_session_id", None)
    cl.user_session.set("agent_mode", "react")
    cl.user_session.set("history", history)
    cl.user_session.set("scene", "default")
    cl.user_session.set("memory", memory)
    cl.user_session.set("memory_enabled", memory.long is not None)
    cl.user_session.set("persist_dir", str(persist_dir))

    # Settings 面板（右上角齿轮图标）
    await cl.ChatSettings(
        _build_settings_widgets(cfg, memory_enabled=memory.long is not None)
    ).send()

    tool_names = ", ".join(get_registry().list_names())
    mem_status = "✅ 已启用（短期 + 长期）" if memory.long else "⚠️ 仅短期（长期记忆初始化失败或被禁用）"
    header = (
        f"**Provider**: `{cfg.llm.provider}` ｜ **Model**: `{cfg.llm.model}` "
        f"｜ **Temp**: `{cfg.llm.temperature}` ｜ **Max steps**: `{cfg.agent.max_steps}`  \n"
        f"**已加载工具**: {tool_names}  \n"
        f"**记忆系统**: {mem_status}"
    )
    await cl.Message(
        content=f"{_WELCOME}\n\n---\n{header}",
        author="Course Agent",
        actions=_scene_actions(),
    ).send()

    # Task 010：主动学习提示——查询今日待复习错题数
    try:
        from course_agent.storage.mistake_db import count_due_today

        due = count_due_today()
    except Exception:  # noqa: BLE001
        due = 0
    if due > 0:
        await cl.Message(
            content=(
                f"📓 **今天有 {due} 道错题待复习**  \n"
                "输入 `/mistakes` 查看清单，或直接告诉我「开始复习」我陪你过一遍。"
            ),
            author="System",
        ).send()


@cl.action_callback("scene")
async def on_scene_action(action: cl.Action) -> None:
    """点击场景快捷按钮：切换 System Prompt + 清空短期历史（保留长期记忆）.

    Task 011 起，多了一个 ``examiner`` 场景：切换到 ExaminerAgent，走限定工具集 +
    独立 system_prompt，并把 agent_mode 设为 "examiner"。
    """
    scene = (action.payload or {}).get("scene", "default")
    cfg = cl.user_session.get("cfg") or copy.deepcopy(get_config())

    # ---- Task 011：出题模式 ----
    if scene == "examiner":
        try:
            llm = create_llm(cfg.llm)
            examiner = ExaminerAgent(llm=llm, max_steps=cfg.agent.max_steps)
        except Exception as e:  # noqa: BLE001
            await cl.Message(
                content=f"❌ 切换出题模式失败：{e}", author="System"
            ).send()
            return

        cl.user_session.set("agent", examiner)
        cl.user_session.set("session_runtime", None)
        cl.user_session.set("task_session_id", None)
        cl.user_session.set("agent_mode", "examiner")
        # Examiner 有自己的 system prompt，重置 history 用 examiner 的 prompt
        from course_agent.agent.examiner import EXAMINER_SYSTEM_PROMPT

        cl.user_session.set(
            "history",
            [LLMMessage(role="system", content=EXAMINER_SYSTEM_PROMPT).model_dump()],
        )
        cl.user_session.set("scene", "examiner")

        # 重置短期记忆（保留长期）
        memory: MemoryManager | None = cl.user_session.get("memory")
        if memory is not None:
            await memory.clear_short()
            memory.short = ShortTermMemory(
                llm=examiner.llm,
                max_turns=memory.short.max_turns,
                compress_trigger=memory.short.compress_trigger,
            )
            set_active_manager(memory)

        await cl.Message(
            content=(
                "✅ 已切换到 **📝 出题模式（Examiner Agent）**\n\n"
                f"我会从教材库 + 你的错题本里挑知识点出题陪你练。可用工具：`{', '.join(examiner.allowed_tools)}`\n\n"
                "你可以直接说「出一道线代特征值的题」或「来个简单的二分查找题」。"
            ),
            author="Course Agent",
        ).send()
        return

    # ---- Task 012：多 Agent 编排模式 ----
    if scene == "orchestrator":
        try:
            llm = create_llm(cfg.llm)
            orchestrator = create_runtime(
                cfg,
                llm=llm,
                enable_capabilities=True,
            )
        except Exception as e:  # noqa: BLE001
            await cl.Message(
                content=f"❌ 切换复杂任务模式失败：{e}", author="System"
            ).send()
            return

        cl.user_session.set("agent", orchestrator)
        cl.user_session.set("orchestrator_llm", llm)
        cl.user_session.set("session_runtime", None)
        cl.user_session.set("task_session_id", None)
        cl.user_session.set("agent_mode", "orchestrator")
        cl.user_session.set("history", [])
        cl.user_session.set("scene", "orchestrator")

        # 重置短期记忆（保留长期）
        memory: MemoryManager | None = cl.user_session.get("memory")
        if memory is not None:
            await memory.clear_short()
            memory.short = ShortTermMemory(
                llm=llm,
                max_turns=memory.short.max_turns,
                compress_trigger=memory.short.compress_trigger,
            )
            set_active_manager(memory)

        await cl.Message(
            content=(
                "✅ 已切换到 **🧩 复杂任务模式（Orchestrator）**\n\n"
                f"当前 backend：`{cfg.runtime.backend}`。我会按 **Plan → Solve → Critique → Refine** 的闭环处理你的任务，"
                "适合多步骤、多工具协作的复杂作业。\n\n"
                "你可以直接描述任务，例如「帮我写一份关于快速排序的报告，包含原理、代码和复杂度分析」。"
            ),
            author="Course Agent",
        ).send()
        return

    if scene not in _SCENE_PROMPTS:
        await cl.Message(content=f"⚠️ 未知场景：{scene}", author="System").send()
        return

    label, prompt = _SCENE_PROMPTS[scene]

    try:
        agent = _build_agent(cfg, system_prompt=prompt)
    except Exception as e:  # noqa: BLE001
        await cl.Message(
            content=f"❌ 切换场景失败：{e}", author="System"
        ).send()
        return

    cl.user_session.set("agent", agent)
    cl.user_session.set("session_runtime", _build_session_runtime(cfg, agent))
    cl.user_session.set("task_session_id", None)
    cl.user_session.set("agent_mode", "react")
    cl.user_session.set("history", _reset_history(prompt))
    cl.user_session.set("scene", scene)

    # 重置短期记忆，但保留长期记忆（跨场景的偏好/事实仍然可用）
    memory: MemoryManager | None = cl.user_session.get("memory")
    if memory is not None:
        await memory.clear_short()
        # 重建一个新的 short term memory（把当前 LLM 注入进去用于新对话的摘要）
        memory.short = ShortTermMemory(
            llm=agent.llm,
            max_turns=memory.short.max_turns,
            compress_trigger=memory.short.compress_trigger,
        )
        set_active_manager(memory)

    await cl.Message(
        content=(
            f"✅ 已切换到 **{label}**，短期对话已清空（长期记忆保留）。\n\n"
            "现在你可以直接输入本场景下的作业问题啦 👇"
        ),
        author="Course Agent",
    ).send()


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """Settings 面板变化：重建 Agent + 按需切换长期记忆开关."""
    cfg = cl.user_session.get("cfg") or copy.deepcopy(get_config())

    model = (settings.get("model") or cfg.llm.model).strip() or cfg.llm.model
    temperature = float(settings.get("temperature", cfg.llm.temperature))
    max_steps = int(settings.get("max_steps", cfg.agent.max_steps))
    memory_enabled = bool(
        settings.get("memory_enabled", cl.user_session.get("memory_enabled", True))
    )

    cfg.llm.model = model
    cfg.llm.temperature = temperature
    cfg.agent.max_steps = max_steps

    # 保留当前场景对应的 system prompt（若已设置）
    scene = cl.user_session.get("scene") or "default"
    system_prompt: str | None = None
    if scene in _SCENE_PROMPTS:
        system_prompt = _SCENE_PROMPTS[scene][1]

    try:
        if scene == "orchestrator":
            llm = create_llm(cfg.llm)
            agent = create_runtime(cfg, llm=llm, enable_capabilities=True)
        elif scene == "examiner":
            llm = create_llm(cfg.llm)
            agent = ExaminerAgent(llm=llm, max_steps=cfg.agent.max_steps)
        else:
            agent = _build_agent(cfg, system_prompt=system_prompt)
    except Exception as e:  # noqa: BLE001
        await cl.Message(
            content=f"❌ 应用设置失败：{e}", author="System"
        ).send()
        return

    # 处理长期记忆开关变化
    memory: MemoryManager | None = cl.user_session.get("memory")
    persist_dir = Path(cl.user_session.get("persist_dir") or "data/memory/default")
    current_llm = getattr(agent, "llm", None)
    if current_llm is None and hasattr(agent, "orchestrator"):
        current_llm = getattr(agent.orchestrator, "solver", None)
        current_llm = getattr(current_llm, "llm", None)
    if memory is None or (memory_enabled != (memory.long is not None)):
        memory = _build_memory(current_llm, enable_long=memory_enabled, persist_dir=persist_dir)
    else:
        # 仅替换 LLM（用于摘要压缩）
        memory.short.llm = current_llm
    set_active_manager(memory)

    cl.user_session.set("cfg", cfg)
    cl.user_session.set("agent", agent)
    cl.user_session.set("session_runtime", _build_session_runtime(cfg, agent))
    cl.user_session.set("memory", memory)
    cl.user_session.set("memory_enabled", memory.long is not None)

    mem_line = "✅ 长期记忆已启用" if memory.long else "⚠️ 长期记忆已关闭"
    await cl.Message(
        content=(
            "⚙️ 设置已更新：\n"
            f"- Model: `{model}`\n"
            f"- Temperature: `{temperature}`\n"
            f"- Max steps: `{max_steps}`\n"
            f"- {mem_line}\n\n"
            "历史对话保留，下一条消息起生效。"
        ),
        author="System",
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """处理用户发送的消息（带记忆增强 + Task 009 图片上传）."""
    agent = cl.user_session.get("agent")
    history_raw: list[dict] = cl.user_session.get("history") or []
    memory: MemoryManager | None = cl.user_session.get("memory")

    if agent is None:
        await cl.Message(
            content="❌ Agent 未初始化，请刷新页面重试。", author="System"
        ).send()
        return

    # Task 010：/mistakes slash 分支——直接列出错题，不走 LLM
    if (message.content or "").strip().lower().startswith("/mistakes"):
        try:
            from course_agent.storage.mistake_db import (
                count_due_today,
                list_mistakes_db,
            )

            rows = list_mistakes_db(tag="", due_only=False, limit=20)
            n_due = count_due_today()
        except Exception as e:  # noqa: BLE001
            await cl.Message(
                content=f"❌ 读取错题本失败：{type(e).__name__}: {e}",
                author="System",
            ).send()
            return
        if not rows:
            await cl.Message(
                content="📭 错题本还是空的——做错题后告诉我「记入错题本」即可写入。",
                author="System",
            ).send()
            return
        lines = [
            f"📓 **错题本**（共 {len(rows)} 条 · 今日待复习 {n_due}）",
            "| ID | 题目（截断 60） | 标签 | 复习次数 | 下次复习 |",
            "|---|---|---|---|---|",
        ]
        for r in rows:
            q = r["question"]
            q = q if len(q) <= 60 else q[:57] + "..."
            lines.append(
                f"| {r['id']} | {q} | {r.get('tags') or '-'} | "
                f"{r['repetitions']} | {r['next_review_at'][:10]} |"
            )
        await cl.Message(content="\n".join(lines), author="Course Agent").send()
        return
    # Task 009：检测用户上传的图片，落地到临时路径并把路径注入用户输入
    user_text = message.content or ""
    image_paths = _extract_image_paths(message)
    if image_paths:
        path_lines = "\n".join(f"- {p}" for p in image_paths)
        user_text = (
            f"{user_text}\n\n"
            f"【用户上传了 {len(image_paths)} 张图片，本地路径如下，"
            "请使用 image_ocr 工具抽取文字后再回答】\n"
            f"{path_lines}"
        ).strip()
        await cl.Message(
            content=f"📎 收到 {len(image_paths)} 张图片，已自动提示 Agent 调用 image_ocr 抽取文字。",
            author="System",
        ).send()

    # 关键：每次进入消息处理都要把 active manager 切到本 session 的 manager
    set_active_manager(memory)

    base_history = _build_history(history_raw)

    # 用 MemoryManager 重建增强上下文（注入长期记忆相关片段 + 短期摘要）
    if memory is not None:
        try:
            enriched = await memory.enrich_context(user_text, base_history)
        except Exception as e:  # noqa: BLE001
            _log.warning(f"enrich_context 失败，回退到裸历史：{e}")
            enriched = base_history
    else:
        enriched = base_history

    cap_specs = []
    try:
        cap_specs = build_default_capability_registry(
            tool_registry=get_registry(),
            mcp_cfg=(cl.user_session.get("cfg") or get_config()).mcp,
        ).list_all()
    except Exception as e:  # noqa: BLE001
        _log.warning(f"构建 capability 列表失败，回退到普通 Tool Step：{e}")
    callbacks = ChainlitCallbacks(capability_specs=cap_specs)

    # Task 012：复杂任务模式（Orchestrator）—— Plan→Solve→Critique→Refine
    if cl.user_session.get("agent_mode") == "orchestrator" and hasattr(agent, "arun"):
        try:
            result = await agent.arun(user_text, callbacks=callbacks)
        except Exception as e:  # noqa: BLE001
            _log.warning(f"Orchestrator 运行失败：{type(e).__name__}: {e}")
            await cl.Message(
                content=f"❌ Orchestrator 失败：{type(e).__name__}: {e}",
                author="System",
            ).send()
            return

        # 主答案
        backend = getattr(agent, "backend", (cl.user_session.get("cfg") or get_config()).runtime.backend)
        await cl.Message(
            content=result.final_answer, author=f"Orchestrator/{backend}"
        ).send()

        # Step 卡片：Plan + 每个 sub-task
        try:
            async with cl.Step(name="Plan", type="tool") as plan_step:
                plan_step.input = user_text
                plan_step.output = "\n".join(
                    f"- #{p.get('id', i + 1)} {p.get('title', '')}"
                    for i, p in enumerate(result.plan)
                )
            for sr in result.sub_results:
                sid = sr.sub_task.get("id", "?")
                title = sr.sub_task.get("title", "")
                score = sr.critic.get("score", "?")
                passed = sr.critic.get("pass", False)
                async with cl.Step(
                    name=f"Sub-Task #{sid}", type="tool"
                ) as ss:
                    ss.input = title
                    ok = "✅" if passed else "❌"
                    ss.output = (
                        f"{ok} score={score}/5 "
                        f"｜ refine={sr.refine_rounds} 轮\n\n"
                        f"{(sr.solver_output or '')[:600]}"
                    )
        except Exception as e:  # noqa: BLE001
            _log.warning(f"Orchestrator Step 渲染异常：{e}")

        # 写入记忆 + 历史
        final_text = result.final_answer or ""
        if memory is not None:
            try:
                await memory.add_user(user_text)
                await memory.add_assistant(final_text)
            except Exception as e:  # noqa: BLE001
                _log.warning(f"写入记忆失败：{e}")
        history_raw.append(
            LLMMessage(role="user", content=user_text).model_dump()
        )
        history_raw.append(
            LLMMessage(role="assistant", content=final_text).model_dump()
        )
        if len(history_raw) > 21:
            history_raw = [history_raw[0]] + history_raw[-20:]
        cl.user_session.set("history", history_raw)
        return

    # Task 016：stateful react graph session
    session_runtime = cl.user_session.get("session_runtime")
    if (
        getattr(agent, "runtime_kind", "") == "react_graph"
        and session_runtime is not None
    ):
        session_id = cl.user_session.get("task_session_id")
        current_session = (
            session_runtime.get_session(session_id) if session_id else None
        )
        current_status = (
            getattr(getattr(current_session, "status", None), "value", None)
            if current_session is not None
            else None
        )
        try:
            if current_session is not None and current_status == "waiting_human_input":
                session_result = await session_runtime.continue_session(
                    current_session.session_id,
                    user_text,
                    callbacks=callbacks,
                )
            elif current_session is not None and current_status == "waiting_approval":
                if any(token in user_text for token in ["确认", "继续", "批准", "yes", "ok"]):
                    session_result = await session_runtime.resume(
                        current_session.session_id,
                        callbacks=callbacks,
                    )
                else:
                    session_result = await session_runtime.continue_session(
                        current_session.session_id,
                        user_text,
                        callbacks=callbacks,
                    )
            else:
                session_result = await session_runtime.start(
                    user_text,
                    history=enriched,
                    callbacks=callbacks,
                )
        except Exception as e:  # noqa: BLE001
            _log.warning(f"SessionRuntime 运行失败：{type(e).__name__}: {e}")
            await cl.Message(
                content=f"❌ Stateful session 失败：{type(e).__name__}: {e}",
                author="System",
            ).send()
            return

        cl.user_session.set("task_session_id", session_result.session.session_id)
        final_text = session_result.runtime_result.answer or ""
        await cl.Message(content=final_text, author="Course Agent").send()
        try:
            async with cl.Step(name="Task Session", type="tool") as task_step:
                task_step.input = user_text
                task_step.output = (
                    f"session_id=`{session_result.session.session_id}`\n"
                    f"status=`{session_result.session.status}`\n"
                    f"waiting_reason=`{session_result.session.waiting_reason or '-'}`\n"
                    f"replay=`{session_result.session.latest_replay_path or '-'}`"
                )
        except Exception as e:  # noqa: BLE001
            _log.warning(f"Task Session Step 渲染异常：{e}")

        replay = getattr(agent, "get_last_replay", lambda: None)() or {}
        nodes = replay.get("node_sequence", [])
        if nodes:
            try:
                async with cl.Step(name="Graph Runtime", type="tool") as graph_step:
                    graph_step.input = user_text
                    graph_step.output = (
                        f"backend=`{replay.get('backend', 'langgraph')}`\n"
                        f"runtime=`{replay.get('runtime_kind', 'react_graph')}`\n"
                        f"nodes=`{' -> '.join(nodes)}`\n"
                        f"total steps=`{replay.get('steps', 0)}`\n"
                        f"replay=`{replay.get('path', '')}`"
                    )
            except Exception as e:  # noqa: BLE001
                _log.warning(f"Graph Runtime Step 渲染异常：{e}")

        if memory is not None:
            try:
                await memory.add_user(user_text)
                await memory.add_assistant(final_text)
            except Exception as e:  # noqa: BLE001
                _log.warning(f"写入记忆失败：{e}")
        history_raw.append(LLMMessage(role="user", content=user_text).model_dump())
        history_raw.append(LLMMessage(role="assistant", content=final_text).model_dump())
        if len(history_raw) > 21:
            history_raw = [history_raw[0]] + history_raw[-20:]
        cl.user_session.set("history", history_raw)
        return

    # Task 011：流式渲染主消息；任意异常整体降级到非流式 arun
    msg = cl.Message(content="", author="Course Agent")
    await msg.send()

    final_text = ""
    streamed_ok = False
    try:
        async for chunk in agent.astream_run(
            user_input=user_text,
            history=enriched,
            callbacks=callbacks,
        ):
            if chunk.delta_text:
                await msg.stream_token(chunk.delta_text)
                final_text += chunk.delta_text
        await msg.update()
        streamed_ok = True
    except Exception as e:  # noqa: BLE001
        _log.warning(f"流式渲染异常，整体降级到 arun：{type(e).__name__}: {e}")

    if not streamed_ok or not final_text.strip():
        # 兜底：非流式
        result = await agent.arun(
            user_input=user_text,
            history=enriched,
            callbacks=callbacks,
        )
        final_text = result.answer or final_text
        await cl.Message(content=final_text, author="Course Agent").send()

    # Task 015：graph-native react runtime 的最小摘要展示
    if getattr(agent, "runtime_kind", "") == "react_graph" and hasattr(
        agent, "get_last_replay"
    ):
        replay = agent.get_last_replay() or {}
        nodes = replay.get("node_sequence", [])
        if nodes:
            try:
                async with cl.Step(name="Graph Runtime", type="tool") as graph_step:
                    graph_step.input = user_text
                    graph_step.output = (
                        f"backend=`{replay.get('backend', 'langgraph')}`\n"
                        f"runtime=`{replay.get('runtime_kind', 'react_graph')}`\n"
                        f"nodes=`{' -> '.join(nodes)}`\n"
                        f"total steps=`{replay.get('steps', 0)}`\n"
                        f"replay=`{replay.get('path', '')}`"
                    )
            except Exception as e:  # noqa: BLE001
                _log.warning(f"Graph Runtime Step 渲染异常：{e}")

    # 写入记忆（短期 + 可选长期）
    if memory is not None:
        try:
            await memory.add_user(user_text)
            await memory.add_assistant(final_text)
        except Exception as e:  # noqa: BLE001
            _log.warning(f"写入记忆失败：{e}")

    # 更新 session 历史：追加本轮的 user + assistant
    history_raw.append(LLMMessage(role="user", content=user_text).model_dump())
    history_raw.append(
        LLMMessage(role="assistant", content=final_text).model_dump()
    )

    # 截断保护：保留 system + 最近 10 轮（20 条消息）
    if len(history_raw) > 21:
        history_raw = [history_raw[0]] + history_raw[-20:]

    cl.user_session.set("history", history_raw)
