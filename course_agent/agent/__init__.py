"""Agent 实现层（MVP 先只暴露一个通用 Agent）."""

from course_agent.agent.examiner import EXAMINER_SYSTEM_PROMPT, ExaminerAgent

__all__ = ["ExaminerAgent", "EXAMINER_SYSTEM_PROMPT"]
