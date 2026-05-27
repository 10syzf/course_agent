"""Task 018：Context profiling."""

from __future__ import annotations

from course_agent.context.models import ContextEnvelope


def profile_context(envelope: ContextEnvelope) -> dict[str, object]:
    source_counts: dict[str, int] = {}
    for section in envelope.sections:
        source_counts[section.source] = source_counts.get(section.source, 0) + section.char_count
    dropped = len(envelope.dropped_sections)
    compression_saved = envelope.total_chars - envelope.selected_chars
    return {
        'role': envelope.role,
        'query': envelope.query,
        'total_chars': envelope.total_chars,
        'selected_chars': envelope.selected_chars,
        'section_count': len(envelope.sections),
        'dropped_sections': dropped,
        'compression_saved_chars': max(0, compression_saved),
        'source_breakdown': source_counts,
    }
