"""Task 018：上下文压缩策略."""

from __future__ import annotations

import re

from course_agent.context.models import CompressionTrace, ContextSection


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ''
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3].rstrip() + '...'


def extractive_compress_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ''
    if len(text) <= max_chars:
        return text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return truncate_text(text, max_chars)
    kept: list[str] = []
    for idx, line in enumerate(lines):
        if idx < 3 or idx == len(lines) - 1 or line.startswith(('-', '*', '1.')):
            candidate = '\n'.join(kept + [line])
            if len(candidate) <= max_chars:
                kept.append(line)
    if not kept:
        pieces = re.split(r'(?<=[。！？.!?])', text)
        out = ''
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            candidate = (out + ' ' + piece).strip()
            if len(candidate) > max_chars:
                break
            out = candidate
        return truncate_text(out or text, max_chars)
    return truncate_text('\n'.join(kept), max_chars)


def summarize_text(text: str, max_chars: int = 200) -> str:
    if max_chars <= 0:
        return ''
    if len(text) <= max_chars:
        return text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bullets = [ln for ln in lines if ln.startswith(('-', '*', '1.', '2.', '3.'))]
    if bullets:
        return truncate_text('；'.join(bullets), max_chars)
    pieces = re.split(r'(?<=[。！？.!?])', ' '.join(lines) or text)
    head = pieces[0].strip() if pieces and pieces[0].strip() else text[: max_chars // 2]
    tail = ''
    if len(pieces) > 1:
        for piece in reversed(pieces[1:]):
            piece = piece.strip()
            if piece:
                tail = piece
                break
    merged = head if not tail else f'{head} ... {tail}'
    return truncate_text(merged, max_chars)


def compress_section(
    section: ContextSection,
    *,
    max_chars: int,
    strategy: str = 'extractive',
) -> tuple[ContextSection, CompressionTrace]:
    before = section.char_count
    if strategy == 'truncate':
        content = truncate_text(section.content, max_chars)
    elif strategy == 'summary':
        content = summarize_text(section.content, max_chars=max_chars)
    else:
        content = extractive_compress_text(section.content, max_chars)
        strategy = 'extractive'
    compressed = section.model_copy(
        update={
            'content': content,
            'metadata': {
                **section.metadata,
                'compressed': True,
                'compression_strategy': strategy,
                'original_chars': before,
            },
        }
    )
    trace = CompressionTrace(
        section_name=section.name,
        action='compress',
        strategy=strategy,
        before_chars=before,
        after_chars=compressed.char_count,
    )
    return compressed, trace
