"""Memory 抽象基类与数据结构."""

from __future__ import annotations

import time
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """单条记忆记录."""

    id: str
    role: str
    content: str
    score: float | None = None
    ts: float = Field(default_factory=time.time)
    meta: dict[str, Any] = Field(default_factory=dict)

    def short_repr(self, max_chars: int = 120) -> str:
        body = self.content if len(self.content) <= max_chars else self.content[:max_chars] + "…"
        return f"[{self.role}] {body}"


@runtime_checkable
class BaseMemory(Protocol):
    """所有记忆实现的统一接口."""

    async def add(self, role: str, content: str, **meta: Any) -> None: ...

    async def recall(self, query: str, k: int = 5) -> list[MemoryRecord]: ...

    async def clear(self) -> None: ...
