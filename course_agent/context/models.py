"""Task 018：Context 模型."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ContextSection(BaseModel):
    """一个可选择/压缩/落盘的上下文 section。"""

    name: str
    content: str
    source: str
    role: str = 'system'
    priority: int = 50
    compressible: bool = True
    pinned: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)


class CompressionTrace(BaseModel):
    """上下文压缩轨迹。"""

    section_name: str
    action: str
    strategy: str
    before_chars: int
    after_chars: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextEnvelope(BaseModel):
    """编译后的上下文包络。"""

    role: str
    query: str
    sections: list[ContextSection] = Field(default_factory=list)
    dropped_sections: list[str] = Field(default_factory=list)
    compression_trace: list[CompressionTrace] = Field(default_factory=list)
    total_chars: int = 0
    selected_chars: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        role: str,
        query: str,
        sections: list[ContextSection],
        all_sections: list[ContextSection] | None = None,
        dropped_sections: list[str] | None = None,
        compression_trace: list[CompressionTrace] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContextEnvelope:
        selected_chars = sum(s.char_count for s in sections)
        total_chars = sum(s.char_count for s in (all_sections or sections))
        return cls(
            role=role,
            query=query,
            sections=sections,
            dropped_sections=dropped_sections or [],
            compression_trace=compression_trace or [],
            total_chars=total_chars,
            selected_chars=selected_chars,
            metadata=metadata or {},
        )
