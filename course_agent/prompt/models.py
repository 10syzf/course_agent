"""Task 017：Prompt 模型."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import BaseModel, Field


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PromptSection(BaseModel):
    """Prompt 的一个结构化 section."""

    name: str
    content: str
    is_static: bool
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)


class PromptEnvelope(BaseModel):
    """编译后的 prompt 包络."""

    role: str
    static_prefix: str
    dynamic_tail: str
    full_prompt: str
    static_hash: str
    dynamic_hash: str
    sections: list[PromptSection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        role: str,
        static_prefix: str,
        dynamic_tail: str,
        sections: list[PromptSection],
        metadata: dict[str, Any] | None = None,
    ) -> PromptEnvelope:
        full_prompt = "\n\n".join(
            part for part in [static_prefix.strip(), dynamic_tail.strip()] if part
        ).strip()
        return cls(
            role=role,
            static_prefix=static_prefix.strip(),
            dynamic_tail=dynamic_tail.strip(),
            full_prompt=full_prompt,
            static_hash=_sha256(static_prefix.strip()),
            dynamic_hash=_sha256(dynamic_tail.strip()),
            sections=sections,
            metadata=metadata or {},
        )


__all__ = ["PromptEnvelope", "PromptSection"]
