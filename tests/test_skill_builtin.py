"""内建 Skill 单测（Task 013）."""

from __future__ import annotations

import pytest

from course_agent.skills import get_skill_registry
from course_agent.skills.runtime import LocalSkillProvider


def test_builtin_skill_names_present():
    names = get_skill_registry().list_names()
    assert "study_plan_skill" in names
    assert "quiz_from_notes_skill" in names


@pytest.mark.asyncio
async def test_study_plan_skill_happy_path():
    provider = LocalSkillProvider()
    result = await provider.call(
        "study_plan_skill",
        {"topic": "线性代数", "days": 3},
    )
    assert "线性代数" in result.output
    assert "Day 1" in result.output
    assert "Day 3" in result.output


@pytest.mark.asyncio
async def test_study_plan_skill_days_clamped():
    provider = LocalSkillProvider()
    result = await provider.call(
        "study_plan_skill",
        {"topic": "微积分", "days": 0},
    )
    assert "总天数：1" in result.output


@pytest.mark.asyncio
async def test_quiz_from_notes_skill_happy_path():
    provider = LocalSkillProvider()
    result = await provider.call(
        "quiz_from_notes_skill",
        {"notes": "动态规划用于解决具有重叠子问题和最优子结构的问题", "count": 2},
    )
    assert "共 2 题" in result.output
    assert "动态规划" in result.output


@pytest.mark.asyncio
async def test_quiz_from_notes_skill_count_clamped():
    provider = LocalSkillProvider()
    result = await provider.call(
        "quiz_from_notes_skill",
        {"notes": "abc", "count": 99},
    )
    assert "共 5 题" in result.output


@pytest.mark.asyncio
async def test_quiz_from_notes_skill_empty_notes_fallback():
    provider = LocalSkillProvider()
    result = await provider.call(
        "quiz_from_notes_skill",
        {"notes": "", "count": 1},
    )
    assert "课程重点" in result.output
