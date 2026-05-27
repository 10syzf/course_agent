"""Task 018：上下文选择器."""

from __future__ import annotations

from course_agent.context.budget import ContextBudget
from course_agent.context.compressor import compress_section
from course_agent.context.models import CompressionTrace, ContextSection

_SOURCE_STRATEGY = {
    'long_memory': 'summary',
    'short_memory_summary': 'summary',
    'task_notes': 'extractive',
    'session_notes': 'extractive',
    'handoff': 'summary',
}


def _sort_key(item: tuple[int, ContextSection]) -> tuple[int, int, int]:
    idx, section = item
    return (0 if section.pinned else 1, -section.priority, idx)


def select_context_sections(
    sections: list[ContextSection],
    budget: ContextBudget,
) -> tuple[list[ContextSection], list[str], list[CompressionTrace]]:
    available = budget.available_chars
    indexed = list(enumerate(sections))
    indexed.sort(key=_sort_key)

    chosen: list[tuple[int, ContextSection]] = []
    dropped: list[str] = []
    traces: list[CompressionTrace] = []
    used = 0

    for idx, section in indexed:
        remaining = available - used
        if remaining <= 0:
            dropped.append(section.name)
            continue
        if section.char_count <= remaining:
            chosen.append((idx, section))
            used += section.char_count
            continue
        if not section.compressible:
            if section.pinned:
                compressed, trace = compress_section(section, max_chars=remaining, strategy='truncate')
                chosen.append((idx, compressed))
                traces.append(trace)
                used += compressed.char_count
            else:
                dropped.append(section.name)
            continue

        strategy = _SOURCE_STRATEGY.get(section.source, 'extractive')
        compressed, trace = compress_section(section, max_chars=remaining, strategy=strategy)
        if compressed.char_count > 0 and compressed.char_count <= remaining:
            chosen.append((idx, compressed))
            traces.append(trace)
            used += compressed.char_count
        elif section.pinned and remaining > 0:
            forced, force_trace = compress_section(section, max_chars=remaining, strategy='truncate')
            chosen.append((idx, forced))
            traces.append(force_trace)
            used += forced.char_count
        else:
            dropped.append(section.name)

    chosen.sort(key=lambda item: item[0])
    return [section for _, section in chosen], dropped, traces
