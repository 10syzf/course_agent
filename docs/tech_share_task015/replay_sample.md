# Replay Sample

典型 replay artifact 结构：

```json
{
  "thread_id": "xxx",
  "backend": "langgraph",
  "runtime_kind": "react_graph",
  "input": "帮我算一下 (3+5)*2",
  "steps": 2,
  "trace": [
    {"node": "start", "kind": "input", "summary": "帮我算一下 (3+5)*2"},
    {"node": "prepare_context", "kind": "context", "summary": "messages=2"},
    {"node": "llm", "kind": "tool_plan", "summary": "(no thought)"},
    {"node": "tool", "kind": "tool_call", "summary": "calculator"},
    {"node": "tool", "kind": "tool_result", "summary": "16"},
    {"node": "llm", "kind": "final_answer", "summary": "计算结果是：16"},
    {"node": "finalize", "kind": "finalize", "summary": "计算结果是：16"}
  ],
  "node_sequence": ["start", "prepare_context", "llm", "tool", "tool", "llm", "finalize"],
  "final_answer": "计算结果是：16"
}
```

## 分享时可强调

- replay 是“运行证据”
- 它可以直接配合 benchmark / Mermaid / UI Step 一起讲
- 它让一次 agent 执行具备可复盘性
