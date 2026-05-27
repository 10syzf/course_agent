# Multi-Agent Context Handoff

## 为什么要做

多 Agent 的难点不是“多几个角色”，而是：

- Planner 怎么把任务交给 Solver
- Critic 怎么把反馈交回 Solver
- Orchestrator 怎么累计跨 sub-task 的工作上下文

## Task 018 的最小实现

- `SubTaskBrief`
- `HandoffContext`
- `CriticDigest`
- `TaskContextLedger`

## 当前收益

- refine feedback 不再伪装成 `system history`
- Solver 下一轮能显式收到 critic feedback
- Orchestrator 能积累 prior summaries 与 critic digests

## 分享时可以强调

- history 代表“对话历史”
- handoff 代表“agent 间工作交接”
- 这两个概念拆开后，系统边界会清晰很多
