"""MemoryManager：短期 + 长期记忆的统一编排入口."""

from __future__ import annotations

from typing import Any

from course_agent.llm.base import LLMMessage
from course_agent.logger import get_logger
from course_agent.memory.base import MemoryRecord
from course_agent.memory.long_term import LongTermMemory
from course_agent.memory.short_term import ShortTermMemory

_log = get_logger("MemoryManager")


class MemoryManager:
    """串联短期 + 长期记忆，给 AgentLoop 提供"上下文增强"."""

    def __init__(
        self,
        short: ShortTermMemory,
        long: LongTermMemory | None = None,
        *,
        recall_k: int = 3,
        recall_min_score: float = 0.2,
    ) -> None:
        self.short = short
        self.long = long
        self.recall_k = recall_k
        self.recall_min_score = recall_min_score

    async def enrich_context(
        self,
        user_input: str,
        base_history: list[LLMMessage] | None = None,
    ) -> list[LLMMessage]:
        """构建给 AgentLoop 用的"记忆增强"历史.

        组装顺序（从前到后）：
          1. base_history 中的 system 消息（保留人格 prompt）
          2. 长期记忆相关片段（若有命中）
          3. 短期记忆压缩后的最近窗口
        """
        msgs: list[LLMMessage] = []

        # 1. 保留 base_history 里的 system prompt
        if base_history:
            for m in base_history:
                if m.role == "system":
                    msgs.append(m)
                    break

        # 2. 长期记忆相关片段
        if self.long is not None:
            try:
                relevant = await self.long.recall(user_input, k=self.recall_k)
                relevant = [r for r in relevant if (r.score or 0) >= self.recall_min_score]
            except Exception as e:  # noqa: BLE001
                _log.warning(f"长期记忆检索失败：{e}")
                relevant = []
            if relevant:
                lines = [
                    f"- [{r.role}, score={r.score:.2f}] {r.content}"
                    for r in relevant
                ]
                msgs.append(
                    LLMMessage(
                        role="system",
                        content=(
                            "[RELEVANT MEMORIES] 以下是从长期记忆中检索到的相关片段，仅供参考：\n"
                            + "\n".join(lines)
                        ),
                    )
                )

        # 3. 短期记忆窗口（含可能的摘要）
        short_msgs = await self.short.compressed_history()
        # 跳过 short 里的 system（避免和上面的 base_history system 冲突）
        msgs.extend(m for m in short_msgs if m.role != "system" or not msgs)

        return msgs

    async def add_user(self, content: str, **meta: Any) -> None:
        await self.short.add("user", content, **meta)
        if self.long is not None:
            try:
                await self.long.add("user", content, **meta)
            except Exception as e:  # noqa: BLE001
                _log.warning(f"长期记忆写入失败（user）：{e}")

    async def add_assistant(self, content: str, **meta: Any) -> None:
        await self.short.add("assistant", content, **meta)
        if self.long is not None:
            try:
                await self.long.add("assistant", content, **meta)
            except Exception as e:  # noqa: BLE001
                _log.warning(f"长期记忆写入失败（assistant）：{e}")

    async def remember(self, content: str, tag: str = "note", **meta: Any) -> str:
        """主动写入长期记忆（不进短期）."""
        if self.long is None:
            return "长期记忆未启用，无法持久化。"
        await self.long.add("memory", content, tag=tag, **meta)
        return f"已记住（tag={tag}，长度 {len(content)} 字符）"

    async def recall(self, query: str, k: int | None = None) -> list[MemoryRecord]:
        if self.long is None:
            return []
        return await self.long.recall(query, k=k or self.recall_k)

    async def clear_short(self) -> None:
        await self.short.clear()

    async def clear_long(self) -> None:
        if self.long is not None:
            await self.long.clear()
