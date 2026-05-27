# Task 018：Context Governance

## 本期主题

Task 017 解决的是 prompt contract。
Task 018 解决的是 context governance。

这期的核心问题不是“怎么写提示词”，而是：

- 模型到底看到了哪些信息
- 这些信息为什么被保留
- 超预算时谁该被压缩、谁该被丢弃

## 关键升级

- 新增 `ContextSection` / `ContextEnvelope` / `ContextBudget`
- 新增 selector / compressor / compiler / artifact / profiling
- `AgentLoop` 与 `ReactGraphRuntime` 接入统一 context compiler
- `MemoryManager` 从文本 enrich 升级为 section-based policy
- 多 Agent 增加 handoff 结构，不再依赖伪装成 history 的 feedback

## 分享时可以强调

- prompt 决定“怎么约束模型”
- context 决定“模型看到了什么”
- 真正复杂的 Agent 平台，迟早都要从 prompt 走向 context
