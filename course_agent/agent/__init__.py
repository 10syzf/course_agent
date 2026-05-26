"""Agent 实现层（Task 012：四角分工 + Orchestrator）."""

from course_agent.agent.base import AgentMessage, BaseAgent
from course_agent.agent.critic import CRITIC_SYSTEM_PROMPT, CriticAgent
from course_agent.agent.examiner import EXAMINER_SYSTEM_PROMPT, ExaminerAgent
from course_agent.agent.orchestrator import (
    Orchestrator,
    OrchestratorResult,
    SubTaskResult,
)
from course_agent.agent.planner import PLANNER_SYSTEM_PROMPT, PlannerAgent
from course_agent.agent.solver import SOLVER_SYSTEM_PROMPT, SolverAgent

__all__ = [
    # base
    "AgentMessage",
    "BaseAgent",
    # 4 个角色
    "ExaminerAgent",
    "EXAMINER_SYSTEM_PROMPT",
    "PlannerAgent",
    "PLANNER_SYSTEM_PROMPT",
    "SolverAgent",
    "SOLVER_SYSTEM_PROMPT",
    "CriticAgent",
    "CRITIC_SYSTEM_PROMPT",
    # 编排器
    "Orchestrator",
    "OrchestratorResult",
    "SubTaskResult",
]
