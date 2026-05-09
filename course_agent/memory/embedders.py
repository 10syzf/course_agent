"""Embedder 抽象与实现.

提供：
- BaseEmbedder: 统一接口
- HashEmbedder: 完全离线、无依赖的 hash-based 伪 embedding，方便单测
- OpenAIEmbedder: 走 OpenAI 兼容接口（DashScope text-embedding-v3 / OpenAI text-embedding-3-small）
- create_embedder(): 工厂函数，根据 .env 自动选择

设计取舍：默认不依赖 sentence-transformers（500MB+），仅在用户显式安装 [local-embed] extra 时启用。
"""

from __future__ import annotations

import hashlib
import math
import os
from abc import ABC, abstractmethod
from typing import Any

from course_agent.logger import get_logger

_log = get_logger("Embedder")


class BaseEmbedder(ABC):
    """文本 → 向量的统一接口."""

    dim: int = 0

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """同步嵌入单条文本."""
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """默认逐条调用，子类可覆盖以利用 batch API."""
        return [self.embed(t) for t in texts]


class HashEmbedder(BaseEmbedder):
    """完全离线、无依赖的 hash-based embedder.

    把每个 token 哈希到 dim 维空间内的一个 bucket，并按出现频次累加。
    最后做 L2 归一化。仅用于：
    - 单元测试
    - 用户没有 API Key 也想离线体验记忆功能时的 fallback
    召回质量明显弱于真实 embedding，但能保证基本的"相同/相近词命中"。
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        if not text:
            return vec
        for tok in self._tokenize(text):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        text = text.lower()
        # 同时支持英文按空格分、中文按字符分
        out: list[str] = []
        buf: list[str] = []
        for ch in text:
            if ch.isalnum() and ord(ch) < 128:
                buf.append(ch)
            else:
                if buf:
                    out.append("".join(buf))
                    buf = []
                if ch.strip():  # 中文/符号也作为 token
                    out.append(ch)
        if buf:
            out.append("".join(buf))
        return out


class OpenAIEmbedder(BaseEmbedder):
    """走 OpenAI 兼容接口的 embedding（懒加载客户端）."""

    def __init__(
        self,
        model: str = "text-embedding-v3",
        api_key: str | None = None,
        base_url: str | None = None,
        dim: int = 1024,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.dim = dim
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI  # type: ignore
            except ImportError as e:
                raise RuntimeError("需要安装 openai 包以使用 OpenAIEmbedder") from e
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def embed(self, text: str) -> list[float]:
        client = self._ensure_client()
        resp = client.embeddings.create(model=self.model, input=text or " ")
        return resp.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._ensure_client()
        # DashScope 单批最多 25 条，留点余量
        batch_size = 16
        out: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            chunk = [t or " " for t in texts[i : i + batch_size]]
            resp = client.embeddings.create(model=self.model, input=chunk)
            out.extend(d.embedding for d in resp.data)
        return out


def create_embedder(
    kind: str | None = None,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> BaseEmbedder:
    """工厂：根据 kind 选择 embedder.

    kind:
        - "hash"   → HashEmbedder（离线、无 Key）
        - "openai" → OpenAIEmbedder（走 .env 中的 OPENAI_BASE_URL）
        - None     → 自动：有 OPENAI_API_KEY 用 openai，否则 hash
    """
    if kind is None:
        kind = "openai" if (api_key or os.getenv("OPENAI_API_KEY")) else "hash"

    if kind == "hash":
        _log.info("Embedder: HashEmbedder（离线，召回质量较弱）")
        return HashEmbedder()

    if kind == "openai":
        # DashScope 兼容 text-embedding-v3，OpenAI 官方用 text-embedding-3-small
        default_model = "text-embedding-v3"
        if base_url and "openai.com" in (base_url or ""):
            default_model = "text-embedding-3-small"
        chosen = model or os.getenv("OPENAI_EMBEDDING_MODEL") or default_model
        _log.info(f"Embedder: OpenAIEmbedder(model={chosen})")
        return OpenAIEmbedder(model=chosen, api_key=api_key, base_url=base_url)

    raise ValueError(f"未知 embedder kind: {kind}")
