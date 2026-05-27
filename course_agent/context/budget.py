"""Task 018：Context Budget."""

from __future__ import annotations

from pydantic import BaseModel


class ContextBudget(BaseModel):
    """字符级上下文预算。"""

    max_chars: int = 3200
    reserve_chars: int = 800
    compression_trigger_ratio: float = 0.85
    hard_drop_allowed: bool = True

    @property
    def available_chars(self) -> int:
        return max(0, self.max_chars - self.reserve_chars)
