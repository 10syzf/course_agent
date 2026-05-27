# Resume Demo

## CLI 演示顺序

```bash
uv run course-agent session start "这个任务需要你确认后再继续"
uv run course-agent session list
uv run course-agent session show <session_id>
uv run course-agent session resume <session_id>
```

## 展示重点

- `session_id`
- `status`
- `waiting_reason`
- `latest_replay_path`
- 最终变为 `completed`
