"""短期记忆：滑动窗口 + LLM 摘要压缩.

设计要点：
- 单会话内的对话历史，超过阈值就把"最早的一半"喂给 LLM 压成 200 字摘要
- 摘要替换为一条 role=system 的 [PREVIOUS CONTEXT SUMMARY] 消息
- 不依赖 Chroma，纯内存
- 接口和 BaseMemory 一致，但 recall() 返回最近 k 条（无向量检索）
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from course_agent.llm.base import BaseLLM, LLMMessage
from course_agent.logger import get_logger
from course_agent.memory.base import MemoryRecord

_log = get_logger("ShortTermMemory")

_SUMMARIZE_PROMPT = (
    "你是对话摘要器。请把下面的多轮对话压缩成不超过 200 字的中文摘要，"
    "重点保留：用户的关键问题、Agent 给出的关键结论、已知偏好与上下文。"
    "不要遗漏代词指代、人名/术语，不要展开冗余细节。"
)


class ShortTermMemory:
    """会话内短期记忆."""

    def __init__(
        self,
        llm: BaseLLM | None = None,
        max_turns: int = 20,
        compress_trigger: int = 16,
    ) -> None:
        """构造.

        Args:
            llm: 用于摘要压缩的 LLM；为 None 时关闭压缩，仅做朴素截断
            max_turns: 内存里最多保留多少条 user/assistant 消息（不含 system）
            compress_trigger: 超过这个阈值就触发一次压缩
        """
        self.llm = llm
        self.max_turns = max_turns
        self.compress_trigger = compress_trigger
        self._records: list[MemoryRecord] = []
        self._summary: str | None = None

    @property
    def size(self) -> int:
        return len(self._records)

    @property
    def summary(self) -> str | None:
        return self._summary

    async def add(self, role: str, content: str, **meta: Any) -> None:
        """追加一条消息；触发条件满足时自动压缩."""
        self._records.append(
            MemoryRecord(
                id=str(uuid4()),
                role=role,
                content=content,
                ts=time.time(),
                meta=meta,
            )
        )
        if self.llm is not None and len(self._records) > self.compress_trigger:
            await self._compress()

    async def recall(self, query: str, k: int = 5) -> list[MemoryRecord]:
        """短期记忆没有语义检索，按时间倒序返回最近 k 条."""
        return list(reversed(self._records[-k:]))

    async def clear(self) -> None:
        self._records.clear()
        self._summary = None

    async def compressed_history(self) -> list[LLMMessage]:
        """给 AgentLoop 用：返回 [可选摘要, ...保留窗口内的消息]."""
        msgs: list[LLMMessage] = []
        if self._summary:
            msgs.append(
                LLMMessage(
                    role="system",
                    content=f"[PREVIOUS CONTEXT SUMMARY]\n{self._summary}",
                )
            )
        for rec in self._records[-self.max_turns :]:
            # 跳过非标准 role（如 tool 在短期记忆里通常没有意义）
            if rec.role in {"user", "assistant", "system"}:
                msgs.append(LLMMessage(role=rec.role, content=rec.content))  # type: ignore[arg-type]
        return msgs

    async def _compress(self) -> None:
        """把最早的一半记录压成摘要."""
        if self.llm is None:
            return
        cut = len(self._records) // 2
        if cut <= 0:
            return
        old = self._records[:cut]
        text = "\n".join(f"[{r.role}] {r.content}" for r in old)

        prefix = ""
        if self._summary:
            prefix = f"[已有摘要]\n{self._summary}\n\n[新增对话]\n"
        full = prefix + text

        try:
            resp = await self.llm.achat(
                messages=[
                    LLMMessage(role="system", content=_SUMMARIZE_PROMPT),
                    LLMMessage(role="user", content=full),
                ]
            )
            self._summary = (resp.content or "").strip() or self._summary
            self._records = self._records[cut:]
            _log.info(
                f"短期记忆已压缩：丢弃 {cut} 条 → 摘要 {len(self._summary or '')} 字"
            )
        except Exception as e:  # noqa: BLE001
            _log.warning(f"短期记忆压缩失败，回退到截断：{e}")
            self._records = self._records[cut:]
