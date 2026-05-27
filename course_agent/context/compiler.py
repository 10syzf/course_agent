"""Task 018：Context compiler 与消息渲染."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from course_agent.context.budget import ContextBudget
from course_agent.context.models import ContextEnvelope, ContextSection
from course_agent.context.selectors import select_context_sections
from course_agent.llm.base import LLMMessage
from course_agent.prompt import PromptEnvelope, compile_prompt


def _render_notes(title: str, notes: str | dict[str, Any] | None) -> str:
    if not notes:
        return ''
    if isinstance(notes, str):
        text = notes.strip()
        return f'[{title}]\n{text}' if text else ''
    lines = [f'[{title}]']
    for key, value in notes.items():
        if value in (None, '', [], {}):
            continue
        if isinstance(value, list):
            lines.append(f'- {key}: ' + ', '.join(str(v) for v in value))
        else:
            lines.append(f'- {key}: {value}')
    return '\n'.join(lines)


def _history_sections(history: list[LLMMessage] | None) -> list[ContextSection]:
    items: list[ContextSection] = []
    for idx, msg in enumerate(history or []):
        if msg.role == 'system' or not (msg.content or '').strip():
            continue
        items.append(
            ContextSection(
                name=f'history_{idx}_{msg.role}',
                content=msg.content or '',
                source='history',
                role=msg.role,
                priority=40 + idx,
                compressible=msg.role != 'tool',
                metadata={'history_index': idx},
            )
        )
    return items


async def compile_context(
    *,
    role: str,
    user_input: str,
    role_prompt: str = '',
    history: list[LLMMessage] | None = None,
    project_root: str | Path | None = None,
    env_notes: str | dict[str, Any] | None = None,
    memory_notes: str | dict[str, Any] | None = None,
    mcp_notes: str | dict[str, Any] | None = None,
    session_notes: str | dict[str, Any] | None = None,
    task_notes: str | dict[str, Any] | None = None,
    memory_manager: Any | None = None,
    budget: ContextBudget | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[PromptEnvelope, ContextEnvelope]:
    prompt_envelope = compile_prompt(
        role=role,
        role_prompt=role_prompt,
        user_input=user_input,
        history_count=len(history or []),
        project_root=project_root,
        env_notes=env_notes,
        memory_notes=memory_notes,
        mcp_notes=mcp_notes,
        session_notes=session_notes,
        task_notes=task_notes,
        metadata=metadata,
    )

    sections: list[ContextSection] = []
    if memory_manager is not None:
        sections.extend(
            await memory_manager.collect_context_sections(
                user_input,
                base_history=history,
            )
        )
    else:
        sections.extend(_history_sections(history))

    session_text = _render_notes('SESSION NOTES', session_notes)
    if session_text:
        sections.append(
            ContextSection(
                name='session_notes',
                content=session_text,
                source='session_notes',
                role='system',
                priority=95,
                compressible=True,
                pinned=True,
            )
        )
    task_text = _render_notes('TASK NOTES', task_notes)
    if task_text:
        sections.append(
            ContextSection(
                name='task_notes',
                content=task_text,
                source='task_notes',
                role='system',
                priority=92,
                compressible=True,
                pinned=True,
            )
        )

    chosen, dropped, traces = select_context_sections(sections, budget or ContextBudget())
    envelope = ContextEnvelope.create(
        role=role,
        query=user_input,
        sections=chosen,
        all_sections=sections,
        dropped_sections=dropped,
        compression_trace=traces,
        metadata={
            'prompt_role': prompt_envelope.role,
            'static_hash': prompt_envelope.static_hash,
            'dynamic_hash': prompt_envelope.dynamic_hash,
            **(metadata or {}),
        },
    )
    return prompt_envelope, envelope


def render_context_messages(envelope: ContextEnvelope) -> list[LLMMessage]:
    out: list[LLMMessage] = []
    for section in envelope.sections:
        role = section.role if section.role in {'system', 'user', 'assistant', 'tool'} else 'system'
        out.append(LLMMessage(role=role, content=section.content))
    return out
