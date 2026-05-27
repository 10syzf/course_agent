from __future__ import annotations

from course_agent.context import (
    ContextSection,
    compress_section,
    extractive_compress_text,
    summarize_text,
    truncate_text,
)

LONG_TEXT = """第一行说明
- 关键事实 A
- 关键事实 B
- 关键事实 C
最后一行结论非常重要，需要保留。"""


def test_truncate_text_shortens_and_adds_ellipsis():
    out = truncate_text('abcdefg', 5)
    assert out.endswith('...')
    assert len(out) == 5


def test_extractive_compress_text_prefers_bullets():
    out = extractive_compress_text(LONG_TEXT, 30)
    assert '-' in out or '关键事实' in out
    assert len(out) <= 30


def test_summarize_text_short_text_returns_original():
    out = summarize_text('简短文本', max_chars=20)
    assert out == '简短文本'


def test_summarize_text_long_text_shortens():
    out = summarize_text('这是第一句。这里是第二句。这里是第三句。', max_chars=12)
    assert len(out) <= 12


def test_compress_section_updates_metadata_and_trace():
    section, trace = compress_section(
        ContextSection(name='mem', content='x' * 100, source='long_memory'),
        max_chars=20,
        strategy='summary',
    )
    assert section.char_count <= 20
    assert section.metadata['compressed'] is True
    assert trace.section_name == 'mem'
