# Prompt Inspect Demo

## 基础命令

```bash
uv run course-agent prompt inspect
uv run course-agent prompt inspect --role solver --query "帮我总结 Prompt Compiler 的作用"
uv run course-agent prompt latest
```

## 演示顺序

1. 先运行 `prompt inspect`，展示完整 prompt 已经不是散落字符串。
2. 再展示输出中的 `static_prefix` 与 `dynamic_tail`，说明两层边界。
3. 再运行 `prompt latest`，说明 prompt artifact 已经落盘，可以复查最近一次编译结果。

## 分享时可以强调

- inspect 不是为了“看一眼文本”
- 而是为了回答“这次到底给模型发了什么”
- latest 让 prompt 成为可沉淀的工件，而不是瞬时上下文
