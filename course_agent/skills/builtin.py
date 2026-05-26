"""内建 Skill（Task 013）."""

from __future__ import annotations

from course_agent.skills.runtime import SkillContext, skill


@skill(
    name="study_plan_skill",
    description="基于主题和天数生成结构化复习计划",
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "days": {"type": "integer", "default": 7},
        },
        "required": ["topic"],
    },
    tags=["study", "planner"],
)
def study_plan_skill(ctx: SkillContext, topic: str, days: int = 7) -> str:
    days = max(1, min(int(days), 30))
    lines = [f"学习主题：{topic}", f"总天数：{days}", "", "计划："]
    for i in range(1, days + 1):
        lines.append(f"- Day {i}：复习 {topic} 的一个关键点，并完成 2 道练习题")
    return "\n".join(lines)


@skill(
    name="quiz_from_notes_skill",
    description="根据一段笔记文本生成 3 道练习题",
    parameters={
        "type": "object",
        "properties": {
            "notes": {"type": "string"},
            "count": {"type": "integer", "default": 3},
        },
        "required": ["notes"],
    },
    tags=["quiz", "notes"],
)
def quiz_from_notes_skill(ctx: SkillContext, notes: str, count: int = 3) -> str:
    count = max(1, min(int(count), 5))
    seed = (notes or "").strip().replace("\n", " ")
    seed = seed[:60] if seed else "课程重点"
    lines = [f"基于笔记生成练习题（共 {count} 题）:"]
    for i in range(1, count + 1):
        lines.append(f"{i}. 请解释“{seed}”中的一个关键概念，并给出一个例子。")
    return "\n".join(lines)
