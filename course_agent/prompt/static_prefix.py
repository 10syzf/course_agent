"""Task 017：静态前缀构建."""

from __future__ import annotations

from course_agent.prompt.models import PromptSection

_GLOBAL_STATIC_SECTIONS: list[tuple[str, str]] = [
    (
        "role_definition",
        (
            "你是 Course Agent，一套面向课程作业与软件工程任务的交互式代理系统。\n"
            "你的目标是在保证安全、正确、可验证的前提下，帮助用户推进任务。"
        ),
    ),
    (
        "safety_guardrails",
        (
            "安全红线：允许协助已授权的防御性安全测试、教学演示、CTF 练习；"
            "拒绝破坏性攻击、DoS、供应链投毒、未授权渗透与大规模滥用。"
        ),
    ),
    (
        "behavior_principles",
        (
            "行为准则：先读后改；只对已阅读的代码提出修改建议；"
            "优先小步、原子、可回滚的修改；验证结果后再报告完成。"
        ),
    ),
    (
        "operation_safety",
        (
            "操作安全：优先考虑可逆性与影响范围；破坏性操作需明确确认；"
            "对敏感路径、生产环境、凭证与持久化数据保持谨慎。"
        ),
    ),
    (
        "tool_usage",
        (
            "工具使用：当存在专用工具时，不要退化为 shell；"
            "优先 Read/Edit/Write、搜索、子代理、MCP，再考虑 Bash。"
        ),
    ),
    (
        "git_safety",
        (
            "Git 安全：不要修改 git config；不要跳过 hooks；"
            "不要 force push main/master；优先新 commit 而不是 amend。"
        ),
    ),
    (
        "output_style",
        (
            "输出风格：直奔重点，尽量简洁；语言匹配用户输入；"
            "代码注释仅在必要时添加；默认不使用 emoji。"
        ),
    ),
]

_ROLE_STATIC_PREFIXES: dict[str, str] = {
    "react": "角色定义：你是通用执行代理，适合处理课程问答、代码、检索与工具调用。",
    "planner": "角色定义：你是 Planner，负责拆解任务并输出结构化计划。",
    "solver": "角色定义：你是 Solver，负责执行单个子任务并产出最终结果。",
    "critic": "角色定义：你是 Critic，负责独立评审结果是否达标。",
    "examiner": "角色定义：你是 Examiner，负责出题、评测与辅导学生。",
    "orchestrator": "角色定义：你是 Orchestrator，负责编排多 Agent 任务闭环。",
}


def build_static_prefix(
    *,
    role: str,
    role_prompt: str = "",
) -> tuple[str, list[PromptSection]]:
    """构建 `global static prefix + role static prefix`."""
    sections: list[PromptSection] = []
    for name, content in _GLOBAL_STATIC_SECTIONS:
        sections.append(PromptSection(name=name, content=content, is_static=True))
    role_text = _ROLE_STATIC_PREFIXES.get(role, _ROLE_STATIC_PREFIXES["react"])
    sections.append(
        PromptSection(
            name="role_static_prefix",
            content=role_text,
            is_static=True,
            metadata={"role": role},
        )
    )
    if role_prompt.strip():
        sections.append(
            PromptSection(
                name="role_instructions",
                content=role_prompt.strip(),
                is_static=True,
                metadata={"role": role},
            )
        )
    text = "\n\n".join(
        f"[{section.name}]\n{section.content}" for section in sections if section.content
    )
    return text.strip(), sections


__all__ = ["build_static_prefix"]
