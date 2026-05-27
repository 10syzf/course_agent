from __future__ import annotations

from course_agent.context import ContextBudget, ContextEnvelope, ContextSection


def test_context_section_char_count():
    section = ContextSection(name='a', content='hello', source='history')
    assert section.char_count == 5


def test_context_budget_available_chars():
    budget = ContextBudget(max_chars=1000, reserve_chars=250)
    assert budget.available_chars == 750


def test_context_envelope_create_counts_selected_and_total():
    all_sections = [
        ContextSection(name='a', content='1234', source='history'),
        ContextSection(name='b', content='123456', source='memory'),
    ]
    env = ContextEnvelope.create(
        role='react',
        query='你好',
        sections=[all_sections[0]],
        all_sections=all_sections,
    )
    assert env.selected_chars == 4
    assert env.total_chars == 10


def test_context_envelope_keeps_dropped_sections():
    env = ContextEnvelope.create(
        role='solver',
        query='x',
        sections=[],
        dropped_sections=['old_history'],
    )
    assert env.dropped_sections == ['old_history']


def test_context_section_preserves_metadata_and_role():
    section = ContextSection(
        name='task',
        content='do it',
        source='task_notes',
        role='system',
        metadata={'k': 'v'},
    )
    assert section.role == 'system'
    assert section.metadata['k'] == 'v'
