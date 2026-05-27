# Benchmark Sample

下面是一组 Task 015 完成后的典型输出：

```text
Runtime Compare
legacy    | legacy_react | 3830ms | 2 steps | 1 tool_call | 4 trace rows
langgraph | react_graph  | 1578ms | 2 steps | 1 tool_call | 7 trace rows
```

## 解释方式

- `legacy` trace 更短，因为循环是隐式的
- `langgraph` trace 更长，因为 `prepare_context / llm / tool / finalize` 都被显式记录
- `langgraph` 的价值不只在性能，而在于可解释性和可复盘性
