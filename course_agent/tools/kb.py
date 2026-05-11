"""教材 RAG 工具（Task 010）.

两个 @tool 入口：
    - kb_ingest(path_or_url)   摄入文件 → 切 chunk → 写入 Chroma kb_textbook collection
    - kb_search(query, top_k)  从 kb_textbook 召回带 source/page 的相关段落

设计取舍：
- 复用 LongTermMemory 用过的 chromadb / Embedder 抽象，但**独立 collection** kb_textbook
- 持久化路径独立：data/kb/ （不污染 Memory 的 data/memory/<session>）
- chunk 策略：朴素的固定字符长度 + overlap（默认 800 / 100），中文友好
- HashEmbedder 兜底时在 search 结果尾部追加显著警告（不假装效果）
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from course_agent.logger import get_logger
from course_agent.memory.embedders import (
    BaseEmbedder,
    HashEmbedder,
    create_embedder,
)
from course_agent.tools.registry import tool

_log = get_logger("kb")

_DEFAULT_PERSIST_DIR = Path("data/kb")
_KB_COLLECTION_NAME = "kb_textbook"
_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_CHUNK_OVERLAP = 100
_HARD_MAX_CHUNKS_PER_INGEST = 5000
_SEARCH_OUTPUT_LIMIT = 8 * 1024  # 8 KB


# ---------- chunk ----------


def _chunk_text(
    text: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """朴素的固定字符切分.

    chunk_size <= 0 时退化成「整段一个 chunk」；overlap 自动夹到 [0, chunk_size//2]。
    """
    if not text:
        return []
    if chunk_size <= 0:
        return [text]
    if overlap < 0:
        overlap = 0
    if overlap >= chunk_size:
        overlap = chunk_size // 2

    out: list[str] = []
    n = len(text)
    step = chunk_size - overlap
    i = 0
    while i < n:
        out.append(text[i : i + chunk_size])
        i += step
    return out


# ---------- chroma collection helper ----------


def _get_kb_collection(
    persist_dir: Path | None = None,
    embedder: BaseEmbedder | None = None,
) -> tuple[Any, BaseEmbedder]:
    """返回 (chroma_collection, embedder).

    - persist_dir 为 None 时用模块默认（data/kb）
    - embedder 为 None 时走 create_embedder() 自动选择
    """
    try:
        import chromadb  # type: ignore
    except ImportError as e:
        raise RuntimeError("需要安装 chromadb 包以使用教材库") from e

    pd = (persist_dir or _DEFAULT_PERSIST_DIR).expanduser()
    pd.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(pd))
    col = client.get_or_create_collection(
        name=_KB_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    emb = embedder or create_embedder()
    return col, emb


def _is_hash_embedder(emb: BaseEmbedder) -> bool:
    return isinstance(emb, HashEmbedder)


# ---------- 文本抽取 ----------


def _read_pdf_text(path: Path) -> tuple[list[tuple[int, str]], int]:
    """复用 pypdf 抽取每页文本.

    返回 [(page_no_1based, text), ...] 与总页数；扫描件兜底走 image_ocr 与 pdf_read 工具一致。
    """
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("需要 pypdf：uv add pypdf") from e

    reader = PdfReader(str(path))
    total = len(reader.pages)
    pages: list[tuple[int, str]] = []
    for idx in range(total):
        try:
            t = (reader.pages[idx].extract_text() or "").strip()
        except Exception as e:  # noqa: BLE001
            t = f"[页面 {idx + 1} 解析失败：{e}]"
        pages.append((idx + 1, t))

    # 扫描件兜底：所有页几乎都没文字 → 尝试 OCR 第一页（成本可控）
    max_per_page = max((len(t) for _, t in pages), default=0)
    if max_per_page < 30:
        try:
            from course_agent.tools.pdf_tools import _try_ocr_first_page

            ocr_text = _try_ocr_first_page(path)
        except Exception as e:  # noqa: BLE001
            _log.warning(f"OCR 兜底失败：{type(e).__name__}: {e}")
            ocr_text = None
        if ocr_text:
            pages = [(1, f"[OCR]\n{ocr_text}")]
            return pages, total
    return pages, total


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


# ---------- @tool: kb_ingest ----------


@tool(
    name="kb_ingest",
    description=(
        "把一份教材 / 笔记 / 文章摄入到本地教材库（Chroma 向量库 kb_textbook）。"
        "支持本地路径，扩展名 .pdf / .md / .txt / .markdown。"
        "PDF 自动按页切；其它文件按 800 字符 + 100 overlap 切。"
        "已存在的内容会按 chunk_id 去重避免重复入库。"
    ),
)
def kb_ingest(
    path: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> str:
    if not isinstance(path, str) or not path.strip():
        return json.dumps({"error": "path 不能为空"}, ensure_ascii=False)
    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        return json.dumps(
            {"error": f"文件不存在或不是普通文件：{path}"},
            ensure_ascii=False,
        )

    ext = p.suffix.lower()
    source_name = p.name
    chunks: list[tuple[str, dict[str, Any]]] = []  # (text, metadata)

    try:
        if ext == ".pdf":
            pages, total = _read_pdf_text(p)
            for page_no, page_text in pages:
                if not page_text.strip():
                    continue
                for ci, c in enumerate(
                    _chunk_text(page_text, chunk_size, chunk_overlap)
                ):
                    chunks.append(
                        (
                            c,
                            {
                                "source": source_name,
                                "page": page_no,
                                "chunk_idx": ci,
                                "total_pages": total,
                            },
                        )
                    )
        elif ext in {".md", ".markdown", ".txt"}:
            full = _read_text_file(p)
            for ci, c in enumerate(_chunk_text(full, chunk_size, chunk_overlap)):
                chunks.append(
                    (
                        c,
                        {
                            "source": source_name,
                            "page": 0,
                            "chunk_idx": ci,
                            "total_pages": 0,
                        },
                    )
                )
        else:
            return json.dumps(
                {"error": f"暂不支持的扩展名：{ext}（支持 .pdf/.md/.markdown/.txt）"},
                ensure_ascii=False,
            )
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"error": f"解析失败：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    if not chunks:
        return f"⚠️ {source_name} 解析后没有有效文本（可能是扫描件且 OCR 不可用）。"

    if len(chunks) > _HARD_MAX_CHUNKS_PER_INGEST:
        chunks = chunks[:_HARD_MAX_CHUNKS_PER_INGEST]
        truncated_msg = (
            f"⚠️ chunk 数超过 {_HARD_MAX_CHUNKS_PER_INGEST}，已截断。"
        )
    else:
        truncated_msg = ""

    try:
        col, emb = _get_kb_collection()
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"error": f"打开教材库失败：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    try:
        texts = [c for c, _m in chunks]
        embeddings = emb.embed_batch(texts)
        # 用 source + page + chunk_idx 做稳定 id，便于二次 ingest 时覆盖而非重复
        ids = [
            f"{m['source']}::p{m['page']}::c{m['chunk_idx']}::"
            f"{uuid.uuid5(uuid.NAMESPACE_URL, t[:64]).hex[:8]}"
            for t, m in chunks
        ]
        # 去重：删除已有同 id 的（Chroma 没有 native upsert 的友好接口）
        try:
            col.delete(ids=ids)
        except Exception:  # noqa: BLE001
            pass
        col.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=[m for _t, m in chunks],
        )
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"error": f"写入向量库失败：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    fallback_note = (
        " ⚠️ 当前用 hash 兜底，向量召回率有限，建议配置真 embedding（OPENAI_API_KEY）。"
        if _is_hash_embedder(emb)
        else ""
    )
    pages_suffix = ""
    if ext == ".pdf":
        first_meta = chunks[0][1]
        tp = first_meta.get("total_pages") or 0
        pages_suffix = f"（共 {tp} 页）"
    return (
        f"✅ 已摄入 {len(chunks)} 个 chunk，来源：{source_name}{pages_suffix}。"
        f"{truncated_msg}{fallback_note}"
    )


# ---------- @tool: kb_search ----------


@tool(
    name="kb_search",
    description=(
        "从本地教材库 kb_textbook 中检索相关段落。"
        "返回的每段都带 [📚 来源 P.页码] 标头，便于在回答时引用『教材 P.42』。"
        "参数：query（必填）；top_k（默认 5，最大 20）。"
    ),
)
def kb_search(query: str, top_k: int = 5) -> str:
    if not isinstance(query, str) or not query.strip():
        return json.dumps({"error": "query 不能为空"}, ensure_ascii=False)
    try:
        k = max(1, min(int(top_k), 20))
    except (ValueError, TypeError):
        k = 5

    try:
        col, emb = _get_kb_collection()
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"error": f"打开教材库失败：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    try:
        n_total = col.count()
    except Exception:  # noqa: BLE001
        n_total = 0
    if n_total == 0:
        return "📭 教材库为空，请先调用 kb_ingest 摄入教材。"

    try:
        q_emb = emb.embed(query)
        res = col.query(query_embeddings=[q_emb], n_results=k)
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {"error": f"检索失败：{type(e).__name__}: {e}"},
            ensure_ascii=False,
        )

    docs: list[str] = (res.get("documents") or [[]])[0] or []
    metas: list[dict[str, Any]] = (res.get("metadatas") or [[]])[0] or []
    if not docs:
        return f"📭 在教材库中没有找到相关内容（query={query[:30]!r}）。"

    parts: list[str] = [
        f"📚 教材库检索：query={query[:30]!r}，命中 {len(docs)} 段"
    ]
    used = 0
    for d, m in zip(docs, metas, strict=False):
        m = m or {}
        page = m.get("page") or 0
        src = m.get("source") or "?"
        page_str = f"P.{page}" if page else "—"
        block = f"\n--- [📚 {src} {page_str}] ---\n{d.strip()}"
        if used + len(block) > _SEARCH_OUTPUT_LIMIT:
            parts.append("\n...[输出超长，已截断]")
            break
        parts.append(block)
        used += len(block)

    if _is_hash_embedder(emb):
        parts.append(
            "\n\n⚠️ 当前 embedder 为 hash 兜底，召回率有限；"
            "建议在 .env 中配置 OPENAI_API_KEY 启用真实 embedding。"
        )
    return "\n".join(parts)


# ---------- 给 doctor 用 ----------


def _kb_count() -> int:
    """返回当前教材库 chunk 数；任意失败均返回 0."""
    try:
        col, _ = _get_kb_collection()
        return int(col.count())
    except Exception:  # noqa: BLE001
        return 0


def _kb_persist_dir() -> Path:
    return _DEFAULT_PERSIST_DIR.expanduser()


# 让 ruff 知道我们用 os 是为了 future env override
_ = os
