"""Chainlit 应用入口：浏览器访问的 Course Agent Web UI."""

from __future__ import annotations

import copy

import chainlit as cl
from chainlit.input_widget import Slider, TextInput

from course_agent.config import get_config
from course_agent.core import AgentLoop
from course_agent.llm import create_llm
from course_agent.llm.base import LLMMessage
from course_agent.logger import setup_logger
from course_agent.tools import get_registry
from course_agent.ui.adapters import ChainlitCallbacks

setup_logger()


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


def _reset_history(system_prompt: str) -> list[dict]:
    return [LLMMessage(role="system", content=system_prompt).model_dump()]


def _scene_actions() -> list[cl.Action]:
    """生成起始屏幕的 4 个场景快捷按钮."""
    labels = {
        "math": "📐 数学作业",
        "code": "💻 编程作业",
        "write": "📝 写作作业",
        "research": "🔍 资料检索",
    }
    return [
        cl.Action(
            name="scene",
            payload={"scene": key},
            label=labels[key],
            tooltip=f"切换到「{labels[key]}」提示词模板",
        )
        for key in ("math", "code", "write", "research")
    ]


def _build_settings_widgets(cfg) -> list:
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
    ]


def _build_agent(cfg, system_prompt: str | None = None) -> AgentLoop:
    """按当前 cfg 构建一个全新的 Agent."""
    llm = create_llm(cfg.llm)
    return AgentLoop(
        llm=llm,
        max_steps=cfg.agent.max_steps,
        system_prompt=system_prompt,
    )


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

    history = _reset_history(agent.system_prompt)

    cl.user_session.set("cfg", cfg)
    cl.user_session.set("agent", agent)
    cl.user_session.set("history", history)
    cl.user_session.set("scene", "default")

    # Settings 面板（右上角齿轮图标）
    await cl.ChatSettings(_build_settings_widgets(cfg)).send()

    tool_names = ", ".join(get_registry().list_names())
    header = (
        f"**Provider**: `{cfg.llm.provider}` ｜ **Model**: `{cfg.llm.model}` "
        f"｜ **Temp**: `{cfg.llm.temperature}` ｜ **Max steps**: `{cfg.agent.max_steps}`  \n"
        f"**已加载工具**: {tool_names}"
    )
    await cl.Message(
        content=f"{_WELCOME}\n\n---\n{header}",
        author="Course Agent",
        actions=_scene_actions(),
    ).send()


@cl.action_callback("scene")
async def on_scene_action(action: cl.Action) -> None:
    """点击场景快捷按钮：切换 System Prompt + 清空历史."""
    scene = (action.payload or {}).get("scene", "default")
    if scene not in _SCENE_PROMPTS:
        await cl.Message(content=f"⚠️ 未知场景：{scene}", author="System").send()
        return

    label, prompt = _SCENE_PROMPTS[scene]
    cfg = cl.user_session.get("cfg") or copy.deepcopy(get_config())

    try:
        agent = _build_agent(cfg, system_prompt=prompt)
    except Exception as e:  # noqa: BLE001
        await cl.Message(
            content=f"❌ 切换场景失败：{e}", author="System"
        ).send()
        return

    cl.user_session.set("agent", agent)
    cl.user_session.set("history", _reset_history(prompt))
    cl.user_session.set("scene", scene)

    await cl.Message(
        content=(
            f"✅ 已切换到 **{label}**，历史对话已清空。\n\n"
            "现在你可以直接输入本场景下的作业问题啦 👇"
        ),
        author="Course Agent",
    ).send()


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """Settings 面板变化：重建 Agent（保留当前场景的 system prompt 与历史）."""
    cfg = cl.user_session.get("cfg") or copy.deepcopy(get_config())

    model = (settings.get("model") or cfg.llm.model).strip() or cfg.llm.model
    temperature = float(settings.get("temperature", cfg.llm.temperature))
    max_steps = int(settings.get("max_steps", cfg.agent.max_steps))

    cfg.llm.model = model
    cfg.llm.temperature = temperature
    cfg.agent.max_steps = max_steps

    # 保留当前场景对应的 system prompt（若已设置）
    scene = cl.user_session.get("scene") or "default"
    system_prompt: str | None = None
    if scene in _SCENE_PROMPTS:
        system_prompt = _SCENE_PROMPTS[scene][1]

    try:
        agent = _build_agent(cfg, system_prompt=system_prompt)
    except Exception as e:  # noqa: BLE001
        await cl.Message(
            content=f"❌ 应用设置失败：{e}", author="System"
        ).send()
        return

    cl.user_session.set("cfg", cfg)
    cl.user_session.set("agent", agent)

    await cl.Message(
        content=(
            "⚙️ 设置已更新：\n"
            f"- Model: `{model}`\n"
            f"- Temperature: `{temperature}`\n"
            f"- Max steps: `{max_steps}`\n\n"
            "历史对话保留，下一条消息起生效。"
        ),
        author="System",
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """处理用户发送的消息."""
    agent: AgentLoop | None = cl.user_session.get("agent")
    history_raw: list[dict] = cl.user_session.get("history") or []

    if agent is None:
        await cl.Message(
            content="❌ Agent 未初始化，请刷新页面重试。", author="System"
        ).send()
        return

    history_msgs = _build_history(history_raw)
    callbacks = ChainlitCallbacks()

    # 关键：把之前的 user/assistant 轮次一并传入，作为多轮上下文
    result = await agent.arun(
        user_input=message.content,
        history=history_msgs,
        callbacks=callbacks,
    )

    # 更新 session 历史：追加本轮的 user + assistant
    history_raw.append(LLMMessage(role="user", content=message.content).model_dump())
    history_raw.append(
        LLMMessage(role="assistant", content=result.answer).model_dump()
    )

    # 截断保护：保留 system + 最近 10 轮（20 条消息）
    if len(history_raw) > 21:
        history_raw = [history_raw[0]] + history_raw[-20:]

    cl.user_session.set("history", history_raw)
