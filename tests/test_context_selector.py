from __future__ import annotations

from course_agent.context import ContextBudget, ContextSection, select_context_sections


def test_selector_keeps_all_when_budget_is_enough():
    sections = [
        ContextSection(name='a', content='123', source='history'),
        ContextSection(name='b', content='456', source='memory'),
    ]
    chosen, dropped, traces = select_context_sections(sections, ContextBudget(max_chars=100, reserve_chars=0))
    assert len(chosen) == 2
    assert dropped == []
    assert traces == []


def test_selector_keeps_pinned_section_first_under_pressure():
    sections = [
        ContextSection(name='optional', content='x' * 20, source='history', priority=10),
        ContextSection(name='pinned', content='y' * 20, source='task_notes', priority=5, pinned=True),
    ]
    chosen, dropped, _ = select_context_sections(sections, ContextBudget(max_chars=25, reserve_chars=0))
    names = [s.name for s in chosen]
    assert 'pinned' in names
    assert 'optional' in dropped or any(s.name == 'optional' and s.char_count < 20 for s in chosen)


def test_selector_compresses_large_compressible_section():
    sections = [
        ContextSection(name='large', content='a' * 200, source='long_memory', priority=50),
    ]
    chosen, dropped, traces = select_context_sections(sections, ContextBudget(max_chars=60, reserve_chars=0))
    assert len(chosen) == 1
    assert chosen[0].char_count <= 60
    assert dropped == []
    assert traces


def test_selector_drops_non_compressible_section_when_needed():
    sections = [
        ContextSection(name='tool', content='z' * 80, source='tool_result', compressible=False),
    ]
    chosen, dropped, traces = select_context_sections(sections, ContextBudget(max_chars=20, reserve_chars=0))
    assert chosen == []
    assert dropped == ['tool']
    assert traces == []


def test_selector_restores_original_order_for_chosen_sections():
    sections = [
        ContextSection(name='first', content='111', source='history', priority=10),
        ContextSection(name='second', content='222', source='task_notes', priority=99, pinned=True),
    ]
    chosen, _, _ = select_context_sections(sections, ContextBudget(max_chars=20, reserve_chars=0))
    assert [s.name for s in chosen] == ['first', 'second']
