from __future__ import annotations

from course_agent.context import (
    ContextEnvelope,
    ContextSection,
    context_to_markdown,
    latest_context_path,
    load_context_artifact,
    save_context_artifact,
)


def _envelope():
    return ContextEnvelope.create(
        role='react',
        query='你好',
        sections=[ContextSection(name='history_0_user', content='hello', source='history', role='user')],
        dropped_sections=['old'],
    )


def test_save_and_load_context_artifact(tmp_path):
    path = save_context_artifact(_envelope(), context_dir=tmp_path)
    loaded = load_context_artifact(path)
    assert loaded.role == 'react'
    assert loaded.query == '你好'


def test_latest_context_path_returns_latest_file(tmp_path):
    save_context_artifact(_envelope(), context_dir=tmp_path, artifact_id='a')
    save_context_artifact(_envelope(), context_dir=tmp_path, artifact_id='b')
    latest = latest_context_path(tmp_path)
    assert latest is not None
    assert latest.name.endswith('.json')


def test_context_to_markdown_contains_sections():
    md = context_to_markdown(_envelope())
    assert '# Context Inspect' in md
    assert '## Sections' in md


def test_context_to_markdown_contains_dropped_sections():
    md = context_to_markdown(_envelope())
    assert 'Dropped Sections' in md
    assert '`old`' in md
