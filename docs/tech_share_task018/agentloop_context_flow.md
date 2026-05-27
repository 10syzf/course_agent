# AgentLoop Context Flow

## 新链路

```text
history / memory / session_notes / task_notes
        │
        ▼
compile_context()
        │
        ├── select_context_sections()
        ├── compress_section()
        └── ContextEnvelope
        │
        ▼
render_context_messages()
        │
        ▼
Prompt Compiler + Context Compiler
        │
        ▼
Final LLM Input
```

## 关键点

- Prompt Compiler 仍然负责 `static_prefix` / `dynamic_tail`
- Context Compiler 负责真正进入模型的信息层
- 最终输入变成：prompt constraints + selected context + current user input

## 演示建议

1. 先展示 `prompt inspect`
2. 再展示 `context inspect`
3. 说明两者分别回答“怎么约束模型”和“模型看到了什么”
