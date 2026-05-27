# HITL Demo

## 人工补充输入

```bash
uv run course-agent session start "这题我稍后补充资料"
uv run course-agent session continue <session_id> --input "补充信息：继续"
```

## 人工审批

```bash
uv run course-agent session start "这个任务需要你确认后再继续"
uv run course-agent session resume <session_id>
```

## 分享时可以强调

- graph 并不一定一次跑完
- 某些节点可以主动进入 waiting 状态
- 人可以在图中间接管，再把任务送回运行时继续
