# Prompt Profiling Demo

## 基础命令

```bash
uv run course-agent prompt profile
uv run course-agent prompt profile --role planner --query "把这个复杂任务拆成 3 步"
```

## 关注指标

- `static_chars`
- `dynamic_chars`
- `full_chars`
- `static_ratio`
- `dynamic_ratio`

## 演示重点

- 静态前缀占比通常更高，说明共享规则已被集中收敛
- 动态尾部虽然更短，但承载了环境、项目说明、session、任务上下文
- profiling 能帮助解释后续 prompt 优化应该改哪里

## 分享时可以强调

- benchmark 看的是运行时结果
- profiling 看的是 prompt 结构本身
- 两者结合后，才能更系统地做 prompt 调优
