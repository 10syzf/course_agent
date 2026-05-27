"""Task 014：图运行时相关提示与常量."""

GRAPH_FALLBACK_MERMAID = """flowchart TD
    START([START]) --> Planner
    Planner --> PickNext
    PickNext -->|has task| Solver
    PickNext -->|done| Finalize
    Solver --> Critic
    Critic --> RefineDecision
    RefineDecision -->|retry| Solver
    RefineDecision -->|append| Append
    Append --> PickNext
    Finalize --> END([END])
"""


__all__ = ["GRAPH_FALLBACK_MERMAID"]
