"""Task 018：Context artifact 读写."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from course_agent.context.models import CompressionTrace, ContextEnvelope, ContextSection


def _ensure_context_dir(path: str | Path) -> Path:
    base = Path(path)
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_context_artifact(
    envelope: ContextEnvelope,
    *,
    context_dir: str | Path = 'data/contexts',
    artifact_id: str | None = None,
) -> Path:
    base = _ensure_context_dir(context_dir)
    path = base / f"{artifact_id or uuid4()}.json"
    path.write_text(
        json.dumps(envelope.model_dump(mode='json'), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return path


def latest_context_path(context_dir: str | Path = 'data/contexts') -> Path | None:
    base = _ensure_context_dir(context_dir)
    files = sorted(base.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def load_context_artifact(path: str | Path) -> ContextEnvelope:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    data['sections'] = [ContextSection.model_validate(item) for item in data.get('sections', [])]
    data['compression_trace'] = [CompressionTrace.model_validate(item) for item in data.get('compression_trace', [])]
    return ContextEnvelope.model_validate(data)


def context_to_markdown(envelope: ContextEnvelope) -> str:
    lines = [
        f'# Context Inspect · {envelope.role}',
        '',
        f'- query: `{envelope.query}`',
        f'- total_chars: `{envelope.total_chars}`',
        f'- selected_chars: `{envelope.selected_chars}`',
        f'- dropped_sections: `{len(envelope.dropped_sections)}`',
        '',
        '## Sections',
        '',
    ]
    for section in envelope.sections:
        lines.extend(
            [
                f'### {section.name}',
                '',
                f'- source: `{section.source}`',
                f'- role: `{section.role}`',
                f'- chars: `{section.char_count}`',
                '',
                section.content,
                '',
            ]
        )
    if envelope.dropped_sections:
        lines.extend(['## Dropped Sections', '', *[f'- `{name}`' for name in envelope.dropped_sections], ''])
    if envelope.compression_trace:
        lines.extend(['## Compression Trace', ''])
        for item in envelope.compression_trace:
            lines.append(
                f"- `{item.section_name}`: {item.strategy} ({item.before_chars} -> {item.after_chars})"
            )
    return "\n".join(lines)
