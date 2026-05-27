# Context Compression Demo

## 演示命令

```bash
uv run course-agent context inspect
uv run course-agent context inspect --role solver --query "帮我总结上下文压缩策略"
uv run course-agent context profile
```

## 看什么

- `total_chars`
- `selected_chars`
- `dropped_sections`
- `compression_saved_chars`
- section 来源分布

## 讲解重点

- `truncate` 是保底策略
- `extractive` 适合 history / task notes
- `summary` 适合 long memory / handoff / 长文本

## 可延伸的话题

- 现在是字符级 budget
- 后续可以升级到 tokenizer-aware budget
- 后续也可以加更强的 rerank / extract / summarize pipeline
