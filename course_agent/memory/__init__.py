"""Course Agent 记忆系统.

提供：
- ShortTermMemory: 单会话内的滑动窗口 + LLM 摘要压缩
- LongTermMemory: 跨会话的 Chroma 向量持久化
- MemoryManager: 统一编排，给 AgentLoop 注入"记忆增强"的上下文
- recall / remember: 暴露给 Agent 自己调用的工具
"""

from __future__ import annotations

from course_agent.memory.base import BaseMemory, MemoryRecord
from course_agent.memory.embedders import (
    BaseEmbedder,
    HashEmbedder,
    OpenAIEmbedder,
    create_embedder,
)
from course_agent.memory.long_term import LongTermMemory
from course_agent.memory.manager import MemoryManager
from course_agent.memory.short_term import ShortTermMemory

__all__ = [
    "BaseEmbedder",
    "BaseMemory",
    "HashEmbedder",
    "LongTermMemory",
    "MemoryManager",
    "MemoryRecord",
    "OpenAIEmbedder",
    "ShortTermMemory",
    "create_embedder",
]
