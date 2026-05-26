"""Skill registry 兼容导出（Task 013）."""

from course_agent.skills.runtime import (
    LocalSkillProvider,
    Skill,
    SkillContext,
    SkillRegistry,
    get_skill_registry,
    skill,
)

__all__ = [
    "LocalSkillProvider",
    "Skill",
    "SkillContext",
    "SkillRegistry",
    "get_skill_registry",
    "skill",
]
