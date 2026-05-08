"""AgentLoop ↔ Chainlit 适配器：把 Agent 事件翻译成 Chainlit UI 组件."""

from __future__ import annotations

import json
from typing import Any

import chainlit as cl

from course_agent.logger import get_logger

_log = get_logger("ChainlitAdapter")


class ChainlitCallbacks:
    """把 AgentCallbacks 事件翻译成 Chainlit 的 Message/Step 组件.

    设计：
      - on_thought      -> 忽略（Qwen tool-calling 场景下 thought 通常为空）
      - on_tool_call    -> 创建一个 cl.Step，展示工具名和参数
      - on_tool_result  -> 在对应 Step 里填入 output（或错误红色）
      - on_final        -> 发送一条 assistant 消息（主回答）
    """

    def __init__(self) -> None:
        self._steps: dict[tuple[int, str], cl.Step] = {}

    async def on_thought(self, step: int, content: str) -> None:
        if not content or not content.strip():
            return
        # 用一个 Step 展示思考内容（可折叠）
        async with cl.Step(name=f"💭 思考 (Step {step})", type="llm") as s:
            s.output = content

    async def on_tool_call(
        self, step: int, name: str, args: dict[str, Any]
    ) -> None:
        args_str = json.dumps(args, ensure_ascii=False, indent=2)
        s = cl.Step(name=f"🔧 {name}", type="tool")
        await s.__aenter__()
        s.input = args_str
        self._steps[(step, name)] = s

    async def on_tool_result(
        self, step: int, name: str, result: str, is_error: bool = False
    ) -> None:
        s = self._steps.pop((step, name), None)
        if s is None:
            # 防御：找不到对应 Step 则兜底新开一个
            s = cl.Step(name=f"🔧 {name} (结果)", type="tool")
            await s.__aenter__()

        display = result if len(result) <= 2000 else result[:2000] + "\n... (已截断)"
        if is_error:
            s.output = f"❌ {display}"
            s.is_error = True
        else:
            s.output = display

        try:
            await s.__aexit__(None, None, None)
        except Exception as e:  # noqa: BLE001
            _log.warning(f"关闭 Step 异常: {e}")

    async def on_final(self, answer: str) -> None:
        if not answer:
            answer = "(模型未返回内容)"
        await cl.Message(content=answer, author="Course Agent").send()
