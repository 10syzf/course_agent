"""MemoryManager：短期 + 长期记忆的统一编排入口."""

from __future__ import annotations

from typing import Any

from course_agent.context.models import ContextSection
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
        if base_history:
            for m in base_history:
                if m.role == "system":
                    msgs.append(m)
                    break
        sections = await self.collect_context_sections(user_input, base_history=base_history)
        msgs.extend(render_context_messages_from_sections(sections))
        return msgs

    async def collect_context_sections(
        self,
        user_input: str,
        base_history: list[LLMMessage] | None = None,
    ) -> list[ContextSection]:
        """收集可供 context compiler 使用的结构化 sections."""
        sections: list[ContextSection] = []

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
                sections.append(
                    ContextSection(
                        name="relevant_memories",
                        content=(
                            "[RELEVANT MEMORIES] 以下是从长期记忆中检索到的相关片段，仅供参考：\n"
                            + "\n".join(lines)
                        ),
                        source="long_memory",
                        role="system",
                        priority=90,
                        compressible=True,
                    )
                )

        short_msgs = await self.short.compressed_history()
        summary_index = 0
        for idx, msg in enumerate(short_msgs):
            if not (msg.content or "").strip():
                continue
            if msg.role == "system":
                sections.append(
                    ContextSection(
                        name=f"short_memory_summary_{summary_index}",
                        content=msg.content or "",
                        source="short_memory_summary",
                        role="system",
                        priority=85,
                        compressible=True,
                        metadata={"short_index": idx},
                    )
                )
                summary_index += 1
                continue
            sections.append(
                ContextSection(
                    name=f"short_memory_{idx}_{msg.role}",
                    content=msg.content or "",
                    source="short_memory_recent",
                    role=msg.role,
                    priority=55 + idx,
                    compressible=msg.role != "tool",
                    metadata={"short_index": idx},
                )
            )

        return sections

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


def render_context_messages_from_sections(
    sections: list[ContextSection],
) -> list[LLMMessage]:
    """兼容旧 memory.enrich_context()：把 sections 转回消息列表."""
    out: list[LLMMessage] = []
    for section in sections:
        role = section.role if section.role in {"system", "user", "assistant", "tool"} else "system"
        out.append(LLMMessage(role=role, content=section.content))
    return out
