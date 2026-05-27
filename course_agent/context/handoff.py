"""Task 018：多 Agent 上下文交接模型."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SubTaskBrief(BaseModel):
    sub_task: dict[str, Any]
    constraints: list[str] = Field(default_factory=list)
    accepted_context: list[str] = Field(default_factory=list)
    pinned_facts: list[str] = Field(default_factory=list)
    recent_findings: list[str] = Field(default_factory=list)

    @classmethod
    def from_sub_task(
        cls,
        sub_task: dict[str, Any],
        *,
        constraints: list[str] | None = None,
        accepted_context: list[str] | None = None,
        pinned_facts: list[str] | None = None,
        recent_findings: list[str] | None = None,
    ) -> SubTaskBrief:
        return cls(
            sub_task=sub_task,
            constraints=constraints or [],
            accepted_context=accepted_context or [],
            pinned_facts=pinned_facts or [],
            recent_findings=recent_findings or [],
        )


class CriticDigest(BaseModel):
    score: int
    pass_: bool = Field(alias='pass')
    feedback: str
    must_fix: list[str] = Field(default_factory=list)
    optional_suggestions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)

    model_config = {'populate_by_name': True}

    @classmethod
    def from_result(cls, result: dict[str, Any]) -> CriticDigest:
        feedback = str(result.get('feedback', '')).strip()
        must_fix = [feedback] if feedback and not bool(result.get('pass')) else []
        optional = [feedback] if feedback and bool(result.get('pass')) else []
        return cls(
            score=int(result.get('score', 0)),
            pass_=bool(result.get('pass', False)),
            feedback=feedback,
            must_fix=must_fix,
            optional_suggestions=optional,
            evidence=[],
        )


class HandoffContext(BaseModel):
    prior_subtask_summaries: list[str] = Field(default_factory=list)
    critic_feedback: str | None = None
    refine_round: int = 0
    pinned_facts: list[str] = Field(default_factory=list)

    def to_task_notes(self) -> dict[str, Any]:
        return {
            'handoff': {
                'prior_subtask_summaries': self.prior_subtask_summaries,
                'critic_feedback': self.critic_feedback or '',
                'refine_round': self.refine_round,
                'pinned_facts': self.pinned_facts,
            }
        }


class TaskContextLedger(BaseModel):
    summaries: list[str] = Field(default_factory=list)
    critic_digests: list[CriticDigest] = Field(default_factory=list)

    def add_summary(self, text: str) -> None:
        if text:
            self.summaries.append(text)

    def add_critic(self, digest: CriticDigest) -> None:
        self.critic_digests.append(digest)
