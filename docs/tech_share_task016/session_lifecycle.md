# Session Lifecycle

## 推荐状态流转

```text
created
  -> running
  -> waiting_human_input / waiting_approval
  -> running
  -> completed
```

也支持：

- `failed`
- `cancelled`

## Task 016 的实现重点

- session 元数据持久化
- replay 路径与 session 关联
- waiting_reason 可在 CLI / Chainlit 中展示
