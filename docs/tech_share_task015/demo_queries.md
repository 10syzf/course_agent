# Demo Queries

## 单 Agent 对比

```bash
uv run course-agent chat "帮我算一下 (3+5)*2" --backend legacy
uv run course-agent chat "帮我算一下 (3+5)*2" --backend langgraph
```

## Replay

```bash
uv run course-agent replay latest
uv run course-agent replay export --format md
```

## Benchmark

```bash
uv run course-agent benchmark runtime --backend legacy
uv run course-agent benchmark runtime --backend langgraph
uv run course-agent benchmark compare
```

## 多 Agent 图

```bash
uv run course-agent graph
```
