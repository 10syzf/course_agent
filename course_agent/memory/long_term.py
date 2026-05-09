"""长期记忆：基于 Chroma 的持久化向量存储."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from course_agent.logger import get_logger
from course_agent.memory.base import MemoryRecord
from course_agent.memory.embedders import BaseEmbedder

_log = get_logger("LongTermMemory")


class LongTermMemory:
    """跨会话的向量记忆.

    底层用 Chroma 做持久化向量存储；每个用户/会话对应一个独立的 collection。
    """

    def __init__(
        self,
        embedder: BaseEmbedder,
        persist_dir: str | Path = "data/memory",
        collection: str = "course_agent",
    ) -> None:
        self.embedder = embedder
        self.persist_dir = Path(persist_dir).expanduser()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection
        self._client: Any = None
        self._collection: Any = None

    def _ensure_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        try:
            import chromadb  # type: ignore
        except ImportError as e:
            raise RuntimeError("需要安装 chromadb 包以使用 LongTermMemory") from e
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    async def add(self, role: str, content: str, **meta: Any) -> None:
        if not content or not content.strip():
            return
        col = self._ensure_collection()
        emb = self.embedder.embed(content)
        rec_id = str(uuid4())
        col.add(
            ids=[rec_id],
            embeddings=[emb],
            documents=[content],
            metadatas=[{"role": role, "ts": time.time(), **meta}],
        )

    async def add_batch(self, items: list[tuple[str, str, dict[str, Any]]]) -> None:
        """批量添加：[(role, content, meta), ...]，比 add() 单条快很多."""
        if not items:
            return
        col = self._ensure_collection()
        contents = [c for _, c, _ in items if c.strip()]
        if not contents:
            return
        embeddings = self.embedder.embed_batch(contents)
        col.add(
            ids=[str(uuid4()) for _ in contents],
            embeddings=embeddings,
            documents=contents,
            metadatas=[{"role": r, "ts": time.time(), **m} for r, c, m in items if c.strip()],
        )

    async def recall(self, query: str, k: int = 5) -> list[MemoryRecord]:
        if not query.strip():
            return []
        col = self._ensure_collection()
        try:
            count = col.count()
        except Exception:  # noqa: BLE001
            count = 0
        if count == 0:
            return []
        emb = self.embedder.embed(query)
        res = col.query(query_embeddings=[emb], n_results=min(k, count))

        records: list[MemoryRecord] = []
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            score = (1.0 - dist) if dist is not None else None
            records.append(
                MemoryRecord(
                    id=ids[i] if i < len(ids) else str(uuid4()),
                    role=str(meta.get("role", "memory")),
                    content=doc or "",
                    score=score,
                    ts=float(meta.get("ts", 0.0)),
                    meta={k: v for k, v in meta.items() if k not in {"role", "ts"}},
                )
            )
        return records

    async def clear(self) -> None:
        try:
            import chromadb  # type: ignore
        except ImportError:
            return
        if self._client is None:
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        try:
            self._client.delete_collection(self.collection_name)
        except Exception as e:  # noqa: BLE001
            _log.warning(f"删除 collection 失败（可能不存在）：{e}")
        self._collection = None

    def count(self) -> int:
        try:
            return self._ensure_collection().count()
        except Exception:  # noqa: BLE001
            return 0
